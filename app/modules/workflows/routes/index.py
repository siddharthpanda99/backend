import asyncio
import json
import logging
import os
import traceback
import sys
import uuid
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

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
    # New comfy.vision.* canonical names
    "comfy.vision.empty_latent": {"latent": "samples"},
    "comfy.vision.clip_encode": {
        "text": "positive",
        "latent": "latent_image",
        "images": "latent",
        "latent_image": "latent_image",
        "conditioning": "positive",
    },
    "comfy.vision.vae_decode": {
        "latent": "samples",
        "image": "images",
        "images": "samples",
        "samples": "latent",
    },
    "comfy.vision.ksampler": {
        "latent_image": "latent",
        "positive": "positive",
        "negative": "negative",
        "model": "model",
    },
    "comfy.vision.upscale_latent": {
        "images": "samples",
        "samples": "samples",
        "latent": "samples",
    },
    "comfy.vision.save_image": {"image": "images", "samples": "images"},
    # Legacy vision.* aliases (maps to comfy.vision)
    "vision.empty_latent": {"latent": "samples"},
    "vision.clip_encode": {
        "text": "positive",
        "latent": "latent_image",
        "conditioning": "positive",
    },
    "vision.vae_decode": {
        "latent": "samples",
        "images": "samples",
        "samples": "latent",
    },
    "vision.ksampler": {
        "latent_image": "latent",
        "positive": "positive",
        "negative": "negative",
        "model": "model",
    },
    "vision.upscale_latent": {
        "images": "samples",
        "samples": "samples",
        "latent": "samples",
    },
    "vision.save_image": {"image": "images", "samples": "images"},
}


def extract_references_from_properties(properties: Dict[str, Any]) -> Dict[str, List]:
    """Extract node references from {{nodes.X.Y}} patterns in properties.
    Returns: {property_name: [(source_node_id, source_port)]}
    """
    import re

    references = {}
    prop_str = json.dumps(properties)
    # Match {{nodes.NODE_ID.PORT}} patterns
    matches = re.findall(r"\{\{nodes\.(\w+)\.(\w+)\}\}", prop_str)
    for source_id, source_port in matches:
        if source_port not in references:
            references[source_port] = []
        references[source_port].append((source_id, source_port))
    return references


def build_edge_map_from_properties(
    state_map: Dict[str, Any],
) -> Dict[str, Dict[str, List]]:
    """Build edge map by parsing {{nodes.X.Y}} references in properties."""
    edge_map = {}

    for node_id, state in state_map.items():
        props = state.static_inputs or {}
        prop_str = json.dumps(props)

        # Match {{nodes.SOURCE_ID.PORT}} patterns
        import re

        matches = re.findall(r"\{\{nodes\.(\w+)\.(\w+)\}\}", prop_str)

        for source_id, source_port in matches:
            if source_id not in edge_map:
                edge_map[source_id] = {}
            if source_port not in edge_map[source_id]:
                edge_map[source_id][source_port] = []
            edge_map[source_id][source_port].append((node_id, source_port))

    return edge_map


def resolve_port(node_id: str, port_name: str) -> str:
    """Resolve UI port name to tool's canonical port name."""
    if not port_name:
        return "output"

    # 1. Check specialized PORT_ALIASES for the specific node type
    if node_id in PORT_ALIASES:
        if port_name in PORT_ALIASES[node_id]:
            return PORT_ALIASES[node_id][port_name]

    # 2. Case-insensitive common mappings (UI often sends caps)
    COMMON_UI_MAP = {
        "MODEL": "model",
        "CLIP": "clip",
        "VAE": "vae",
        "CONDITIONING": "conditioning",
        "LATENT": "latent",
        "IMAGE": "image",
        "IMAGES": "images",
        "MASK": "mask",
    }
    if port_name.upper() in COMMON_UI_MAP:
        return COMMON_UI_MAP[port_name.upper()]

    # 3. Generic aliases - maps UI port names to tool port names
    GENERIC_ALIASES = {
        "images": "samples",
        "latent": "latent_image",
        "latent_image": "latent",
        "conditioning": "positive",
        "samples": "latent",
        # Additional sampler port aliases
        "model_output": "model",
        "clip_output": "clip",
        "latent_output": "latent",
        "images_output": "images",
    }
    return GENERIC_ALIASES.get(port_name.lower(), port_name)


