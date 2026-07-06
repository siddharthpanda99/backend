"""HITL Assignments — CRUD routes for HITL reviewer assignments.

Orphaned legacy table: hitl_assignments maps reviewers to tasks/policies
with assignment strategy and scheduling.
"""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlmodel import Session, select
from common_lib.modules.data_storage.database.connection import get_engine
from sqlalchemy import Column, Integer, Text, Float, JSON, DateTime
from sqlalchemy.sql import func
from common_lib.modules.data_storage.database.orm import PureBase

router = APIRouter(prefix="/assignments", tags=["HITL — Assignments"])


class HITLAssignmentCreate(BaseModel):
    policy_id: str
    task_id: Optional[int] = None
    reviewer_id: str
    reviewer_type: str = Field(default="user", description="user | team | role | group")
    assignment_strategy: str = Field(default="manual", description="manual | round_robin | load_balanced | risk_based")
    status: str = Field(default="assigned", description="assigned | accepted | in_progress | completed | reassigned")
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
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class HITLAssignmentListResponse(BaseModel):
    items: list[HITLAssignmentResponse]
    total: int
    page: int = 1
    page_size: int = 20


class HITLAssignmentRecord(PureBase):
    __tablename__ = "hitl_assignments"
    id = Column(Integer, primary_key=True)
    policy_id = Column(Text, nullable=False, index=True)
    task_id = Column(Integer, nullable=True, index=True)
    reviewer_id = Column(Text, nullable=False, index=True)
    reviewer_type = Column(Text, default="user")
    assignment_strategy = Column(Text, default="manual")
    status = Column(Text, default="assigned", index=True)
    priority = Column(Integer, default=0)
    risk_score = Column(Float, nullable=True)
    metadata_json = Column("metadata", JSON, default={})
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


def _row_to_response(row: HITLAssignmentRecord) -> HITLAssignmentResponse:
    return HITLAssignmentResponse(
        id=row.id,
        policy_id=row.policy_id,
        task_id=row.task_id,
        reviewer_id=row.reviewer_id,
        reviewer_type=row.reviewer_type or "user",
        assignment_strategy=row.assignment_strategy or "manual",
        status=row.status or "assigned",
        priority=row.priority or 0,
        risk_score=row.risk_score,
        metadata_json=row.metadata_json if isinstance(row.metadata_json, dict) else {},
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("", response_model=HITLAssignmentListResponse)
def list_assignments(
    policy_id: Optional[str] = Query(None),
    task_id: Optional[int] = Query(None),
    reviewer_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    with Session(get_engine()) as session:
        query = select(HITLAssignmentRecord)
        if policy_id:
            query = query.where(HITLAssignmentRecord.policy_id == policy_id)
        if task_id:
            query = query.where(HITLAssignmentRecord.task_id == task_id)
        if reviewer_id:
            query = query.where(HITLAssignmentRecord.reviewer_id == reviewer_id)
        if status:
            query = query.where(HITLAssignmentRecord.status == status)
        query = query.order_by(HITLAssignmentRecord.created_at.desc())
        all_rows = session.exec(query).all()
        total = len(all_rows)
        rows = all_rows[(page - 1) * page_size : page * page_size]
        return HITLAssignmentListResponse(
            items=[_row_to_response(r) for r in rows],
            total=total,
            page=page,
            page_size=page_size,
        )


@router.get("/{assignment_id}", response_model=HITLAssignmentResponse)
def get_assignment(assignment_id: int):
    with Session(get_engine()) as session:
        row = session.get(HITLAssignmentRecord, assignment_id)
        if not row:
            raise HTTPException(status_code=404, detail="Assignment not found")
        return _row_to_response(row)


@router.post("", response_model=HITLAssignmentResponse, status_code=201)
def create_assignment(body: HITLAssignmentCreate):
    with Session(get_engine()) as session:
        row = HITLAssignmentRecord(
            policy_id=body.policy_id,
            task_id=body.task_id,
            reviewer_id=body.reviewer_id,
            reviewer_type=body.reviewer_type,
            assignment_strategy=body.assignment_strategy,
            status=body.status,
            priority=body.priority,
            risk_score=body.risk_score,
            metadata_json=body.metadata_json or {},
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return _row_to_response(row)


@router.put("/{assignment_id}", response_model=HITLAssignmentResponse)
def update_assignment(assignment_id: int, body: HITLAssignmentUpdate):
    with Session(get_engine()) as session:
        row = session.get(HITLAssignmentRecord, assignment_id)
        if not row:
            raise HTTPException(status_code=404, detail="Assignment not found")
        for field, value in body.model_dump(exclude_unset=True).items():
            setattr(row, field, value)
        row.updated_at = datetime.now(timezone.utc)
        session.add(row)
        session.commit()
        session.refresh(row)
        return _row_to_response(row)


@router.delete("/{assignment_id}", status_code=204)
def delete_assignment(assignment_id: int):
    with Session(get_engine()) as session:
        row = session.get(HITLAssignmentRecord, assignment_id)
        if not row:
            raise HTTPException(status_code=404, detail="Assignment not found")
        session.delete(row)
        session.commit()
