"""Workflow management API — thin router delegating to WorkflowService in common_lib."""

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, AsyncGenerator
from fastapi import APIRouter, Depends, HTTPException, Body
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from common_lib.modules.jobs.artifacts import job_dir
from common_lib.modules.jobs.models import JobRecord
from common_lib.modules.jobs.service import get_job_service

from app.modules.jobs.actor import capture_job_actor, owned_job_service
from common_lib.modules.workflows.job_executors import (
    GRAPH_RUN_KIND,
    ensure_workflow_executors_registered,
)
from common_lib.modules.workflows.service import workflow_service

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(capture_job_actor)])

TERMINAL_STATUSES = ("completed", "failed", "cancelled")
GRAPH_RUN_TIMEOUT = 600


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


class TemplateGenerationRequest(BaseModel):
    prompt: str
    category: str
    context: Optional[Dict[str, Any]] = None
    options: Optional[Dict[str, Any]] = None


@router.get("/")
def list_workflows(
    search: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
):
    return workflow_service.list_workflows(
        search=search, category=category, limit=limit, offset=offset
    )


@router.post("/", status_code=201)
def create_workflow(req: WorkflowCreateRequest):
    result = workflow_service.create_workflow(
        name=req.name,
        description=req.description,
        category=req.category,
        engine=req.engine,
        tags=req.tags,
        author=req.author,
        status=req.status,
        parameters=req.parameters,
        nodes=req.nodes,
        edges=req.edges,
    )
    return {"data": result, "message": "Workflow created"}


@router.get("/{workflow_id}")
def get_workflow(workflow_id: str):
    result = workflow_service.get_workflow(workflow_id)
    if not result:
        raise HTTPException(
            status_code=404, detail=f"Workflow not found: {workflow_id}"
        )
    return {"data": result}


@router.put("/{workflow_id}")
def update_workflow(workflow_id: str, req: WorkflowUpdateRequest):
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    result = workflow_service.update_workflow(workflow_id, updates)
    if not result:
        raise HTTPException(
            status_code=404, detail=f"Workflow not found: {workflow_id}"
        )
    return {"data": result, "message": "Workflow updated"}


@router.delete("/{workflow_id}", status_code=204)
def delete_workflow(workflow_id: str):
    if not workflow_service.delete_workflow(workflow_id):
        raise HTTPException(
            status_code=404, detail=f"Workflow not found: {workflow_id}"
        )


@router.post("/{workflow_id}/run")
async def run_workflow(workflow_id: str, inputs: Dict[str, Any] = {}):
    """Run a stored workflow as a background job; stream job-backed SSE.

    Execution runs on a jobs worker thread (off the event loop). The SSE
    channel carries coarse ``progress`` events backed by job progress plus a
    terminal ``workflow.completed``/``workflow.failed`` event with outputs.
    """
    workflow = workflow_service.get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(
            status_code=404, detail=f"Workflow not found: {workflow_id}"
        )
    nodes = workflow.get("nodes", [])
    edges = workflow.get("edges", [])
    if not nodes:
        raise HTTPException(status_code=400, detail="Workflow has no nodes")
    record: JobRecord = _submit_graph_run(nodes=nodes, edges=edges, inputs=inputs or {})

    async def sse_wrapper() -> AsyncGenerator[str, None]:
        async for chunk in _poll_graph_job_sse(record.id):
            yield chunk

    return StreamingResponse(sse_wrapper(), media_type="text/event-stream")


@router.post("/submit", status_code=202)
def submit_graph_run(
    nodes: List[Dict[str, Any]] = [],
    edges: List[Dict[str, Any]] = [],
    inputs: Dict[str, Any] = {},
) -> Dict[str, Any]:
    """Submit a node/edge graph run as a background job; 202 {job_id}."""
    record: JobRecord = _submit_graph_run(
        nodes=nodes, edges=edges or [], inputs=inputs or {}
    )
    return {"job_id": record.id, "status": record.status}


