import json
import logging
import uuid
import asyncio
from typing import Any, Dict, List, AsyncGenerator
from pathlib import Path

from common_lib.modules.orchestration.workflow.execution.executor import GraphExecutor
from common_lib.modules.orchestration.workflow.execution.core import ExecutionEngine
from common_lib.modules.orchestration.workflow.execution.context import ExecutionContext
from common_lib.modules.orchestration.workflow.execution.primitives import Graph, State, Transition
from common_lib.modules.orchestration.workflow.observability import EventTracer, EventType

logger = logging.getLogger(__name__)

class WorkflowService:
    def __init__(self):
        self.workflows = {}

    def get_all(self) -> List[Dict[str, Any]]:
        return list(self.workflows.values())

    def get_by_id(self, workflow_id: str) -> Dict[str, Any]:
        return self.workflows.get(workflow_id, {})

    def create(self, workflow: Dict[str, Any]) -> Dict[str, Any]:
        workflow_id = str(uuid.uuid4())
        workflow['id'] = workflow_id
        self.workflows[workflow_id] = workflow
        return workflow

    def update(self, workflow_id: str, workflow: Dict[str, Any]) -> Dict[str, Any]:
        self.workflows[workflow_id] = workflow
        return workflow

    def delete(self, workflow_id: str) -> bool:
        if workflow_id in self.workflows:
            del self.workflows[workflow_id]
            return True
        return False

    async def run_graph_stream(self, nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]], inputs: Dict[str, Any] = {}) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Executes a workflow graph and streams events via AsyncGenerator.
        Ensures a stable, enforced linear sequence for complex character generation.
        """
        # --- PHASE 0: Infrastructure Setup ---
        event_queue = asyncio.Queue()
        loop = asyncio.get_event_loop()
        
        logger.info(f"[WorkflowService] INITIATING Graph Stream | Nodes: {len(nodes)} | Edges: {len(edges)}")

        class QueueTracer(EventTracer):
            """Dumps every execution event into the stream queue for the UI."""
            def emit(self, event):
                try:
                    data = event.to_dict()
                    logger.info(f"[QueueTracer] EMIT: {data.get('event_type')} (state_id={data.get('state_id')})")
                    
                    # Extract error for debugging
                    error_msg = data.get("error") or (data.get("metadata") or {}).get("error")
                    if error_msg:
                        import sys
                        print(f"\n[QueueTracer] CRITICAL ERROR DETECTED: {error_msg}", file=sys.stderr)
                        logger.error(f"[QueueTracer] ERROR EVENT DETECTED: {error_msg}")
                    
                    loop.call_soon_threadsafe(event_queue.put_nowait, data)
                except Exception as e:
                    import sys
                    print(f"\n[QueueTracer] Serialization Failed: {e}", file=sys.stderr)
                    logger.error(f"[QueueTracer] Serialization Failed: {e}")

            def flush(self): pass
            def close(self): pass

        # --- PHASE 1: DISCOVERY & STATE RESOLUTION ---
        # Map UI identifiers to backend tool signatures and create State objects
        state_map = {}
        tool_mappings = {
            'load_image': 'vision.load_image',
            'face_analysis': 'vision.face_analysis',
            'face_extractor': 'vision.face_extractor',
            'controlnet_extractor': 'vision.controlnet_extractor',
            'save_character_profile': 'vision.save_character_profile',
            'face_swapper': 'vision.face_swapper',
            'biography': 'vision.biography'
        }

        for n in nodes:
            raw_type = n.get('toolId') or n.get('type', '')
            props = n.get('properties') or n.get('data', {}).get('properties') or {}
            
            # Resolve Tool ID
            tool_id = raw_type
            if not tool_id.startswith('vision.'):
                norm = raw_type.lower().replace(' ', '_')
                if norm in tool_mappings:
                    tool_id = tool_mappings[norm]

            state = State(
                id=n['id'],
                tool_id=tool_id,
                static_inputs=props.copy(),
                description=n.get('title', n['id']),
                timeout_seconds=n.get('timeout_seconds', props.get('timeout_seconds', 300))
            )
            state_map[n['id']] = state
            logger.info(f"  - Configured state '{n['id']}' -> {tool_id}")

        # --- PHASE 2: STRATEGIC LINEARIZATION ---
        # Solve the graph, then force a safe linear path [Loader] -> [Analysis] -> [Save]
        adj = {n['id']: [] for n in nodes}
        in_counts = {n['id']: 0 for n in nodes}
        for e in edges:
            adj[e['from']].append(e['to'])
            in_counts[e['to']] += 1
            
        ready_pool = [n['id'] for n in nodes if in_counts[n['id']] == 0]
        base_sorted = []
        while ready_pool:
            curr = ready_pool.pop(0)
            base_sorted.append(curr)
            for neighbor in adj[curr]:
                in_counts[neighbor] -= 1
                if in_counts[neighbor] == 0:
                    ready_pool.append(neighbor)

        # Apply Heuristic Ordering [Loader] -> [Analysis Nodes] -> [Terminal Save Node]
        loaders, savers, middle = [], [], []
        for sid in base_sorted:
            state = state_map.get(sid)
            t_id = str(state.tool_id or "").lower() if state else ""
            if "load_image" in t_id: loaders.append(sid)
            elif "save_profile" in t_id: savers.append(sid)
            else: middle.append(sid)
        
        final_sequence = loaders + middle + savers
        logger.info(f"[WorkflowService] ENFORCED SEQUENCE: {' -> '.join(final_sequence)}")

        # --- PHASE 3: GRAPH CONSTRUCTION ---
        graph_id = f"dynamic_{uuid.uuid4().hex[:8]}"
        graph = Graph(id=graph_id, name="Character DNA Pipeline", start_state_id=final_sequence[0] if final_sequence else "unknown")
        
        for sid in final_sequence:
            if sid in state_map:
                graph.add_state(state_map[sid])
        
        # Build Forced Transition Path
        for i in range(len(final_sequence) - 1):
            curr_id, next_id = final_sequence[i], final_sequence[i+1]
            if curr_id in state_map and next_id in state_map:
                state_map[curr_id].transitions.append(Transition(to_state_id=next_id, description="Linear sequence enforced"))

        # --- PHASE 4: DATA MAPPING (INTERPOLATION CONDUITS) ---
        vision_ports = ['positive', 'negative', 'latent', 'latent_image', 'samples', 'model', 'clip', 'vae',
                        'image', 'source_image', 'face_model', 'options', 'face_boost', 'mask',
                        'image_path', 'face_image_path', 'canny_image_path', 'depth_image_path', 
                        'pose_image_path', 'tags', 'profile_name', 'face_embedding', 
                        'body_measurements', 'color_palette', 'character_notes', 'user_notes']

        for e in edges:
            parent_state = state_map.get(e['from'])
            target_state = state_map.get(e['to'])
            if parent_state and target_state:
                target_port = (e.get('toPort') or e.get('targetHandle') or e.get('targetPort')).lower()
                source_port = (e.get('fromPort') or e.get('sourceHandle') or e.get('sourcePort') or "image").lower()
                source_type = str(parent_state.tool_id or "").lower()

                output_key = source_port
                
                # DNA Conduit Specialized Rules
                if "face_analysis" in source_type:
                    if target_port in ["tags", "character_notes"]: output_key = "dna_tags"
                    elif target_port == "face_embedding": output_key = "face_embedding"
                    elif target_port == "body_measurements": output_key = "measurements"
                    elif target_port == "color_palette": output_key = "color_palette"
                elif "load_image" in source_type and "path" in target_port:
                    output_key = "PATH"
                elif "extractor" in source_type and "path" in target_port:
                    # e.g. controlnet_extractor.image_path or face_extractor.face_path
                    output_key = "face_path" if "face" in source_type else "image_path"
                elif "interrogate" in source_type:
                    output_key = "description" if "bio" in target_port else "tags"
                
                source_tool = str(parent_state.tool_id or "unknown")
                # Use parent_state.id instead of tool name to ensure unique output keys 
                # when multiple nodes of the same tool type exist in the workflow.
                output_prefix = f"{parent_state.id}_output"
                
                target_state.static_inputs[target_port] = f"{{{output_prefix}.{output_key}}}"
                logger.info(f"  - DNA Conduit: {source_tool} (node: {parent_state.id}, key: {output_key}) -> {target_state.tool_id} ({target_port})")

        # --- PHASE 5: EXECUTION THREAD ---
        async def execution_task():
            try:
                # Resolve registry
                try:
                    from app.modules.demo.routes.react_agent import _engine_manager
                    registry = _engine_manager.registry_svc if _engine_manager else None
                except ImportError:
                    registry = None

                if not registry:
                    from common_lib.modules.core_infrastructure.registry import RegistryService
                    registry = RegistryService()
                    registry.auto_register_common_lib_tools()

                shared_tracer = QueueTracer()
                engine = ExecutionEngine(registry=registry, tracer=shared_tracer)
                executor = GraphExecutor(engine, shared_tracer)
                context = ExecutionContext(agent_id="workflow_system", role="executor")
                
                # Execute graph in worker thread to prevent loop blocking
                await loop.run_in_executor(None, executor.execute, graph, inputs, context)
            except Exception as e:
                logger.error(f"[WorkflowService] Execution CRASHED: {e}", exc_info=True)
            finally:
                loop.call_soon_threadsafe(event_queue.put_nowait, {"event_type": "DONE"})

        task = asyncio.create_task(execution_task())

        # --- PHASE 6: STREAM GENERATOR ---
        while True:
            event = await event_queue.get()
            if isinstance(event, dict) and event.get("event_type") == "DONE":
                break
            yield event

        await task

workflow_service = WorkflowService()
