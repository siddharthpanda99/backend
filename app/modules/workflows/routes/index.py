import asyncio
import json
import logging
import traceback
import sys
import uuid
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from typing import List, Dict, Any

# Configure console logging
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)
formatter = logging.Formatter("[%(name)s] %(levelname)s: %(message)s")
handler.setFormatter(formatter)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(handler)
logger.propagate = True

print("[WorkflowRoutes] Module loaded")

router = APIRouter()
 
# Port Aliases for backward compatibility between UI and Backend node definitions
PORT_ALIASES = {
    "nexus.vision.empty_latent": {
        "latent": "samples"
    },
    "nexus.vision.clip_encode": {
        "text": "positive", 
        "latent": "latent_image", 
        "images": "latent",
        "latent_image": "latent_image",
        "conditioning": "positive"  # UI might send conditioning
    },
    "nexus.vision.vae_decode": {
        "latent": "samples", 
        "image": "images",
        "images": "samples",
        "samples": "latent"  # Map samples input to latent argument
    },
    "nexus.vision.upscale_latent": {
        "images": "samples",
        "samples": "latent",
        "latent": "latent"
    },
    "nexus.vision.ksampler": {
        "latent_image": "latent",
        "positive": "positive",
        "negative": "negative",
        "model": "model"
    },
    "nexus.vision.save_image": {
        "image": "images",
        "samples": "images"
    }
}


def resolve_port(node_id: str, port_name: str) -> str:
    """Resolve UI port name to backend canonical port name."""
    # Handle nexus prefix for tool lookup
    canonical_id = node_id
    if node_id.startswith("vision.") and not node_id.startswith("nexus."):
        canonical_id = f"nexus.{node_id}"
    
    # Check aliases for the specific node type
    if canonical_id in PORT_ALIASES:
        return PORT_ALIASES[canonical_id].get(port_name, port_name)
    if node_id in PORT_ALIASES:
        return PORT_ALIASES[node_id].get(port_name, port_name)
        
    # Generic aliases
    GENERIC_ALIASES = {
        "images": "samples",
        "latent": "latent_image",
        "latent_image": "latent",
        "conditioning": "positive",
        "samples": "latent"
    }
    return GENERIC_ALIASES.get(port_name, port_name)


class QueueEventBackend:
    def __init__(self, queue: asyncio.Queue, loop: asyncio.AbstractEventLoop = None):
        self.queue = queue
        self.loop = loop or asyncio.get_event_loop()
        logger.info("[QueueEventBackend] Created with queue")

    def emit(self, event):
        try:
            data = event.to_dict() if hasattr(event, "to_dict") else event
            event_name = event.event_type.value if hasattr(event, 'event_type') else 'unknown'
            
            # Enhanced Tracing: Log failures with full data
            if event_name == "tool.execution.failed":
                logger.error(f"[QueueEventBackend] TOOL FAILURE: {data}")
            elif event_name == "workflow.failed":
                logger.error(f"[QueueEventBackend] WORKFLOW FAILURE: {data}")
            else:
                print(f"[QueueEventBackend] Emitting: {event_name}")
                
            self.loop.call_soon_threadsafe(
                lambda: self.queue.put_nowait(data)
            )
        except Exception as e:
            print(f"[QueueEventBackend] Emit error: {e}")

    def flush(self):
        pass

    def close(self):
        pass


@router.get("/")
def list_workflows():
    return {"data": [], "message": "No workflows"}


