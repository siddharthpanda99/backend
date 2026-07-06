"""HITL Tasks — CRUD routes for HITL task/request records.

Orphaned legacy table: hitl_tasks represents human-in-the-loop review tasks
that need to be completed by assigned reviewers.
"""

from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlmodel import Session, select
from common_lib.modules.data_storage.database.connection import get_engine
from sqlalchemy import Column, Integer, Text, Float, JSON, DateTime, Boolean
from sqlalchemy.sql import func
from common_lib.modules.data_storage.database.orm import PureBase

router = APIRouter(prefix="/tasks", tags=["HITL — Tasks"])


class HITLTaskCreate(BaseModel):
    policy_id: str
    title: str
    description: str = ""
    status: str = Field(default="pending", description="pending | in_review | approved | rejected | escalated | deferred")
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
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class HITLTaskListResponse(BaseModel):
    items: list[HITLTaskResponse]
    total: int
    page: int = 1
    page_size: int = 20


class HITLTaskRecord(PureBase):
    __tablename__ = "hitl_tasks"
    id = Column(Integer, primary_key=True)
    policy_id = Column(Text, nullable=False, index=True)
    title = Column(Text, nullable=False)
    description = Column(Text, default="")
    status = Column(Text, default="pending", index=True)
    priority = Column(Integer, default=0)
    risk_score = Column(Float, default=0.0)
    assignee_id = Column(Text, nullable=True)
    assignee_type = Column(Text, nullable=True)
    context_json = Column("context", JSON, default={})
    due_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


def _row_to_response(row: HITLTaskRecord) -> HITLTaskResponse:
    return HITLTaskResponse(
        id=row.id,
        policy_id=row.policy_id,
        title=row.title,
        description=row.description or "",
        status=row.status or "pending",
        priority=row.priority or 0,
        risk_score=row.risk_score or 0.0,
        assignee_id=row.assignee_id,
        assignee_type=row.assignee_type,
        context_json=row.context_json if isinstance(row.context_json, dict) else {},
        due_at=row.due_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("", response_model=HITLTaskListResponse)
def list_tasks(
    policy_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    assignee_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    with Session(get_engine()) as session:
        query = select(HITLTaskRecord)
        if policy_id:
            query = query.where(HITLTaskRecord.policy_id == policy_id)
        if status:
            query = query.where(HITLTaskRecord.status == status)
        if assignee_id:
            query = query.where(HITLTaskRecord.assignee_id == assignee_id)
        query = query.order_by(HITLTaskRecord.created_at.desc())
        all_rows = session.exec(query).all()
        total = len(all_rows)
        rows = all_rows[(page - 1) * page_size : page * page_size]
        return HITLTaskListResponse(
            items=[_row_to_response(r) for r in rows],
            total=total,
            page=page,
            page_size=page_size,
        )


@router.get("/stats")
def task_stats():
    with Session(get_engine()) as session:
        all_rows = session.exec(select(HITLTaskRecord)).all()
        total = len(all_rows)
        by_status = {}
        for r in all_rows:
            by_status[r.status] = by_status.get(r.status, 0) + 1
        overdue = sum(1 for r in all_rows if r.due_at and r.due_at < datetime.now(timezone.utc) and r.status in ("pending", "in_review"))
        return {
            "total_tasks": total,
            "by_status": by_status,
            "overdue": overdue,
        }


@router.get("/{task_id}", response_model=HITLTaskResponse)
def get_task(task_id: int):
    with Session(get_engine()) as session:
        row = session.get(HITLTaskRecord, task_id)
        if not row:
            raise HTTPException(status_code=404, detail="Task not found")
        return _row_to_response(row)


@router.post("", response_model=HITLTaskResponse, status_code=201)
def create_task(body: HITLTaskCreate):
    with Session(get_engine()) as session:
        row = HITLTaskRecord(
            policy_id=body.policy_id,
            title=body.title,
            description=body.description,
            status=body.status,
            priority=body.priority,
            risk_score=body.risk_score,
            assignee_id=body.assignee_id,
            assignee_type=body.assignee_type,
            context_json=body.context_json or {},
            due_at=body.due_at,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return _row_to_response(row)


@router.put("/{task_id}", response_model=HITLTaskResponse)
def update_task(task_id: int, body: HITLTaskUpdate):
    with Session(get_engine()) as session:
        row = session.get(HITLTaskRecord, task_id)
        if not row:
            raise HTTPException(status_code=404, detail="Task not found")
        for field, value in body.model_dump(exclude_unset=True).items():
            setattr(row, field, value)
        row.updated_at = datetime.now(timezone.utc)
        session.add(row)
        session.commit()
        session.refresh(row)
        return _row_to_response(row)


@router.delete("/{task_id}", status_code=204)
def delete_task(task_id: int):
    with Session(get_engine()) as session:
        row = session.get(HITLTaskRecord, task_id)
        if not row:
            raise HTTPException(status_code=404, detail="Task not found")
        session.delete(row)
        session.commit()
