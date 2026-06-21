"""Workflow management API — thin router delegating to WorkflowService in common_lib."""

import logging
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Body
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from common_lib.modules.workflows.service import workflow_service

logger = logging.getLogger(__name__)

router = APIRouter()


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
    workflow = workflow_service.get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(
            status_code=404, detail=f"Workflow not found: {workflow_id}"
        )
    nodes = workflow.get("nodes", [])
    edges = workflow.get("edges", [])
    if not nodes:
        raise HTTPException(status_code=400, detail="Workflow has no nodes")
    return await workflow_service.run_workflow_stream(
        nodes=nodes, edges=edges, inputs=inputs
    )


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
    return await workflow_service.run_workflow_stream(
        nodes=nodes, edges=edges, inputs=inputs
    )