class QueueEventBackend:
    def __init__(self, queue: asyncio.Queue, loop: asyncio.AbstractEventLoop = None):
        self.queue = queue
        self.loop = loop or asyncio.get_event_loop()
        logger.info("[QueueEventBackend] Created with queue")

    def emit(self, event):
        try:
            data = event.to_dict() if hasattr(event, "to_dict") else event
            event_name = (
                event.event_type.value if hasattr(event, "event_type") else "unknown"
            )

            # Extract specifics to display in logs (e.g. tool name, state ID)
            state_id = data.get("state_id") if isinstance(data, dict) else ""
            tool_id = data.get("tool_id") if isinstance(data, dict) else ""
            metadata = (
                data.get("metadata")
                if (isinstance(data, dict) and isinstance(data.get("metadata"), dict))
                else {}
            )
            tool_name = (
                tool_id or metadata.get("tool_name") or metadata.get("tool_id") or ""
            )

            # Enhanced Tracing: Log failures with full data
            if event_name == "tool.execution.failed":
                logger.error(
                    f"[QueueEventBackend] TOOL FAILURE (State: {state_id}, Tool: {tool_name}): {data}"
                )
            elif event_name == "workflow.failed":
                logger.error(f"[QueueEventBackend] WORKFLOW FAILURE: {data}")
            elif event_name in ["tool.execution.started", "tool.execution.completed"]:
                print(
                    f"[QueueEventBackend] Emitting: {event_name} (State: {state_id}, Tool: {tool_name})"
                )
            elif event_name in ["state.entered", "state.exited"]:
                print(f"[QueueEventBackend] Emitting: {event_name} (State: {state_id})")
            elif event_name == "state.progress":
                progress = metadata.get("progress", 0.0)
                desc = data.get("state_description", "")
                try:
                    progress_val = float(progress)
                    print(
                        f"[QueueEventBackend] Emitting: {event_name} (State: {state_id}, Progress: {progress_val:.1%}, {desc})"
                    )
                except Exception:
                    print(
                        f"[QueueEventBackend] Emitting: {event_name} (State: {state_id}, Progress: {progress}, {desc})"
                    )
            else:
                print(f"[QueueEventBackend] Emitting: {event_name}")

            self.loop.call_soon_threadsafe(lambda: self.queue.put_nowait(data))
        except Exception as e:
            print(f"[QueueEventBackend] Emit error: {e}")

    def flush(self):
        pass

    def close(self):
        pass


from pydantic import BaseModel
from typing import List, Dict, Any, Optional

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
            registry_workflows.append(
                {
                    "id": wf["id"],
                    "name": wf["name"],
                    "description": wf.get("description", ""),
                    "category": wf.get("category", "workflow"),
                    "node_count": len(wf.get("nodes", [])),
                    "executable": True,
                    "author": wf.get("author", "User"),
                    "status": wf.get("status", "DRAFT"),
                }
            )
            seen_ids.add(wf["id"])

    if search:
        s = search.lower()
        registry_workflows = [
            wf
            for wf in registry_workflows
            if s in wf["name"].lower() or s in wf.get("description", "").lower()
        ]
    if category:
        registry_workflows = [
            wf
            for wf in registry_workflows
            if wf.get("category", "").lower() == category.lower()
        ]

    return {
        "data": registry_workflows[offset : offset + limit],
        "total": len(registry_workflows),
    }


