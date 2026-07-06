"""Session Runtime — CRUD routes for session runtime tables.

Orphaned legacy tables: safety_profiles, reasoning_states, tool_execution_records,
conversation_history. These provide observability into agent session internals.
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

router = APIRouter(prefix="/session-runtime", tags=["Session Runtime"])


# ── Safety Profiles ───────────────────────────────────────────────

class SafetyProfileCreate(BaseModel):
    name: str
    blocked_topics: list[str] = Field(default_factory=list)
    forbidden_patterns: list[str] = Field(default_factory=list)
    moderation_enabled: bool = True


class SafetyProfileResponse(BaseModel):
    id: int
    name: str
    blocked_topics: list[str] = []
    forbidden_patterns: list[str] = []
    moderation_enabled: bool = True


class SafetyProfileListResponse(BaseModel):
    items: list[SafetyProfileResponse]
    total: int


class SafetyProfileRecord(PureBase):
    __tablename__ = "safety_profiles"
    id = Column(Integer, primary_key=True)
    name = Column(Text, unique=True, nullable=False)
    blocked_topics_json = Column("blocked_topics", JSON, default=[])
    forbidden_patterns_json = Column("forbidden_patterns", JSON, default=[])
    moderation_enabled = Column(Integer, default=1)


# ── Reasoning States ──────────────────────────────────────────────

class ReasoningStateResponse(BaseModel):
    id: int
    current_plan: Optional[str] = None
    goals: list = []
    status: Optional[str] = None


class ReasoningStateListResponse(BaseModel):
    items: list[ReasoningStateResponse]
    total: int


class ReasoningStateRecord(PureBase):
    __tablename__ = "reasoning_states"
    id = Column(Integer, primary_key=True)
    current_plan = Column(Text)
    goals_json = Column("goals", JSON, default=[])
    status = Column(Text)


# ── Tool Execution Records ────────────────────────────────────────

class ToolExecutionRecordResponse(BaseModel):
    id: int
    context_id: Optional[int] = None
    tool_id: str
    input_data: Optional[dict] = None
    output_data: Optional[dict] = None
    timestamp: Optional[datetime] = None


class ToolExecutionRecordListResponse(BaseModel):
    items: list[ToolExecutionRecordResponse]
    total: int


class ToolExecRecord(PureBase):
    __tablename__ = "tool_execution_records"
    id = Column(Integer, primary_key=True)
    context_id = Column(Integer, nullable=True)
    tool_id = Column(Text, nullable=False, index=True)
    input_json = Column("input", JSON)
    output_json = Column("output", JSON)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())


# ── Conversation History ──────────────────────────────────────────

class ConversationHistoryCreate(BaseModel):
    session_id: Optional[str] = None
    type: Optional[str] = None
    importance: Optional[int] = None
    subject: Optional[str] = None
    predicate: Optional[str] = None
    object: Optional[str] = None
    confidence: Optional[float] = None
    source: Optional[str] = None
    content: Optional[str] = None
    extraction_type: Optional[str] = None


class ConversationHistoryResponse(BaseModel):
    id: Optional[int] = None
    session_id: Optional[str] = None
    type: Optional[str] = None
    importance: Optional[int] = None
    subject: Optional[str] = None
    predicate: Optional[str] = None
    object: Optional[str] = None
    confidence: Optional[float] = None
    source: Optional[str] = None
    content: Optional[str] = None
    extraction_type: Optional[str] = None
    access_count: Optional[int] = None
    created_at: Optional[datetime] = None


class ConversationHistoryListResponse(BaseModel):
    items: list[ConversationHistoryResponse]
    total: int
    page: int = 1
    page_size: int = 20


class ConversationHistoryRecord(PureBase):
    __tablename__ = "conversation_history"
    id = Column(Integer, primary_key=True)
    session_id = Column(Text, index=True)
    type = Column(Text)
    importance = Column(Integer)
    subject = Column(Text)
    predicate = Column(Text)
    object = Column(Text)
    confidence = Column(Float)
    source = Column(Text)
    content = Column(Text)
    metadata_json = Column("metadata", JSON)
    embedding = Column(Text)
    access_count = Column(Integer, default=0)
    last_accessed = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    extraction_type = Column(Text)


# ── Response helpers ──────────────────────────────────────────────

def _safety_profile_response(row) -> SafetyProfileResponse:
    return SafetyProfileResponse(
        id=row.id,
        name=row.name,
        blocked_topics=row.blocked_topics_json if isinstance(row.blocked_topics_json, list) else [],
        forbidden_patterns=row.forbidden_patterns_json if isinstance(row.forbidden_patterns_json, list) else [],
        moderation_enabled=bool(row.moderation_enabled),
    )


def _reasoning_state_response(row) -> ReasoningStateResponse:
    return ReasoningStateResponse(
        id=row.id,
        current_plan=row.current_plan,
        goals=row.goals_json if isinstance(row.goals_json, list) else [],
        status=row.status,
    )


def _tool_exec_response(row) -> ToolExecutionRecordResponse:
    return ToolExecutionRecordResponse(
        id=row.id,
        context_id=row.context_id,
        tool_id=row.tool_id or "",
        input_data=row.input_json if isinstance(row.input_json, dict) else None,
        output_data=row.output_json if isinstance(row.output_json, dict) else None,
        timestamp=row.timestamp,
    )


def _conv_history_response(row) -> ConversationHistoryResponse:
    return ConversationHistoryResponse(
        id=row.id,
        session_id=row.session_id,
        type=row.type,
        importance=row.importance,
        subject=row.subject,
        predicate=row.predicate,
        object=row.object,
        confidence=row.confidence,
        source=row.source,
        content=row.content,
        extraction_type=row.extraction_type,
        access_count=row.access_count,
        created_at=row.created_at,
    )


# ── Safety Profiles endpoints ─────────────────────────────────────

@router.get("/safety-profiles", response_model=SafetyProfileListResponse)
def list_safety_profiles():
    with Session(get_engine()) as session:
        rows = session.exec(select(SafetyProfileRecord)).all()
        return SafetyProfileListResponse(
            items=[_safety_profile_response(r) for r in rows],
            total=len(rows),
        )


@router.get("/safety-profiles/{profile_id}", response_model=SafetyProfileResponse)
def get_safety_profile(profile_id: int):
    with Session(get_engine()) as session:
        row = session.get(SafetyProfileRecord, profile_id)
        if not row:
            raise HTTPException(status_code=404, detail="Safety profile not found")
        return _safety_profile_response(row)


@router.post("/safety-profiles", response_model=SafetyProfileResponse, status_code=201)
def create_safety_profile(body: SafetyProfileCreate):
    with Session(get_engine()) as session:
        row = SafetyProfileRecord(
            name=body.name,
            blocked_topics_json=body.blocked_topics,
            forbidden_patterns_json=body.forbidden_patterns,
            moderation_enabled=1 if body.moderation_enabled else 0,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return _safety_profile_response(row)


@router.delete("/safety-profiles/{profile_id}", status_code=204)
def delete_safety_profile(profile_id: int):
    with Session(get_engine()) as session:
        row = session.get(SafetyProfileRecord, profile_id)
        if not row:
            raise HTTPException(status_code=404, detail="Safety profile not found")
        session.delete(row)
        session.commit()


# ── Reasoning States endpoints ────────────────────────────────────

@router.get("/reasoning-states", response_model=ReasoningStateListResponse)
def list_reasoning_states(
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    with Session(get_engine()) as session:
        query = select(ReasoningStateRecord)
        if status:
            query = query.where(ReasoningStateRecord.status == status)
        query = query.limit(limit)
        rows = session.exec(query).all()
        return ReasoningStateListResponse(
            items=[_reasoning_state_response(r) for r in rows],
            total=len(rows),
        )


@router.get("/reasoning-states/{state_id}", response_model=ReasoningStateResponse)
def get_reasoning_state(state_id: int):
    with Session(get_engine()) as session:
        row = session.get(ReasoningStateRecord, state_id)
        if not row:
            raise HTTPException(status_code=404, detail="Reasoning state not found")
        return _reasoning_state_response(row)


# ── Tool Execution Records endpoints ──────────────────────────────

@router.get("/tool-executions", response_model=ToolExecutionRecordListResponse)
def list_tool_executions(
    tool_id: Optional[str] = Query(None),
    context_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    with Session(get_engine()) as session:
        query = select(ToolExecRecord)
        if tool_id:
            query = query.where(ToolExecRecord.tool_id == tool_id)
        if context_id is not None:
            query = query.where(ToolExecRecord.context_id == context_id)
        query = query.order_by(ToolExecRecord.timestamp.desc())
        all_rows = session.exec(query).all()
        total = len(all_rows)
        rows = all_rows[(page - 1) * page_size : page * page_size]
        return ToolExecutionRecordListResponse(
            items=[_tool_exec_response(r) for r in rows],
            total=total,
        )


@router.get("/tool-executions/stats")
def tool_execution_stats():
    with Session(get_engine()) as session:
        all_rows = session.exec(select(ToolExecRecord)).all()
        total = len(all_rows)
        by_tool = {}
        for r in all_rows:
            by_tool[r.tool_id] = by_tool.get(r.tool_id, 0) + 1
        return {
            "total_executions": total,
            "by_tool": by_tool,
            "unique_tools": len(by_tool),
        }


@router.get("/tool-executions/{exec_id}", response_model=ToolExecutionRecordResponse)
def get_tool_execution(exec_id: int):
    with Session(get_engine()) as session:
        row = session.get(ToolExecRecord, exec_id)
        if not row:
            raise HTTPException(status_code=404, detail="Tool execution not found")
        return _tool_exec_response(row)


# ── Conversation History endpoints ────────────────────────────────

@router.get("/conversation-history", response_model=ConversationHistoryListResponse)
def list_conversation_history(
    session_id: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    extraction_type: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    with Session(get_engine()) as session:
        query = select(ConversationHistoryRecord)
        if session_id:
            query = query.where(ConversationHistoryRecord.session_id == session_id)
        if type:
            query = query.where(ConversationHistoryRecord.type == type)
        if extraction_type:
            query = query.where(ConversationHistoryRecord.extraction_type == extraction_type)
        if search:
            like = f"%{search}%"
            query = query.where(
                ConversationHistoryRecord.content.like(like)
            )
        query = query.order_by(ConversationHistoryRecord.created_at.desc())
        all_rows = session.exec(query).all()
        total = len(all_rows)
        rows = all_rows[(page - 1) * page_size : page * page_size]
        return ConversationHistoryListResponse(
            items=[_conv_history_response(r) for r in rows],
            total=total,
            page=page,
            page_size=page_size,
        )


@router.get("/conversation-history/stats")
def conversation_history_stats():
    with Session(get_engine()) as session:
        all_rows = session.exec(select(ConversationHistoryRecord)).all()
        total = len(all_rows)
        by_type = {}
        by_extraction = {}
        for r in all_rows:
            by_type[r.type or "unknown"] = by_type.get(r.type or "unknown", 0) + 1
            by_extraction[r.extraction_type or "unknown"] = by_extraction.get(r.extraction_type or "unknown", 0) + 1
        sessions = set(r.session_id for r in all_rows if r.session_id)
        return {
            "total_entries": total,
            "unique_sessions": len(sessions),
            "by_type": by_type,
            "by_extraction_type": by_extraction,
        }


@router.post("/conversation-history", response_model=ConversationHistoryResponse, status_code=201)
def create_conversation_history(body: ConversationHistoryCreate):
    with Session(get_engine()) as session:
        row = ConversationHistoryRecord(
            session_id=body.session_id,
            type=body.type,
            importance=body.importance,
            subject=body.subject,
            predicate=body.predicate,
            object=body.object,
            confidence=body.confidence,
            source=body.source,
            content=body.content,
            extraction_type=body.extraction_type,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return _conv_history_response(row)


@router.get("/summary")
def session_runtime_summary():
    """Aggregate stats across all session runtime tables."""
    with Session(get_engine()) as session:
        safety = len(session.exec(select(SafetyProfileRecord)).all())
        reasoning = len(session.exec(select(ReasoningStateRecord)).all())
        tool_execs = len(session.exec(select(ToolExecRecord)).all())
        conv_history = len(session.exec(select(ConversationHistoryRecord)).all())
        return {
            "safety_profiles": safety,
            "reasoning_states": reasoning,
            "tool_executions": tool_execs,
            "conversation_history": conv_history,
            "total_entities": safety + reasoning + tool_execs + conv_history,
        }