@router.get("/job/{job_id}")
def graph_job_status(job_id: str) -> Dict[str, Any]:
    """Return graph-run job status, progress, result_refs, outputs (when done)."""
    record: JobRecord | None = get_job_service().get(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    return {"data": _graph_job_payload(record)}


def _submit_graph_run(
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]] | None,
    inputs: Dict[str, Any],
) -> JobRecord:
    """Register executors (idempotent) and submit a graph-run job."""
    ensure_workflow_executors_registered()
    return owned_job_service().submit(
        kind=GRAPH_RUN_KIND,
        params={
            "nodes": nodes,
            "edges": edges or [],
            "inputs": inputs or {},
            "outputs_def": {},
            "halt_on_failure": False,
        },
        timeout=float(GRAPH_RUN_TIMEOUT),
    )


def _read_graph_result(job_id: str) -> Optional[Dict[str, Any]]:
    """Read the persisted result.json artifact for a graph-run job."""
    candidate: Path = job_dir(job_id) / "result.json"
    try:
        if candidate.is_file():
            raw: Any = json.loads(candidate.read_text(encoding="utf-8"))
            return raw if isinstance(raw, dict) else {"value": raw}
    except Exception as exc:  # noqa: BLE001
        logger.warning("workflows: could not read result for job %s: %s", job_id, exc)
    return None


def _graph_job_payload(record: JobRecord) -> Dict[str, Any]:
    """Serialize a graph-run job record plus outputs (when completed)."""
    payload: Dict[str, Any] = record.to_dict()
    if record.status == "completed":
        result: Optional[Dict[str, Any]] = _read_graph_result(record.id)
        if result is not None:
            payload["result"] = result
    return payload


async def _poll_graph_job_sse(job_id: str) -> AsyncGenerator[str, None]:
    """Yield SSE progress events backed by graph-run job progress."""
    deadline: float = time.time() + float(GRAPH_RUN_TIMEOUT) + 30.0
    last_progress: float = -1.0
    yield f"data: {json.dumps({'event_type': 'workflow.started', 'job_id': job_id})}\n\n"
    while True:
        record: JobRecord | None = get_job_service().get(job_id)
        if record is None:
            yield f"data: {json.dumps({'event_type': 'workflow.failed', 'job_id': job_id, 'error': 'job not found'})}\n\n"
            return
        if record.progress != last_progress:
            last_progress = record.progress
            yield f"data: {json.dumps({'event_type': 'progress', 'job_id': job_id, 'percent': record.progress, 'status': record.status})}\n\n"
        if record.status in TERMINAL_STATUSES:
            if record.status == "completed":
                result: Optional[Dict[str, Any]] = _read_graph_result(job_id)
                final: Dict[str, Any] = {
                    "event_type": "workflow.completed",
                    "job_id": job_id,
                    "outputs": (result or {}).get("outputs", {}),
                }
                yield f"data: {json.dumps(final, default=str)}\n\n"
            else:
                yield f"data: {json.dumps({'event_type': 'workflow.failed', 'job_id': job_id, 'error': record.error or record.status})}\n\n"
            return
        if time.time() > deadline:
            yield f"data: {json.dumps({'event_type': 'workflow.failed', 'job_id': job_id, 'error': 'progress poll timed out'})}\n\n"
            return
        await asyncio.sleep(0.5)


@router.post("/generate-template")
async def generate_template(request: TemplateGenerationRequest):
    return workflow_service.generate_template(
        prompt=request.prompt,
        category=request.category,
        context=request.context,
        options=request.options,
    )


@router.post("/run-stream")
async def run_workflow_stream(
    nodes: List[Dict[str, Any]] = [],
    edges: List[Dict[str, Any]] = None,
    inputs: Dict[str, Any] = {},
):
    """Submit an ad-hoc graph run as a background job; stream job-backed SSE."""
    record: JobRecord = _submit_graph_run(
        nodes=nodes, edges=edges or [], inputs=inputs or {}
    )

    async def sse_wrapper() -> AsyncGenerator[str, None]:
        async for chunk in _poll_graph_job_sse(record.id):
            yield chunk

    return StreamingResponse(sse_wrapper(), media_type="text/event-stream")