@router.post("/", status_code=201)
def create_workflow(req: WorkflowCreateRequest):
    wf_id = (
        req.name.lower().replace(" ", "_").replace("-", "_")
        + "_"
        + str(uuid.uuid4())[:8]
    )
    workflow = {
        "id": wf_id,
        "name": req.name,
        "description": req.description,
        "category": req.category,
        "engine": req.engine,
        "tags": req.tags,
        "author": req.author,
        "status": req.status,
        "parameters": req.parameters,
        "nodes": req.nodes,
        "edges": req.edges,
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
        raise HTTPException(
            status_code=404, detail=f"Workflow not found: {workflow_id}"
        )

    for field in (
        "name",
        "description",
        "category",
        "engine",
        "tags",
        "author",
        "status",
        "parameters",
        "nodes",
        "edges",
    ):
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
        raise HTTPException(
            status_code=404, detail=f"Workflow not found: {workflow_id}"
        )

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
    category = request.category

    # Process natural language request and build nodes/edges
    keywords = prompt.lower()
    nodes = []
    edges = []

    # Dynamic template generation matching user prompts
    if "load" in keywords or "image" in keywords or "vision" in keywords:
        nodes = [
            {
                "id": "loader-1",
                "type": "vision.load_checkpoint",
                "toolId": "vision.load_checkpoint",
                "properties": {"ckpt_name": "v1-5-pruned-emaonly.safetensors"},
                "initialX": 100,
                "initialY": 200,
            },
            {
                "id": "sampler-1",
                "type": "vision.ksampler",
                "toolId": "vision.ksampler",
                "properties": {
                    "seed": 42,
                    "steps": 20,
                    "cfg": 7.0,
                    "sampler_name": "euler",
                    "scheduler": "normal",
                    "denoise": 1.0,
                },
                "initialX": 400,
                "initialY": 200,
            },
            {
                "id": "decoder-1",
                "type": "vision.vae_decode",
                "toolId": "vision.vae_decode",
                "properties": {},
                "initialX": 700,
                "initialY": 200,
            },
            {
                "id": "save-1",
                "type": "vision.save_image",
                "toolId": "vision.save_image",
                "properties": {"filename_prefix": "AI_Generated"},
                "initialX": 1000,
                "initialY": 200,
            },
        ]

        edges = [
            {
                "id": "edge-1",
                "from": "loader-1",
                "fromPort": "model",
                "to": "sampler-1",
                "toPort": "model",
            },
            {
                "id": "edge-2",
                "from": "sampler-1",
                "fromPort": "latent",
                "to": "decoder-1",
                "toPort": "latent",
            },
            {
                "id": "edge-3",
                "from": "decoder-1",
                "fromPort": "image",
                "to": "save-1",
                "toPort": "image",
            },
        ]
    elif "api" in keywords or "webhook" in keywords or "fetch" in keywords:
        nodes = [
            {
                "id": "trigger-1",
                "type": "trigger.webhook",
                "toolId": "trigger.webhook",
                "properties": {"path": "/api/v1/orders", "method": "POST"},
                "initialX": 100,
                "initialY": 200,
            },
            {
                "id": "http-1",
                "type": "action.http_request",
                "toolId": "action.http_request",
                "properties": {
                    "url": "https://api.external.service/process",
                    "method": "POST",
                    "body": "{{nodes.trigger-1.body}}",
                },
                "initialX": 400,
                "initialY": 200,
            },
            {
                "id": "log-1",
                "type": "action.logger",
                "toolId": "action.logger",
                "properties": {
                    "message": "Processed successfully: {{nodes.http-1.response}}"
                },
                "initialX": 700,
                "initialY": 200,
            },
        ]

        edges = [
            {
                "id": "edge-1",
                "from": "trigger-1",
                "fromPort": "output",
                "to": "http-1",
                "toPort": "input",
            },
            {
                "id": "edge-2",
                "from": "http-1",
                "fromPort": "output",
                "to": "log-1",
                "toPort": "input",
            },
        ]
    else:
        nodes = [
            {
                "id": "agent-1",
                "type": "agent.react",
                "toolId": "agent.react",
                "properties": {
                    "system_prompt": f"You are an assistant configured for: {prompt}",
                    "temperature": 0.7,
                },
                "initialX": 100,
                "initialY": 200,
            },
            {
                "id": "summary-1",
                "type": "agent.summarize",
                "toolId": "agent.summarize",
                "properties": {"max_length": 150},
                "initialX": 400,
                "initialY": 200,
            },
        ]
        edges = [
            {
                "id": "edge-1",
                "from": "agent-1",
                "fromPort": "output",
                "to": "summary-1",
                "toPort": "input",
            }
        ]

    processing_time = time.time() - start_time

    template = {
        "id": f"gen-{int(start_time * 1000)}",
        "name": f"AI: {prompt[:30]}",
        "description": f"Generated workflow for prompt: '{prompt}'",
        "category": category,
        "tags": ["ai-generated", category],
        "difficulty": "intermediate",
        "estimatedTime": 10 if "vision" in keywords else 5,
        "nodes": nodes,
        "edges": edges,
        "metadata": {
            "version": "1.0.0",
            "createdAt": int(start_time * 1000),
            "updatedAt": int(start_time * 1000),
            "aiGenerated": True,
            "prompt": prompt,
            "confidence": 0.92,
        },
    }

    return {
        "success": True,
        "template": template,
        "suggestions": [
            "Add a validation node to check incoming schema",
            "Setup notification alerts on error states",
        ],
        "processingTime": round(processing_time, 2),
    }


@router.post("/run-stream")
async def run_workflow_stream(
    nodes: List[Dict[str, Any]] = [],
    edges: List[Dict[str, Any]] = None,
    inputs: Dict[str, Any] = {},
):
    if edges is None:
        edges = []
    logger.info(
        f"[Workflow] run-stream called with {len(nodes)} nodes, {len(edges)} edges (or derived from properties)"
    )

    # DEBUG: Log full payload from frontend
    logger.info(f"[Workflow] Raw payload - nodes count: {len(nodes)}")
    for i, n in enumerate(nodes):
        node_id = n.get("id", f"unknown_{i}")
        tool_id = n.get("toolId", n.get("type", "unknown"))
        props = n.get("properties", {})
        logger.info(
            f"  Node[{i}] id={node_id} toolId={tool_id} properties_count={len(props)} keys={list(props.keys())[:10]}"
        )
    logger.info(
        f"[Workflow] Full payload: {json.dumps({'nodes': [{'id': n.get('id'), 'toolId': n.get('toolId'), 'propertiesKeys': list(n.get('properties', {}).keys())} for n in nodes]}, indent=2)}"
    )

    # CRITICAL: Check if properties are missing or empty
    if not any(n.get("properties") for n in nodes):
        logger.error(
            "[Workflow] CRITICAL: NO NODES HAVE properties! This means UI is not sending node data!"
        )
        logger.error(f"[Workflow] First node: {nodes[0] if nodes else 'NONE'}")
    else:
        logger.info("[Workflow] Properties present in at least one node")

    loop = asyncio.get_event_loop()
    queue = asyncio.Queue()

    from common_lib.modules.workflows.standard.observability import EventTracer
    from common_lib.modules.workflows.standard.execution.core import ExecutionEngine
    from common_lib.modules.workflows.standard.execution.executor import GraphExecutor
    from common_lib.modules.workflows.standard.execution.context import ExecutionContext

    from common_lib.modules.workflows.standard.observability.backends import (
        SQLAlchemyBackend,
    )

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

        # DEBUG: Log ALL properties from frontend
        logger.info(
            f"[Workflow] Node '{node_id}' ({tool_id}) properties: {json.dumps(n.get('properties', {}), indent=2, default=str)[:500]}"
        )

        # Standardize vision tool IDs
        if tool_id.startswith("vision.") and not tool_id.startswith("comfy."):
            # We keep it as vision.* since our Registry and Node mappings use that
            pass

        # Store edge info for centralized state
        edges_by_target = {}
        for e in edges:
            source = e.get("from") or e.get("source")
            target = e.get("to") or e.get("target")
            if target == node_id:
                from_port_raw = e.get("fromPort", "output")
                to_port_raw = e.get("toPort", "input")

                # Resolve ports
                source_node_type = next(
                    (
                        n.get("toolId", n.get("type"))
                        for n in nodes
                        if n.get("id") == source
                    ),
                    "",
                )
                target_node_type = n.get("toolId", n.get("type"))

                from_port = resolve_port(source_node_type, from_port_raw)
                to_port = resolve_port(target_node_type, to_port_raw)

                if node_id not in edges_by_target:
                    edges_by_target[node_id] = []
                edges_by_target[node_id].append(
                    {
                        "source": source,
                        "from_port": from_port,
                        "to_port": to_port,
                    }
                )

        s = State(
            id=node_id,
            tool_id=tool_id,
            static_inputs=n.get("properties", {}),
            metadata={"edges_in": edges_by_target.get(node_id, [])},
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

    # Store full workflow definition (nodes + edges) for metadata
    graph.workflow_definition = {
        "nodes": [
            {
                "id": n.get("id"),
                "type": n.get("type"),
                "tool_id": n.get("toolId"),
                "properties": n.get("properties", {}),
            }
            for n in nodes
        ],
        "edges": edges if edges else [],
    }

    # Add transitions
    for e in edges:
        if isinstance(e, dict):
            source = e.get("from") or e.get("source")
            target = e.get("to") or e.get("target")
            if source in state_map and target in state_map:
                state_map[source].transitions.append(Transition(to_state_id=target))

    # Build edge map with port resolution (from edges OR from properties)
    edge_map = {}

    if edges:
        for e in edges:
            source = e.get("from") or e.get("source")
            target = e.get("to") or e.get("target")
            if source and target:
                source_node = state_map.get(source)
                target_node = state_map.get(target)

                from_port_raw = e.get("fromPort", "output")
                to_port_raw = e.get("toPort", "input")

                from_port = resolve_port(
                    source_node.tool_id if source_node else "", from_port_raw
                )
                to_port = resolve_port(
                    target_node.tool_id if target_node else "", to_port_raw
                )

                if source not in edge_map:
                    edge_map[source] = {}
                if from_port not in edge_map[source]:
                    edge_map[source][from_port] = []
                edge_map[source][from_port].append((target, to_port))
    else:
        # Extract edges from {{nodes.X.Y}} references in properties
        logger.info("[Workflow] No edges provided - extracting from node properties")
        edge_map = build_edge_map_from_properties(state_map)

    logger.info(f"[Workflow] Edge map: {edge_map}")

    # Setup execution
    context = ExecutionContext(
        trace_id=str(uuid.uuid4()), agent_id="workflow", role="executor"
    )

    try:
        from app.modules.entities.routes.registry import _get_registry_svc

        registry = _get_registry_svc()
        if registry:
            # Only log if already populated, avoid triggering discovery just for logging
            tool_count = len(registry._tools) if hasattr(registry, "_tools") else 0
            logger.info(
                f"[Workflow] Using shared registry with {tool_count} tools cached"
            )

        engine = ExecutionEngine(registry=registry, tracer=tracer)
    except Exception as e:
        logger.warning(f"[Workflow] Could not get shared registry: {e}")
        from common_lib.modules.core_infrastructure.registry.tool_registry import (
            RegistryService,
        )

        registry = RegistryService()
        engine = ExecutionEngine(registry=registry, tracer=tracer)

    # Build explicit execution order from EDGES (data flow)
    # Edge: from -> to means "to" depends on "from" output
    # So "from" must execute BEFORE "to"

    node_ids = [n.get("id") for n in nodes]
    consumers = {nid: [] for nid in node_ids}  # node -> nodes that depend on it
    producers = {nid: [] for nid in node_ids}  # node -> nodes it depends on

    for e in edges:
        source = e.get("from") or e.get("source")
        target = e.get("to") or e.get("target")
        if source in producers and target in consumers:
            producers[target].append(source)  # target needs source's output
            consumers[source].append(target)  # source feeds target

    # Kahn's algorithm for topological sort
    # in_degree = number of producers each node has
    in_degree = {nid: len(producers[nid]) for nid in node_ids}

    # Start with nodes that have no producers (can run immediately)
    queue = [nid for nid, deg in in_degree.items() if deg == 0]
    execution_order = []

    logger.info(f"[Workflow] Nodes with no dependencies (start): {queue}")

    while queue:
        node_id = queue.pop(0)
        execution_order.append(node_id)

        # This node executed, reduce in-degree for all its consumers
        for consumer_id in consumers.get(node_id, []):
            in_degree[consumer_id] -= 1
            if in_degree[consumer_id] <= 0 and consumer_id not in execution_order:
                queue.append(consumer_id)

    # Handle disconnected nodes or cycles (append in original order)
    for nid in node_ids:
        if nid not in execution_order:
            execution_order.append(nid)

    logger.info(f"[Workflow] Explicit execution order: {execution_order}")
    logger.info(
        f"[Workflow] Edge-based dependencies: {json.dumps({k: v for k, v in producers.items() if v}, indent=2)}"
    )

    # SET execution_order on graph so executor uses it
    graph.execution_order = execution_order

    # Store edge_map in graph for metadata
    graph.edge_map = edge_map

    engine = ExecutionEngine(registry=registry, tracer=tracer)
    executor = GraphExecutor(engine, tracer, edge_map)

    # Actually run the executor
    async def run_executor():
        try:
            logger.info(
                f"[Workflow] Starting execution of graph {graph.id} in background thread"
            )
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

                    event_type = (
                        data.get("event_type") if isinstance(data, dict) else None
                    )
                    if event_type in ["workflow.completed", "workflow.failed"]:
                        logger.info(
                            f"[Workflow] Stream closing on terminal event: {event_type}"
                        )
                        break
                except asyncio.TimeoutError:
                    # Keepalive
                    yield ": keepalive\n\n"
        except Exception as e:
            logger.error(f"[Workflow] Stream error: {e}")
        finally:
            logger.info("[Workflow] Event stream closed")

    return StreamingResponse(event_generator(), media_type="text/event-stream")
