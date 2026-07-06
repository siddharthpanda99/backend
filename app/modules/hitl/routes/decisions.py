"""HITL Decisions — CRUD routes for HITL decision records.

Orphaned legacy table: hitl_decisions tracks every approve/reject/edit/escalate
decision made against a HITL policy.
"""

from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlmodel import Session, select
from common_lib.modules.data_storage.database.connection import get_engine

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
    created_at: Optional[datetime] = None


class HITLDecisionListResponse(BaseModel):
    items: list[HITLDecisionResponse]
    total: int
    page: int = 1
    page_size: int = 20


# We define the table inline since it's an orphaned legacy table
# that may or may not exist in the current schema
from sqlalchemy import Column, Integer, Text, Float, JSON, DateTime
from sqlalchemy.sql import func
from common_lib.modules.data_storage.database.orm import PureBase


class HITLDecisionRecord(PureBase):
    __tablename__ = "hitl_decisions"
    id = Column(Integer, primary_key=True)
    policy_id = Column(Text, nullable=False, index=True)
    action = Column(Text, nullable=False)
    risk_score = Column(Float, default=0.0)
    confidence = Column(Float, default=0.5)
    rationale = Column(Text, default="")
    reviewer_id = Column(Text, nullable=True)
    context_json = Column("context", JSON, default={})
    created_at = Column(DateTime(timezone=True), server_default=func.now())


def _row_to_response(row: HITLDecisionRecord) -> HITLDecisionResponse:
    return HITLDecisionResponse(
        id=row.id,
        policy_id=row.policy_id,
        action=row.action,
        risk_score=row.risk_score or 0.0,
        confidence=row.confidence or 0.5,
        rationale=row.rationale or "",
        reviewer_id=row.reviewer_id,
        context_json=row.context_json if isinstance(row.context_json, dict) else {},
        created_at=row.created_at,
    )


@router.get("", response_model=HITLDecisionListResponse)
def list_decisions(
    policy_id: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    reviewer_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    with Session(get_engine()) as session:
        query = select(HITLDecisionRecord)
        if policy_id:
            query = query.where(HITLDecisionRecord.policy_id == policy_id)
        if action:
            query = query.where(HITLDecisionRecord.action == action)
        if reviewer_id:
            query = query.where(HITLDecisionRecord.reviewer_id == reviewer_id)
        query = query.order_by(HITLDecisionRecord.created_at.desc())
        all_rows = session.exec(query).all()
        total = len(all_rows)
        rows = all_rows[(page - 1) * page_size : page * page_size]
        return HITLDecisionListResponse(
            items=[_row_to_response(r) for r in rows],
            total=total,
            page=page,
            page_size=page_size,
        )


@router.get("/stats")
def decision_stats():
    with Session(get_engine()) as session:
        all_rows = session.exec(select(HITLDecisionRecord)).all()
        total = len(all_rows)
        by_action = {}
        for r in all_rows:
            by_action[r.action] = by_action.get(r.action, 0) + 1
        avg_risk = sum(r.risk_score or 0 for r in all_rows) / max(total, 1)
        avg_confidence = sum(r.confidence or 0 for r in all_rows) / max(total, 1)
        return {
            "total_decisions": total,
            "by_action": by_action,
            "avg_risk_score": round(avg_risk, 3),
            "avg_confidence": round(avg_confidence, 3),
        }


@router.get("/{decision_id}", response_model=HITLDecisionResponse)
def get_decision(decision_id: int):
    with Session(get_engine()) as session:
        row = session.get(HITLDecisionRecord, decision_id)
        if not row:
            raise HTTPException(status_code=404, detail="Decision not found")
        return _row_to_response(row)


@router.post("", response_model=HITLDecisionResponse, status_code=201)
def create_decision(body: HITLDecisionCreate):
    with Session(get_engine()) as session:
        row = HITLDecisionRecord(
            policy_id=body.policy_id,
            action=body.action,
            risk_score=body.risk_score,
            confidence=body.confidence,
            rationale=body.rationale,
            reviewer_id=body.reviewer_id,
            context_json=body.context_json or {},
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return _row_to_response(row)


@router.delete("/{decision_id}", status_code=204)
def delete_decision(decision_id: int):
    with Session(get_engine()) as session:
        row = session.get(HITLDecisionRecord, decision_id)
        if not row:
            raise HTTPException(status_code=404, detail="Decision not found")
        session.delete(row)
        session.commit()
