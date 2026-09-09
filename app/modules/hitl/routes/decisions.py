"""HITL Decisions — CRUD routes for HITL decision records.

Orphaned legacy table: hitl_decisions tracks every approve/reject/edit/escalate
decision made against a HITL policy.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from common_lib.modules.integration.ports.hitl_port import get_hitl_legacy_service

router = APIRouter(prefix="/decisions", tags=["HITL — Decisions"])


class HITLDecisionCreate(BaseModel):
    policy_id: str
    action: str = Field(..., description="approve | reject | edit | defer | escalate")
    risk_score: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    rationale: str = ""
    reviewer_id: Optional[str] = None
    context_json: Optional[dict] = None


class HITLDecisionResponse(BaseModel):
    id: int
    policy_id: str
    action: str
    risk_score: float
    confidence: float
    rationale: str
    reviewer_id: Optional[str] = None
    context_json: Optional[dict] = None
    created_at: Optional[str] = None


class HITLDecisionListResponse(BaseModel):
    items: list[HITLDecisionResponse]
    total: int
    page: int = 1
    page_size: int = 20


def _get_service():
    svc = get_hitl_legacy_service()
    if not svc:
        raise HTTPException(status_code=503, detail="HITL legacy service unavailable")
    return svc


@router.get("", response_model=HITLDecisionListResponse)
def list_decisions(
    policy_id: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    reviewer_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    svc = _get_service()
    result = svc.list_decisions(
        policy_id=policy_id,
        action=action,
        reviewer_id=reviewer_id,
        page=page,
        page_size=page_size,
    )
    return HITLDecisionListResponse(**result)


@router.get("/stats")
def decision_stats():
    svc = _get_service()
    return svc.decision_stats()


@router.get("/{decision_id}", response_model=HITLDecisionResponse)
def get_decision(decision_id: int):
    svc = _get_service()
    row = svc.get_decision(decision_id)
    if not row:
        raise HTTPException(status_code=404, detail="Decision not found")
    return row


@router.post("", response_model=HITLDecisionResponse, status_code=201)
def create_decision(body: HITLDecisionCreate):
    svc = _get_service()
    payload = body.model_dump(exclude_none=True)
    return svc.create_decision(payload)


@router.delete("/{decision_id}", status_code=204)
def delete_decision(decision_id: int):
    svc = _get_service()
    ok = svc.delete_decision(decision_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Decision not found")
