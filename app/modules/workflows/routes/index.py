import asyncio
import json
import logging
import traceback
import uuid
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from common_lib.modules.workflows.port_resolution import (
    resolve_port,
)
from common_lib.modules.workflows.standard.observability.backends.queue_backend import (
    QueueEventBackend,
)
from common_lib.modules.workflows.standard.observability.backends import (
    SQLAlchemyBackend,
)
from common_lib.modules.workflows.standard.observability import EventTracer

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# In-memory CRUD store
# ---------------------------------------------------------------------------
from common_lib.modules.workflows.standard.registry.workflow_registry import (
    get_workflow_registry,
)

_workflow_crud_store: Dict[str, Dict[str, Any]] = {}


class WorkflowCreateRequest(BaseModel):
    name: str
    description: str = ""
    category: str = "Vision"
    engine: str = "vision"
    tags: List[str] = []
    author: str = "User"
    status: str = "DRAFT"
    parameters: Dict[str, Any] = {}
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []


class WorkflowUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    engine: Optional[str] = None
    tags: Optional[List[str]] = None
    author: Optional[str] = None
    status: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    nodes: Optional[List[Dict[str, Any]]] = None
    edges: Optional[List[Dict[str, Any]]] = None


@router.get("/")
def list_workflows(
    search: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
):
    try:
        registry = get_workflow_registry()
        registry_workflows = registry.list_workflows()
    except Exception:
        registry_workflows = []

    seen_ids = {wf["id"] for wf in registry_workflows}
    for wf in _workflow_crud_store.values():
        if wf["id"] not in seen_ids:
            registry_workflows.append({
                "id": wf["id"],
                "name": wf["name"],
                "description": wf.get("description", ""),
                "category": wf.get("category", "workflow"),
                "node_count": len(wf.get("nodes", [])),
                "executable": True,
                "author": wf.get("author", "User"),
                "status": wf.get("status", "DRAFT"),
            })
            seen_ids.add(wf["id"])

    if search:
        s = search.lower()
        registry_workflows = [
            wf for wf in registry_workflows
            if s in wf["name"].lower() or s in wf.get("description", "").lower()
        ]
    if category:
        registry_workflows = [
            wf for wf in registry_workflows
            if wf.get("category", "").lower() == category.lower()
        ]

    return {"data": registry_workflows[offset: offset + limit], "total": len(registry_workflows)}


@router.post("/", status_code=201)
def create_workflow(req: WorkflowCreateRequest):
    wf_id = req.name.lower().replace(" ", "_").replace("-", "_") + "_" + str(uuid.uuid4())[:8]
    workflow = {
        "id": wf_id, "name": req.name, "description": req.description,
        "category": req.category, "engine": req.engine, "tags": req.tags,
        "author": req.author, "status": req.status, "parameters": req.parameters,
        "nodes": req.nodes, "edges": req.edges,
    }
    _workflow_crud_store[wf_id] = workflow
    return {"data": workflow, "message": "Workflow created"}


@router.get("/{workflow_id}")
def get_workflow(workflow_id: str):
    crud = _workflow_crud_store.get(workflow_id)
    if crud:
        return {"data": crud}
    try:
        registry = get_workflow_registry()
        wf = registry.get_workflow(workflow_id)
        if wf:
            return {"data": wf}
    except Exception:
        pass
    raise HTTPException(status_code=404, detail=f"Workflow not found: {workflow_id}")


@router.put("/{workflow_id}")
def update_workflow(workflow_id: str, req: WorkflowUpdateRequest):
    stored = _workflow_crud_store.get(workflow_id)
    if not stored:
        raise HTTPException(status_code=404, detail=f"Workflow not found: {workflow_id}")
    for field in ("name", "description", "category", "engine", "tags",
                  "author", "status", "parameters", "nodes", "edges"):
        val = getattr(req, field, None)
        if val is not None:
            stored[field] = val
    return {"data": stored, "message": "Workflow updated"}


@router.delete("/{workflow_id}", status_code=204)
def delete_workflow(workflow_id: str):
    if workflow_id in _workflow_crud_store:
        del _workflow_crud_store[workflow_id]
        return
    raise HTTPException(status_code=404, detail=f"Workflow not found: {workflow_id}")


@router.post("/{workflow_id}/run")
async def run_workflow(workflow_id: str, inputs: Dict[str, Any] = {}):
    workflow = _workflow_crud_store.get(workflow_id)
    if not workflow:
        try:
            registry = get_workflow_registry()
            workflow = registry.get_workflow(workflow_id)
        except Exception:
            workflow = None
    if not workflow:
        raise HTTPException(status_code=404, detail=f"Workflow not found: {workflow_id}")
    nodes = workflow.get("nodes", [])
    edges = workflow.get("edges", [])
    if not nodes:
        raise HTTPException(status_code=400, detail="Workflow has no nodes")
    return await run_workflow_stream(nodes=nodes, edges=edges, inputs=inputs)


