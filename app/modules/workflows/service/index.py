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
                target_handle = e.get('toPort') or e.get('targetHandle') or e.get('targetPort')
                if target_handle and target_handle in ['positive', 'negative', 'latent', 'latent_image', 'samples', 'model', 'clip', 'vae']:
                    # Normalize target handle names
                    normalized_handle = "latent" if target_handle == "latent_image" or target_handle == "samples" else target_handle
                    
                    logger.info(f"[Sync] Mapping edge {e['from']} -> {e['to']} (Port: {normalized_handle})")
                    # Use standard output keys based on source node type
                    source_node = next((n for n in nodes if n['id'] == e['from']), {})
                    source_type = source_node.get('toolId') or source_node.get('type', '')
                    
                    # GraphExecutor uses {node_id_output.key} for path resolution
                    output_key = "text" if "clip_encode" in source_type else ("latent" if "latent" in source_type or "ksampler" in source_type else ("image" if "vae_decode" in source_type else "output"))
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
            
            state = State(
                id=n['id'],
                tool_id=n.get('toolId') or n.get('type'),
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
                if target_handle and target_handle in ['positive', 'negative', 'latent', 'latent_image', 'samples', 'model', 'clip', 'vae']:
                    # Normalize target handle names
                    normalized_handle = "latent" if target_handle == "latent_image" or target_handle == "samples" else target_handle
                    
                    logger.info(f"[Stream] Mapping edge {e['from']} -> {e['to']} (Port: {normalized_handle})")
                    # Use standard output keys based on source node type
                    source_node = next((n for n in nodes if n['id'] == e['from']), {})
                    source_type = source_node.get('toolId') or source_node.get('type', '')
                    
                    # GraphExecutor uses {node_id_output.key} for path resolution
                    output_key = "text" if "clip_encode" in source_type else ("latent" if "latent" in source_type or "ksampler" in source_type else ("image" if "vae_decode" in source_type else "output"))
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
