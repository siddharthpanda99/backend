"""HITL Audit Logs — CRUD routes for HITL audit trail.

Orphaned legacy table: hitl_audit_logs provides a complete audit trail
of all HITL policy actions, decisions, and overrides.
"""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlmodel import Session, select
from common_lib.modules.data_storage.database.connection import get_engine
from sqlalchemy import Column, Integer, Text, JSON, DateTime
from sqlalchemy.sql import func
from common_lib.modules.data_storage.database.orm import PureBase

router = APIRouter(prefix="/audit-logs", tags=["HITL — Audit Logs"])


class HITLAuditLogCreate(BaseModel):
    policy_id: Optional[str] = None
    action: str = Field(..., description="created | updated | deleted | approved | rejected | overridden | escalated")
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
    created_at: Optional[datetime] = None


class HITLAuditLogListResponse(BaseModel):
    items: list[HITLAuditLogResponse]
    total: int
    page: int = 1
    page_size: int = 20


class HITLAuditLogRecord(PureBase):
    __tablename__ = "hitl_audit_logs"
    id = Column(Integer, primary_key=True)
    policy_id = Column(Text, nullable=True, index=True)
    action = Column(Text, nullable=False, index=True)
    actor_id = Column(Text, default="system")
    actor_type = Column(Text, default="system")
    target_type = Column(Text, nullable=True)
    target_id = Column(Text, nullable=True)
    summary = Column(Text, default="")
    details_json = Column("details", JSON, default={})
    created_at = Column(DateTime(timezone=True), server_default=func.now())


def _row_to_response(row: HITLAuditLogRecord) -> HITLAuditLogResponse:
    return HITLAuditLogResponse(
        id=row.id,
        policy_id=row.policy_id,
        action=row.action,
        actor_id=row.actor_id or "system",
        actor_type=row.actor_type or "system",
        target_type=row.target_type,
        target_id=row.target_id,
        summary=row.summary or "",
        details_json=row.details_json if isinstance(row.details_json, dict) else {},
        created_at=row.created_at,
    )


@router.get("", response_model=HITLAuditLogListResponse)
def list_audit_logs(
    policy_id: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    actor_id: Optional[str] = Query(None),
    target_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    with Session(get_engine()) as session:
        query = select(HITLAuditLogRecord)
        if policy_id:
            query = query.where(HITLAuditLogRecord.policy_id == policy_id)
        if action:
            query = query.where(HITLAuditLogRecord.action == action)
        if actor_id:
            query = query.where(HITLAuditLogRecord.actor_id == actor_id)
        if target_type:
            query = query.where(HITLAuditLogRecord.target_type == target_type)
        query = query.order_by(HITLAuditLogRecord.created_at.desc())
        all_rows = session.exec(query).all()
        total = len(all_rows)
        rows = all_rows[(page - 1) * page_size : page * page_size]
        return HITLAuditLogListResponse(
            items=[_row_to_response(r) for r in rows],
            total=total,
            page=page,
            page_size=page_size,
        )


@router.get("/stats")
def audit_log_stats():
    with Session(get_engine()) as session:
        all_rows = session.exec(select(HITLAuditLogRecord)).all()
        total = len(all_rows)
        by_action = {}
        by_actor_type = {}
        for r in all_rows:
            by_action[r.action] = by_action.get(r.action, 0) + 1
            by_actor_type[r.actor_type] = by_actor_type.get(r.actor_type, 0) + 1
        return {
            "total_logs": total,
            "by_action": by_action,
            "by_actor_type": by_actor_type,
        }


@router.get("/{log_id}", response_model=HITLAuditLogResponse)
def get_audit_log(log_id: int):
    with Session(get_engine()) as session:
        row = session.get(HITLAuditLogRecord, log_id)
        if not row:
            raise HTTPException(status_code=404, detail="Audit log not found")
        return _row_to_response(row)


@router.post("", response_model=HITLAuditLogResponse, status_code=201)
def create_audit_log(body: HITLAuditLogCreate):
    with Session(get_engine()) as session:
        row = HITLAuditLogRecord(
            policy_id=body.policy_id,
            action=body.action,
            actor_id=body.actor_id,
            actor_type=body.actor_type,
            target_type=body.target_type,
            target_id=body.target_id,
            summary=body.summary,
            details_json=body.details_json or {},
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return _row_to_response(row)