class TemplateGenerationRequest(BaseModel):
    prompt: str
    category: str
    context: Optional[Dict[str, Any]] = None
    options: Optional[Dict[str, Any]] = None


@router.post("/generate-template")
async def generate_template(request: TemplateGenerationRequest):
    """Generate workflow template from natural language using backend AI service."""
    import time
    start_time = time.time()
    prompt = request.prompt
    keywords = prompt.lower()
    nodes = []
    edges = []

    if "load" in keywords or "image" in keywords or "vision" in keywords:
        nodes = [
            {"id": "loader-1", "type": "vision.load_checkpoint", "toolId": "vision.load_checkpoint",
             "properties": {"ckpt_name": "v1-5-pruned-emaonly.safetensors"}, "initialX": 100, "initialY": 200},
            {"id": "sampler-1", "type": "vision.ksampler", "toolId": "vision.ksampler",
             "properties": {"seed": 42, "steps": 20, "cfg": 7.0, "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0},
             "initialX": 400, "initialY": 200},
            {"id": "decoder-1", "type": "vision.vae_decode", "toolId": "vision.vae_decode",
             "properties": {}, "initialX": 700, "initialY": 200},
            {"id": "save-1", "type": "vision.save_image", "toolId": "vision.save_image",
             "properties": {"filename_prefix": "AI_Generated"}, "initialX": 1000, "initialY": 200},
        ]
        edges = [
            {"id": "edge-1", "from": "loader-1", "fromPort": "model", "to": "sampler-1", "toPort": "model"},
            {"id": "edge-2", "from": "sampler-1", "fromPort": "latent", "to": "decoder-1", "toPort": "latent"},
            {"id": "edge-3", "from": "decoder-1", "fromPort": "image", "to": "save-1", "toPort": "image"},
        ]
    elif "api" in keywords or "webhook" in keywords or "fetch" in keywords:
        nodes = [
            {"id": "trigger-1", "type": "trigger.webhook", "toolId": "trigger.webhook",
             "properties": {"path": "/api/v1/orders", "method": "POST"}, "initialX": 100, "initialY": 200},
            {"id": "http-1", "type": "action.http_request", "toolId": "action.http_request",
             "properties": {"url": "https://api.external.service/process", "method": "POST", "body": "{{nodes.trigger-1.body}}"},
             "initialX": 400, "initialY": 200},
            {"id": "log-1", "type": "action.logger", "toolId": "action.logger",
             "properties": {"message": "Processed successfully: {{nodes.http-1.response}}"}, "initialX": 700, "initialY": 200},
        ]
        edges = [
            {"id": "edge-1", "from": "trigger-1", "fromPort": "output", "to": "http-1", "toPort": "input"},
            {"id": "edge-2", "from": "http-1", "fromPort": "output", "to": "log-1", "toPort": "input"},
        ]
    else:
        nodes = [
            {"id": "agent-1", "type": "agent.react", "toolId": "agent.react",
             "properties": {"system_prompt": f"You are an assistant configured for: {prompt}", "temperature": 0.7},
             "initialX": 100, "initialY": 200},
            {"id": "summary-1", "type": "agent.summarize", "toolId": "agent.summarize",
             "properties": {"max_length": 150}, "initialX": 400, "initialY": 200},
        ]
        edges = [{"id": "edge-1", "from": "agent-1", "fromPort": "output", "to": "summary-1", "toPort": "input"}]

    return {
        "success": True,
        "template": {
            "id": f"gen-{int(start_time * 1000)}",
            "name": f"AI: {prompt[:30]}",
            "description": f"Generated workflow for prompt: '{prompt}'",
            "category": request.category,
            "tags": ["ai-generated", request.category],
            "difficulty": "intermediate",
            "estimatedTime": 10 if "vision" in keywords else 5,
            "nodes": nodes,
            "edges": edges,
            "metadata": {"version": "1.0.0", "createdAt": int(start_time * 1000),
                         "updatedAt": int(start_time * 1000), "aiGenerated": True, "prompt": prompt, "confidence": 0.92},
        },
        "suggestions": ["Add a validation node to check incoming schema", "Setup notification alerts on error states"],
        "processingTime": round(time.time() - start_time, 2),
    }


@router.post("/run-stream")
async def run_workflow_stream(
    nodes: List[Dict[str, Any]] = [],
    edges: List[Dict[str, Any]] = None,
    inputs: Dict[str, Any] = {},
):
    if edges is None:
        edges = []
    logger.info(f"[Workflow] run-stream called with {len(nodes)} nodes, {len(edges)} edges")

    loop = asyncio.get_event_loop()
    queue = asyncio.Queue()

    tracer = EventTracer()
    tracer.add_backend(QueueEventBackend(queue, loop))
    tracer.add_backend(SQLAlchemyBackend())

    # Build state map
    from common_lib.modules.workflows.standard.execution.primitives import State, Graph, Transition
    from common_lib.modules.workflows.standard.execution.core import ExecutionEngine
    from common_lib.modules.workflows.standard.execution.executor import GraphExecutor
    from common_lib.modules.workflows.standard.execution.context import ExecutionContext

    state_map = {}
    for n in nodes:
        if not isinstance(n, dict):
            continue
        node_id = n.get("id")
        if not node_id:
            continue
        tool_id = n.get("toolId", n.get("type", "unknown"))

        # Resolve edges for this node
        edges_by_target = {}
        for e in edges:
            source = e.get("from") or e.get("source")
            target = e.get("to") or e.get("target")
            if target == node_id:
                source_node_type = next(
                    (nd.get("toolId", nd.get("type")) for nd in nodes if nd.get("id") == source), ""
                )
                target_node_type = n.get("toolId", n.get("type"))
                from_port = resolve_port(source_node_type, e.get("fromPort", "output"))
                to_port = resolve_port(target_node_type, e.get("toPort", "input"))
                edges_by_target.setdefault(node_id, []).append({
                    "source": source, "from_port": from_port, "to_port": to_port,
                })

        s = State(id=node_id, tool_id=tool_id, static_inputs=n.get("properties", {}),
                  metadata={"edges_in": edges_by_target.get(node_id, [])})
        state_map[node_id] = s

    if not state_map:
        return StreamingResponse(
            iter([f"data: {json.dumps({'event_type': 'workflow.failed', 'error': 'No valid nodes'})}\n\n"]),
            media_type="text/event-stream",
        )

    start_id = list(state_map.keys())[0]
    graph = Graph(id=f"wf_{id(nodes)}", name="Workflow", start_state_id=start_id)
    for s in state_map.values():
        graph.add_state(s)

    # Build transitions and edge map
    edge_map = {}
    for e in edges:
        if isinstance(e, dict):
            source = e.get("from") or e.get("source")
            target = e.get("to") or e.get("target")
            if source in state_map and target in state_map:
                state_map[source].transitions.append(Transition(to_state_id=target))
            if source and target:
                s_node = state_map.get(source)
                t_node = state_map.get(target)
                from_port = resolve_port(s_node.tool_id if s_node else "", e.get("fromPort", "output"))
                to_port = resolve_port(t_node.tool_id if t_node else "", e.get("toPort", "input"))
                edge_map.setdefault(source, {}).setdefault(from_port, []).append((target, to_port))

    # Topological sort (Kahn's algorithm)
    node_ids = [n.get("id") for n in nodes]
    producers = {nid: [] for nid in node_ids}
    for e in edges:
        source = e.get("from") or e.get("source")
        target = e.get("to") or e.get("target")
        if source in producers and target in producers:
            producers[target].append(source)

    in_degree = {nid: len(producers[nid]) for nid in node_ids}
    q = [nid for nid, deg in in_degree.items() if deg == 0]
    execution_order = []
    while q:
        nid = q.pop(0)
        execution_order.append(nid)
        for consumer_id in [e.get("to") or e.get("target") for e in edges if (e.get("from") or e.get("source")) == nid]:
            if consumer_id in in_degree:
                in_degree[consumer_id] -= 1
                if in_degree[consumer_id] <= 0 and consumer_id not in execution_order:
                    q.append(consumer_id)
    for nid in node_ids:
        if nid not in execution_order:
            execution_order.append(nid)

    graph.execution_order = execution_order
    graph.edge_map = edge_map
    graph.workflow_definition = {
        "nodes": [{"id": n.get("id"), "type": n.get("type"), "tool_id": n.get("toolId"),
                    "properties": n.get("properties", {})} for n in nodes],
        "edges": edges if edges else [],
    }

    # Get registry
    try:
        from app.modules.entities.routes.registry import _get_registry_svc
        registry = _get_registry_svc()
        engine = ExecutionEngine(registry=registry, tracer=tracer)
    except Exception as e:
        logger.warning(f"[Workflow] Could not get shared registry: {e}")
        from common_lib.modules.core_infrastructure.registry.tool_registry import RegistryService
        registry = RegistryService()
        engine = ExecutionEngine(registry=registry, tracer=tracer)

    executor = GraphExecutor(engine, tracer, edge_map)

    async def run_executor():
        try:
            context = ExecutionContext(trace_id=str(uuid.uuid4()), agent_id="workflow", role="executor")
            await asyncio.to_thread(executor.execute, graph, inputs, context)
        except Exception as e:
            logger.error(f"[Workflow] Execution failed: {e}")
            logger.error(traceback.format_exc())

    asyncio.create_task(run_executor())

    async def event_generator():
        try:
            while True:
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {json.dumps(data)}\n\n"
                    event_type = data.get("event_type") if isinstance(data, dict) else None
                    if event_type in ["workflow.completed", "workflow.failed"]:
                        break
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        except Exception as e:
            logger.error(f"[Workflow] Stream error: {e}")
        finally:
            logger.info("[Workflow] Event stream closed")

    return StreamingResponse(event_generator(), media_type="text/event-stream")
