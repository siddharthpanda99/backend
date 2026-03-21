import json
import logging
import uuid
from typing import Any, Dict, List, AsyncGenerator
import asyncio

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

    def run_graph(self, nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]], inputs: Dict[str, Any] = {}) -> Dict[str, Any]:
        """
        Sync version for backward compatibility.
        """
        # 1. Topological Sort for linear execution (since GraphExecutor follows one path)
        incoming_counts = {n['id']: 0 for n in nodes}
        adj = {n['id']: [] for n in nodes}
        for e in edges:
            incoming_counts[e['to']] = incoming_counts.get(e['to'], 0) + 1
            adj[e['from']].append(e['to'])
        
        # Simple Kahn's algorithm for topsort
        queue = [n['id'] for n in nodes if incoming_counts.get(n['id'], 0) == 0]
        sorted_nodes = []
        while queue:
            u = queue.pop(0)
            sorted_nodes.append(u)
            for v in adj[u]:
                incoming_counts[v] -= 1
                if incoming_counts[v] == 0:
                    queue.append(v)
        
        # If topsort failed (e.g. cycles), fallback to original list
        if len(sorted_nodes) < len(nodes):
            sorted_nodes = [n['id'] for n in nodes]

        start_node_id = sorted_nodes[0] if sorted_nodes else "unknown"

        graph_id = f"dynamic_{uuid.uuid4().hex[:8]}"
        graph = Graph(id=graph_id, name="UI Transient Workflow", start_state_id=start_node_id)
        state_map = {}
        
        for n in nodes:
            props = n.get('properties') or n.get('data', {}).get('properties') or {}
            state = State(
                id=n['id'],
                tool_id=n.get('toolId') or n.get('type'),
                static_inputs=props,
                description=n.get('title', n['id'])
            )
            graph.add_state(state)
            state_map[n['id']] = state

        # 2. Linear Chaining: Ensure GraphExecutor hits every node in dependency order
        logger.info(f"[WorkflowService] Linearizing {len(sorted_nodes)} nodes: {sorted_nodes}")
        for i in range(len(sorted_nodes) - 1):
            curr_id = sorted_nodes[i]
            next_id = sorted_nodes[i+1]
            if curr_id in state_map and next_id in state_map:
                # Add transition to force path
                state_map[curr_id].transitions.append(Transition(to_state_id=next_id, description="Linear dependency chain"))

        # 3. Dynamic input mapping based on edges (No transitions here, pure data flow)

        for e in edges:
            parent_state = state_map.get(e['from'])
            target_state = state_map.get(e['to'])
            if parent_state and target_state:
                # Automatic input mapping based on toPort/targetHandle/targetPort
                # Automatic input mapping based on toPort/targetHandle/targetPort
                target_handle = e.get('toPort') or e.get('targetHandle') or e.get('targetPort')
                source_handle = e.get('fromPort') or e.get('sourceHandle') or e.get('sourcePort')
                
                if target_handle:
                    # Normalize target handle names
                    normalized_handle = target_handle
                    if target_handle in ["latent_image", "samples"]:
                        normalized_handle = "latent"
                    
                    logger.info(f"[WorkflowService] Mapping edge {e['from']} -> {e['to']} (Port: {normalized_handle})")
                    
                    # Use fromPort as primary source for output key, fallback to type-based guessing
                    output_key = source_handle or "output"
                    
                    if not source_handle:
                        source_node = next((n for n in nodes if n['id'] == e['from']), {})
                        source_type = source_node.get('toolId') or source_node.get('type', '')
                        
                        if "clip_encode" in source_type: output_key = "conditioning"
                        elif "prompt" in source_type: output_key = "text"
                        elif "ksampler" in source_type: output_key = "latent"
                        elif "vae_decode" in source_type: output_key = "image"
                        elif "face_swapper" in source_type: output_key = "image"
                        elif "load_character" in source_type: output_key = normalized_handle # image/mask/tags fallback
                    
                    # 2. Specialized Key mappings (Crucial for Character DNA flow)
                    if normalized_handle == "tags" and "interrogate" in source_type:
                        output_key = "tags"
                    elif normalized_handle == "biography" and "interrogate" in source_type:
                        output_key = "description"
                    elif normalized_handle == "silhouette_image_path" and "body_silhouette_extractor" in source_type:
                        output_key = "mask_path"
                    
                    target_state.static_inputs[normalized_handle] = f"{{{e['from']}_output.{output_key}}}"

                if any(t.to_state_id == e['to'] for t in parent_state.transitions):
                    continue
                transition = Transition(
                    to_state_id=e['to'],
                    description=f"Link from {e['from']} to {e['to']}"
                )
                parent_state.transitions.append(transition)

        try:
            from app.modules.demo.routes.react_agent import _engine_manager
            registry = _engine_manager.registry_svc if _engine_manager else None
        except ImportError:
            registry = None

        if registry is None:
            from common_lib.modules.core_infrastructure.registry import RegistryService
            registry = RegistryService()
            # If for some reason we have a fresh registry, we MUST register tools
            registry.auto_register_common_lib_tools()

        engine = ExecutionEngine(registry=registry)
        tracer = EventTracer()
        executor = GraphExecutor(engine, tracer)
        context = ExecutionContext(agent_id="workflow_system", role="executor")
        results = executor.execute(graph, inputs, context)
        return {
            "workflow_id": graph_id,
            "status": "completed",
            "results": results
        }

    async def run_graph_stream(self, nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]], inputs: Dict[Dict[str, Any], Any] = {}) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Executes a workflow graph and streams events via AsyncGenerator.
        """
        queue = asyncio.Queue()
        loop = asyncio.get_event_loop()

        class QueueTracer(EventTracer):
            def emit(self, event):
                try:
                    # Robust serialization for Event objects which may contain Enums (EventType)
                    if hasattr(event, "model_dump"):
                        data = event.model_dump(mode='json') # Pydantic v2 handles enums here
                    elif hasattr(event, "__dict__"):
                        data = {}
                        for k, v in event.__dict__.items():
                            if hasattr(v, "value"): # Handle Enums
                                data[k] = v.value
                            elif hasattr(v, "isoformat"):
                                data[k] = v.isoformat()
                            else:
                                data[k] = v
                    else:
                        data = str(event)
                        
                    loop.call_soon_threadsafe(queue.put_nowait, data)
                except Exception as e:
                    logger.error(f"Failed to emit event to queue: {e}")

            def flush(self): pass
            def close(self): pass

        # 1. Topological Sort for linear execution (since GraphExecutor follows one path)
        incoming_counts = {n['id']: 0 for n in nodes}
        adj = {n['id']: [] for n in nodes}
        for e in edges:
            incoming_counts[e['to']] = incoming_counts.get(e['to'], 0) + 1
            adj[e['from']].append(e['to'])
        
        # Simple Kahn's algorithm for topsort
        topsort_queue = [n['id'] for n in nodes if incoming_counts.get(n['id'], 0) == 0]
        sorted_nodes = []
        while topsort_queue:
            u = topsort_queue.pop(0)
            sorted_nodes.append(u)
            for v in adj[u]:
                incoming_counts[v] -= 1
                if incoming_counts[v] == 0:
                    topsort_queue.append(v)
        
        # If topsort failed (e.g. cycles), fallback to original list
        if len(sorted_nodes) < len(nodes):
            sorted_nodes = [n['id'] for n in nodes]

        start_node_id = sorted_nodes[0] if sorted_nodes else "unknown"

        graph_id = f"dynamic_{uuid.uuid4().hex[:8]}"
        graph = Graph(id=graph_id, name="UI Transient Workflow", start_state_id=start_node_id)
        state_map = {}
        
        for n in nodes:
            props = n.get('properties') or n.get('data', {}).get('properties') or {}
            # Support node-level timeout overrides from UI or properties
            node_timeout = n.get('timeout_seconds') or n.get('timeoutSeconds') or props.get('timeout_seconds') or props.get('timeoutSeconds')
            
            raw_type = n.get('toolId') or n.get('type', '')
            # Normalize Tool ID: 'Load Image' -> 'vision.load_image'
            tool_id = raw_type
            if not tool_id.startswith('vision.'):
                norm = raw_type.lower().replace(' ', '_')
                # Check known mappings
                mappings = {
                    'load_image': 'vision.load_image',
                    'face_analysis': 'vision.face_analysis',
                    'face_extractor': 'vision.face_extractor',
                    'controlnet_extractor': 'vision.controlnet_extractor',
                    'save_character_profile': 'vision.save_character_profile',
                    'face_swapper': 'vision.face_swapper'
                }
                if norm in mappings:
                    tool_id = mappings[norm]
            
            state = State(
                id=n['id'],
                tool_id=tool_id,
                static_inputs=props,
                description=n.get('title', n['id']),
                timeout_seconds=node_timeout
            )
            graph.add_state(state)
            state_map[n['id']] = state

        # 2. Linear Chaining: Ensure GraphExecutor hits every node in dependency order
        logger.info(f"[WorkflowService] Linearizing {len(sorted_nodes)} nodes: {sorted_nodes}")
        for i in range(len(sorted_nodes) - 1):
            curr_id = sorted_nodes[i]
            next_id = sorted_nodes[i+1]
            if curr_id in state_map and next_id in state_map:
                # Add transition to force path
                state_map[curr_id].transitions.append(Transition(to_state_id=next_id, description="Linear dependency chain"))

        # 3. Dynamic input mapping based on edges (No transitions here, pure data flow)

        for e in edges:
            parent_state = state_map.get(e['from'])
            target_state = state_map.get(e['to'])
            if parent_state and target_state:
                # Automatic input mapping based on toPort/targetHandle/targetPort
                target_handle = e.get('toPort') or e.get('targetHandle') or e.get('targetPort')
                # Expand supported ports for vision/reactor
                vision_ports = ['positive', 'negative', 'latent', 'latent_image', 'samples', 'model', 'clip', 'vae',
                                'image', 'source_image', 'face_model', 'options', 'face_boost', 'mask',
                                'image_path', 'face_image_path', 'canny_image_path', 'depth_image_path', 
                                'pose_image_path', 'tags', 'profile_name']
                
                if target_handle and (target_handle.lower() in vision_ports or any(k in target_handle.lower() for k in ['image', 'path', 'tags'])):
                    # Normalize target handle names
                    normalized_handle = target_handle.lower()
                    if target_handle in ["latent_image", "samples"]:
                        normalized_handle = "latent"
                    
                    logger.info(f"[Stream] Mapping edge {e['from']} -> {e['to']} (Port: {normalized_handle})")
                    # Use standard output keys based on source node type
                    source_node = next((n for n in nodes if n['id'] == e['from']), {})
                    source_type = source_node.get('toolId') or source_node.get('type', '')
                    
                    # GraphExecutor uses {node_id_output.key} for path resolution
                    output_key = "output"
                    
                    # 0. Heuristic: if normalized_handle is a standard data type, use it as default key
                    standard_data_ports = ['image', 'mask', 'latent', 'model', 'clip', 'vae', 'conditioning', 'text']
                    if normalized_handle in standard_data_ports:
                        output_key = normalized_handle

                    # 1. Handle specialized output keys by source type
                    if "clip_encode" in source_type: output_key = "conditioning"
                    elif "prompt" in source_type: output_key = "text"
                    elif "string_concatenate" in source_type: output_key = "text"
                    elif "ksampler" in source_type: output_key = "latent"
                    elif "vae_decode" in source_type: output_key = "image"
                    elif "load_character" in source_type: output_key = normalized_handle # image/mask/tags
                    elif "face_model" in source_type: output_key = "face_model"
                    elif "reactor_options" in source_type: output_key = "options"
                    elif "face_boost" in source_type: output_key = "face_boost"
                    elif "face_swapper" in source_type: output_key = "image"
                    
                    # 2. Handle Profile-specific Handle to Key mapping (Crucial for Character DNA flow)
                    if normalized_handle == "image_path" and "load_image" in source_type:
                        output_key = "PATH"
                    elif normalized_handle == "face_image_path" and "face_extractor" in source_type:
                        output_key = "face_path"
                    elif "image_path" in normalized_handle and "controlnet_extractor" in source_type:
                        output_key = "image_path"
                    elif normalized_handle == "tags" and "interrogate" in source_type:
                        output_key = "tags"
                    elif (normalized_handle == "biography" or normalized_handle == "bio") and "interrogate" in source_type:
                        output_key = "description"
                    elif normalized_handle == "silhouette_image_path" and "body_silhouette_extractor" in source_type:
                        output_key = "mask_path"
                    elif normalized_handle == "tags" and "face_analysis" in source_type:
                        output_key = "dna_tags"
                    
                    target_state.static_inputs[normalized_handle] = f"{{{e['from']}_output.{output_key}}}"

                if any(t.to_state_id == e['to'] for t in parent_state.transitions):
                    continue
                transition = Transition(
                    to_state_id=e['to'],
                    description=f"Link from {e['from']} to {e['to']}"
                )
                parent_state.transitions.append(transition)

        async def run_in_thread():
            try:
                from app.modules.demo.routes.react_agent import _engine_manager
                registry = _engine_manager.registry_svc if _engine_manager else None
            except ImportError:
                registry = None

            if registry is None:
                from common_lib.modules.core_infrastructure.registry import RegistryService
                registry = RegistryService()
                registry.auto_register_common_lib_tools()

            engine = ExecutionEngine(registry=registry)
            tracer = QueueTracer()
            executor = GraphExecutor(engine, tracer)
            context = ExecutionContext(agent_id="workflow_system", role="executor")
            
            # Run in worker thread
            await loop.run_in_executor(None, executor.execute, graph, inputs, context)
            
            # Signal end of stream
            loop.call_soon_threadsafe(queue.put_nowait, {"event_type": "DONE"})

        task = asyncio.create_task(run_in_thread())

        while True:
            event = await queue.get()
            if isinstance(event, dict) and event.get("event_type") == "DONE":
                break
            yield event

        await task

workflow_service = WorkflowService()
