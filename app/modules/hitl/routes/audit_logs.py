"""HITL Audit Logs — CRUD routes for HITL audit trail.

Orphaned legacy table: hitl_audit_logs provides a complete audit trail
of all HITL policy actions, decisions, and overrides.
"""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from common_lib.modules.integration.ports.hitl_port import get_hitl_legacy_service

router = APIRouter(prefix="/audit-logs", tags=["HITL — Audit Logs"])


class HITLAuditLogCreate(BaseModel):
    policy_id: Optional[str] = None
    action: str = Field(
        ...,
        description="created | updated | deleted | approved | rejected | overridden | escalated",
    )
    actor_id: str = Field(default="system")
    actor_type: str = Field(default="system", description="user | system | agent | api")
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    summary: str = ""
    details_json: Optional[dict] = None


class HITLAuditLogResponse(BaseModel):
    id: int
    policy_id: Optional[str] = None
    action: str
    actor_id: str
    actor_type: str
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    summary: str
    details_json: Optional[dict] = None
    created_at: Optional[str] = None


class HITLAuditLogListResponse(BaseModel):
    items: list[HITLAuditLogResponse]
    total: int
    page: int = 1
    page_size: int = 20


def _get_service():
    svc = get_hitl_legacy_service()
    if not svc:
        raise HTTPException(status_code=503, detail="HITL legacy service unavailable")
    return svc


@router.get("", response_model=HITLAuditLogListResponse)
def list_audit_logs(
    policy_id: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    actor_id: Optional[str] = Query(None),
    target_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    svc = _get_service()
    result = svc.list_audit_logs(
        policy_id=policy_id,
        action=action,
        actor_id=actor_id,
        target_type=target_type,
        page=page,
        page_size=page_size,
    )
    return HITLAuditLogListResponse(**result)


@router.get("/stats")
def audit_log_stats():
    svc = _get_service()
    return svc.audit_log_stats()


@router.get("/{log_id}", response_model=HITLAuditLogResponse)
def get_audit_log(log_id: int):
    svc = _get_service()
    row = svc.get_audit_log(log_id)
    if not row:
        raise HTTPException(status_code=404, detail="Audit log not found")
    return row


@router.post("", response_model=HITLAuditLogResponse, status_code=201)
def create_audit_log(body: HITLAuditLogCreate):
    svc = _get_service()
    payload = body.model_dump(exclude_none=True)
    return svc.create_audit_log(payload)