@router.post("/run-stream")
async def run_workflow_stream(
    nodes: List[Dict[str, Any]] = [],
    edges: List[Dict[str, Any]] = [],
    inputs: Dict[str, Any] = {},
):
    logger.info(
        f"[Workflow] run-stream called with {len(nodes)} nodes, {len(edges)} edges"
    )

    loop = asyncio.get_event_loop()
    queue = asyncio.Queue()

    from common_lib.modules.workflows.standard.observability import EventTracer
    from common_lib.modules.workflows.standard.execution.core import ExecutionEngine
    from common_lib.modules.workflows.standard.execution.executor import GraphExecutor
    from common_lib.modules.workflows.standard.execution.context import ExecutionContext

    from common_lib.modules.workflows.standard.observability.backends import SQLAlchemyBackend

    tracer = EventTracer()
    tracer.add_backend(QueueEventBackend(queue, loop))
    tracer.add_backend(SQLAlchemyBackend())

    # Build state map
    state_map = {}
    for n in nodes:
        if not isinstance(n, dict):
            continue
        node_id = n.get("id")
        if not node_id:
            continue
        from common_lib.modules.workflows.standard.execution.primitives import State

        tool_id = n.get("toolId", n.get("type", "unknown"))
        if tool_id.startswith("vision.") and not tool_id.startswith("nexus."):
            tool_id = f"nexus.{tool_id}"
            
        s = State(
            id=node_id,
            tool_id=tool_id,
            static_inputs=n.get("properties", {}),
        )
        state_map[node_id] = s
        logger.info(f"  Created state: {node_id} -> {s.tool_id}")

    if not state_map:
        return StreamingResponse(
            iter(
                [
                    f"data: {json.dumps({'event_type': 'workflow.failed', 'error': 'No valid nodes'})}\n\n"
                ]
            ),
            media_type="text/event-stream",
        )

    # Build graph
    from common_lib.modules.workflows.standard.execution.primitives import (
        Graph,
        Transition,
    )

    start_id = list(state_map.keys())[0]
    graph = Graph(id=f"wf_{id(nodes)}", name="Workflow", start_state_id=start_id)
    for s in state_map.values():
        graph.add_state(s)
    logger.info(f"[Workflow] Graph built with {len(graph.states)} states")

    # Add transitions
    for e in edges:
        if isinstance(e, dict):
            source = e.get("from") or e.get("source")
            target = e.get("to") or e.get("target")
            if source in state_map and target in state_map:
                state_map[source].transitions.append(Transition(to_state_id=target))

    # Build edge map with port resolution
    edge_map = {}
    for e in edges:
        source = e.get("from") or e.get("source")
        target = e.get("to") or e.get("target")
        if source and target:
            source_node = state_map.get(source)
            target_node = state_map.get(target)
            
            from_port_raw = e.get("fromPort", "output")
            to_port_raw = e.get("toPort", "input")
            
            from_port = resolve_port(source_node.tool_id if source_node else "", from_port_raw)
            to_port = resolve_port(target_node.tool_id if target_node else "", to_port_raw)
            
            if source not in edge_map:
                edge_map[source] = {}
            if from_port not in edge_map[source]:
                edge_map[source][from_port] = []
            edge_map[source][from_port].append((target, to_port))
    logger.info(f"[Workflow] Edge map: {edge_map}")

    # Setup execution
    context = ExecutionContext(trace_id=str(uuid.uuid4()), agent_id="workflow", role="executor")
    
    try:
        from common_lib.modules.orchestration.agent_loader import get_engine_manager
        from common_lib.modules.workflows.standard.observability.events import WorkflowEvent, EventType



        em = get_engine_manager()
        logger.info(f"[Workflow] Engine manager: {em}")
        if em and em.registry_svc:
            registry = em.registry_svc
        else:
            import os
            from common_lib.modules.core_infrastructure.registry.tool_registry import (
                RegistryService,
            )

            file_path = os.path.abspath(__file__)
            # index.py -> routes -> workflows -> modules -> app -> Backend
            backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(file_path)))))
            monorepo_root = os.path.dirname(backend_dir)
            common_lib_root = os.path.join(monorepo_root, "Python Libs", "common_lib")
            
            tools_dir = os.path.join(
                common_lib_root, "src", "common_lib", "templates", "tools"
            )
            registry = RegistryService()
            if os.path.exists(tools_dir):
                registry.load_from_directory(tools_dir)
            logger.info(
                f"[Workflow] Created fallback registry with tools from: {tools_dir}"
            )
        logger.info(f"[Workflow] Registry: {registry}")
    except Exception as e:
        logger.warning(f"[Workflow] Could not get registry: {e}")
        import traceback

        logger.warning(f"[Workflow] Traceback: {traceback.format_exc()}")
        from common_lib.modules.core_infrastructure.registry.tool_registry import (
            RegistryService,
        )

        registry = RegistryService()

    # Topological sort for execution order
    execution_order = []
    try:
        visited = set()
        temp_visited = set()

        def visit(n_id):
            if n_id in temp_visited:
                return # Cycle detected, but we'll let the executor handle it or just break
            if n_id not in visited:
                temp_visited.add(n_id)
                # Find all neighbors (targets of this node)
                neighbors = []
                for e in edges:
                    if (e.get("from") == n_id or e.get("source") == n_id):
                        target = e.get("to") or e.get("target")
                        if target:
                            neighbors.append(target)
                for m in neighbors:
                    visit(m)
                temp_visited.remove(n_id)
                visited.add(n_id)
                execution_order.insert(0, n_id)

        # Start from all nodes to ensure disconnected components are included
        for n in nodes:
            if n.get("id") not in visited:
                visit(n.get("id"))
        
        graph.execution_order = execution_order
        logger.info(f"[Workflow] Computed execution order: {execution_order}")
    except Exception as e:
        logger.warning(f"[Workflow] Topological sort failed: {e}")

    engine = ExecutionEngine(registry=registry, tracer=tracer)
    executor = GraphExecutor(engine, tracer, edge_map)

    # Actually run the executor
    async def run_executor():
        try:
            logger.info(f"[Workflow] Starting execution of graph {graph.id} in background thread")
            # GraphExecutor.execute is synchronous, so run it in a thread
            result = await asyncio.to_thread(executor.execute, graph, inputs, context)
            

            logger.info(f"[Workflow] Execution completed for graph {graph.id}")
        except Exception as e:
            logger.error(f"[Workflow] Execution failed: {e}")
            logger.error(traceback.format_exc())



    # Start execution in background
    asyncio.create_task(run_executor())

    async def event_generator():
        logger.info("[Workflow] Starting event stream")
        try:
            while True:
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {json.dumps(data)}\n\n"
                    
                    event_type = data.get("event_type")
                    if event_type in ["workflow.completed", "workflow.failed"]:
                        logger.info(f"[Workflow] Stream closing on terminal event: {event_type}")
                        break
                except asyncio.TimeoutError:
                    # Keepalive
                    yield ": keepalive\n\n"
        except Exception as e:
            logger.error(f"[Workflow] Stream error: {e}")
        finally:
            logger.info("[Workflow] Event stream closed")

    return StreamingResponse(event_generator(), media_type="text/event-stream")
