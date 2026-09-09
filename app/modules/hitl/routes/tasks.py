"""HITL Tasks — CRUD routes for HITL task/request records.

Orphaned legacy table: hitl_tasks represents human-in-the-loop review tasks
that need to be completed by assigned reviewers.
"""

from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from common_lib.modules.integration.ports.hitl_port import get_hitl_legacy_service

router = APIRouter(prefix="/tasks", tags=["HITL — Tasks"])


class HITLTaskCreate(BaseModel):
    policy_id: str
    title: str
    description: str = ""
    status: str = Field(
        default="pending",
        description="pending | in_review | approved | rejected | escalated | deferred",
    )
    priority: int = Field(default=0, ge=-100, le=100)
    risk_score: float = Field(default=0.0, ge=0.0, le=1.0)
    assignee_id: Optional[str] = None
    assignee_type: Optional[str] = None
    context_json: Optional[dict] = None
    due_at: Optional[datetime] = None


class HITLTaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[int] = None
    risk_score: Optional[float] = None
    assignee_id: Optional[str] = None
    assignee_type: Optional[str] = None
    context_json: Optional[dict] = None
    due_at: Optional[datetime] = None


class HITLTaskResponse(BaseModel):
    id: int
    policy_id: str
    title: str
    description: str
    status: str
    priority: int
    risk_score: float
    assignee_id: Optional[str] = None
    assignee_type: Optional[str] = None
    context_json: Optional[dict] = None
    due_at: Optional[datetime] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class HITLTaskListResponse(BaseModel):
    items: list[HITLTaskResponse]
    total: int
    page: int = 1
    page_size: int = 20


def _get_service():
    svc = get_hitl_legacy_service()
    if not svc:
        raise HTTPException(status_code=503, detail="HITL legacy service unavailable")
    return svc


@router.get("", response_model=HITLTaskListResponse)
def list_tasks(
    policy_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    assignee_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    svc = _get_service()
    result = svc.list_tasks(
        policy_id=policy_id,
        status=status,
        assignee_id=assignee_id,
        page=page,
        page_size=page_size,
    )
    return HITLTaskListResponse(**result)


@router.get("/stats")
def task_stats():
    svc = _get_service()
    return svc.task_stats()


@router.get("/{task_id}", response_model=HITLTaskResponse)
def get_task(task_id: int):
    svc = _get_service()
    row = svc.get_task(task_id)
    if not row:
        raise HTTPException(status_code=404, detail="Task not found")
    return row


@router.post("", response_model=HITLTaskResponse, status_code=201)
def create_task(body: HITLTaskCreate):
    svc = _get_service()
    payload = body.model_dump(exclude_none=True)
    return svc.create_task(payload)


@router.put("/{task_id}", response_model=HITLTaskResponse)
def update_task(task_id: int, body: HITLTaskUpdate):
    svc = _get_service()
    payload = body.model_dump(exclude_unset=True)
    if not payload:
        raise HTTPException(status_code=400, detail="No fields to update")
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    row = svc.update_task(task_id, payload)
    if not row:
        raise HTTPException(status_code=404, detail="Task not found")
    return row


@router.delete("/{task_id}", status_code=204)
def delete_task(task_id: int):
    svc = _get_service()
    ok = svc.delete_task(task_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Task not found")
