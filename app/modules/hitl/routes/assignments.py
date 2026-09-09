"""HITL Assignments — CRUD routes for HITL reviewer assignments.

Orphaned legacy table: hitl_assignments maps reviewers to tasks/policies
with assignment strategy and scheduling.
"""

from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from common_lib.modules.integration.ports.hitl_port import get_hitl_legacy_service

router = APIRouter(prefix="/assignments", tags=["HITL — Assignments"])


class HITLAssignmentCreate(BaseModel):
    policy_id: str
    task_id: Optional[int] = None
    reviewer_id: str
    reviewer_type: str = Field(default="user", description="user | team | role | group")
    assignment_strategy: str = Field(
        default="manual",
        description="manual | round_robin | load_balanced | risk_based",
    )
    status: str = Field(
        default="assigned",
        description="assigned | accepted | in_progress | completed | reassigned",
    )
    priority: int = Field(default=0)
    risk_score: Optional[float] = None
    metadata_json: Optional[dict] = None


class HITLAssignmentUpdate(BaseModel):
    status: Optional[str] = None
    reviewer_id: Optional[str] = None
    assignment_strategy: Optional[str] = None
    priority: Optional[int] = None
    metadata_json: Optional[dict] = None


class HITLAssignmentResponse(BaseModel):
    id: int
    policy_id: str
    task_id: Optional[int] = None
    reviewer_id: str
    reviewer_type: str
    assignment_strategy: str
    status: str
    priority: int
    risk_score: Optional[float] = None
    metadata_json: Optional[dict] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class HITLAssignmentListResponse(BaseModel):
    items: list[HITLAssignmentResponse]
    total: int
    page: int = 1
    page_size: int = 20


def _get_service():
    svc = get_hitl_legacy_service()
    if not svc:
        raise HTTPException(status_code=503, detail="HITL legacy service unavailable")
    return svc


@router.get("", response_model=HITLAssignmentListResponse)
def list_assignments(
    policy_id: Optional[str] = Query(None),
    task_id: Optional[int] = Query(None),
    reviewer_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    svc = _get_service()
    result = svc.list_assignments(
        policy_id=policy_id,
        task_id=task_id,
        reviewer_id=reviewer_id,
        status=status,
        page=page,
        page_size=page_size,
    )
    return HITLAssignmentListResponse(**result)


@router.get("/{assignment_id}", response_model=HITLAssignmentResponse)
def get_assignment(assignment_id: int):
    svc = _get_service()
    row = svc.get_assignment(assignment_id)
    if not row:
        raise HTTPException(status_code=404, detail="Assignment not found")
    return row


@router.post("", response_model=HITLAssignmentResponse, status_code=201)
def create_assignment(body: HITLAssignmentCreate):
    svc = _get_service()
    payload = body.model_dump(exclude_none=True)
    return svc.create_assignment(payload)


@router.put("/{assignment_id}", response_model=HITLAssignmentResponse)
def update_assignment(assignment_id: int, body: HITLAssignmentUpdate):
    svc = _get_service()
    payload = body.model_dump(exclude_unset=True)
    if not payload:
        raise HTTPException(status_code=400, detail="No fields to update")
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    row = svc.update_assignment(assignment_id, payload)
    if not row:
        raise HTTPException(status_code=404, detail="Assignment not found")
    return row


@router.delete("/{assignment_id}", status_code=204)
def delete_assignment(assignment_id: int):
    svc = _get_service()
    ok = svc.delete_assignment(assignment_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Assignment not found")
