import uuid
import asyncio
import threading
import json
import logging
from typing import List, Dict, Any, Optional, AsyncGenerator
from fastapi import HTTPException

from common_lib.modules.orchestration.workflow.execution.executor import GraphExecutor
from common_lib.modules.orchestration.workflow.execution.core import ExecutionEngine
from common_lib.modules.orchestration.workflow.execution.context import ExecutionContext
from common_lib.modules.orchestration.workflow.execution.primitives import Graph, State, Transition
from common_lib.modules.orchestration.workflow.observability import EventTracer

logger = logging.getLogger(__name__)

class WorkflowService:
    def get_all(self, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
        # This would usually come from a DB or memory store.
        # For now, we'll return an empty list or mock data
        return []

    def get_by_id(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        return None

    def create(self, workflow_in: Any) -> Dict[str, Any]:
        return {}

    def update(self, workflow_id: str, workflow_in: Any) -> Dict[str, Any]:
        return {}

    def delete(self, workflow_id: str) -> bool:
        return True

    def run_graph(self, nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]], inputs: Dict[str, Any] = {}) -> Dict[str, Any]:
        """
        Sync version for backward compatibility.
        """
        graph_id = f"dynamic_{uuid.uuid4().hex[:8]}"
        graph = Graph(id=graph_id, name="UI Transient Workflow", version="1.0.0")
        state_map = {}
        incoming_counts = {n['id']: 0 for n in nodes}
        for e in edges:
            incoming_counts[e['to']] = incoming_counts.get(e['to'], 0) + 1
        start_node_id = next((nid for nid, count in incoming_counts.items() if count == 0), nodes[0]['id'] if nodes else None)
        graph.start_state_id = start_node_id

        for n in nodes:
            state = State(
                id=n['id'],
                tool_id=n.get('toolId') or n.get('type'),
                static_inputs=n.get('properties', {}),
                description=n.get('title', n['id'])
            )
            graph.add_state(state)
            state_map[n['id']] = state

        for e in edges:
            parent_state = state_map.get(e['from'])
            if parent_state:
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
            "status": "success",
            "results": results,
            "trace": [e.model_dump() if hasattr(e, 'model_dump') else e for e in tracer.backends[0].events] if tracer.backends else []
        }

    async def run_graph_stream(self, nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]], inputs: Dict[str, Any] = {}) -> AsyncGenerator[Dict[str, Any], None]:
        """
        SSE stream version of run_graph.
        """
        queue = asyncio.Queue()
        loop = asyncio.get_running_loop()

        from dataclasses import asdict
        from common_lib.modules.orchestration.workflow.observability.events import EventType

        class QueueBackend:
            def emit(self, event):
                try:
                    data = asdict(event)
                    # Convert EventType enum to string
                    if 'event_type' in data and isinstance(data['event_type'], EventType):
                        data['event_type'] = data['event_type'].value
                    
                    # Ensure timestamp is ISO format
                    if 'timestamp' in data and hasattr(data['timestamp'], 'isoformat'):
                        data['timestamp'] = data['timestamp'].isoformat()
                        
                    loop.call_soon_threadsafe(queue.put_nowait, data)
                except Exception as e:
                    logger.error(f"Failed to emit event to queue: {e}")

            def flush(self): pass
            def close(self): pass

        # 1. Build Backend Graph
        graph_id = f"dynamic_{uuid.uuid4().hex[:8]}"
        
        incoming_counts = {n['id']: 0 for n in nodes}
        for e in edges:
            incoming_counts[e['to']] = incoming_counts.get(e['to'], 0) + 1
        
        start_node_id = next((nid for nid, count in incoming_counts.items() if count == 0), nodes[0]['id'] if nodes else None)
        
        if not start_node_id:
            raise ValueError("Workflow graph has no nodes or cannot determine a start node.")

        graph = Graph(id=graph_id, name="UI Transient Workflow", start_state_id=start_node_id)
        state_map = {}
        
        for n in nodes:
            state = State(
                id=n['id'],
                tool_id=n.get('toolId') or n.get('type'),
                static_inputs=n.get('properties', {}),
                description=n.get('title', n['id'])
            )
            graph.add_state(state)
            state_map[n['id']] = state

        for e in edges:
            parent_state = state_map.get(e['from'])
            if parent_state:
                transition = Transition(
                    to_state_id=e['to'],
                    description=f"Link from {e['from']} to {e['to']}"
                )
                parent_state.transitions.append(transition)

        def run_sync():
            try:
                from common_lib.modules.core_infrastructure.registry import RegistryService
                registry = None
                try:
                    from app.modules.demo.routes.react_agent import _engine_manager
                    if _engine_manager and _engine_manager.registry_svc:
                        registry = _engine_manager.registry_svc
                except ImportError:
                    pass

                if registry is None:
                    logger.info("Initializing local tool registry for workflow...")
                    registry = RegistryService()
                    registry.auto_register_common_lib_tools()

                engine = ExecutionEngine(registry=registry)
                tracer = EventTracer()
                tracer.add_backend(QueueBackend())
                executor = GraphExecutor(engine, tracer)
                context = ExecutionContext(agent_id="workflow_system", role="executor")
                executor.execute(graph, inputs, context)
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, {"event_type": "workflow.finished"})

        # Run execution in a separate thread
        threading.Thread(target=run_sync, daemon=True).start()

        while True:
            event = await queue.get()
            if event.get("event_type") == "workflow.finished":
                break
            yield event

workflow_service = WorkflowService()
