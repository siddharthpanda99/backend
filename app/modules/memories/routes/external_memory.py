from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import create_engine
from sqlalchemy.orm import Session as DBSession

# Point back to common_lib for the logic
from common_lib.modules.memory.service import MemoryService
from common_lib.modules.memory.schema import (
    MemoryCreate,
    MemoryUpdate,
    MemoryResponse,
    MemorySearchRequest,
    MemorySearchResponse,
    MemoryStatsResponse,
    SharedRegionCreate,
    SharedRegionResponse,
    MemoryCompactRequest,
)
from common_lib.modules.memory.types import MemoryType
from common_lib.modules.memory.config import DEFAULT_MEMORY_CONFIG

# Backend specific imports for DB
from app.core.settings import get_settings

router = APIRouter(prefix="", tags=["memory"])


def get_db():
    settings = get_settings()
    DATABASE_URL = settings.SQLALCHEMY_DATABASE_URI.replace(
        "postgresql://", "postgresql+psycopg://"
    )
    engine = create_engine(DATABASE_URL, echo=False)

    with DBSession(engine) as session:
        try:
            yield session
        finally:
            session.close()


def get_memory_service(db: DBSession = Depends(get_db)) -> MemoryService:
    return MemoryService(session=db, config=DEFAULT_MEMORY_CONFIG)


@router.post("/", response_model=MemoryResponse)
def store_memory(
    data: MemoryCreate,
    service: MemoryService = Depends(get_memory_service),
):
    memory_id = service.store_memory(
        memory_type=data.memory_type,
        content=data.content,
        agent_id=data.agent_id,
        session_id=data.session_id,
        turn=data.turn,
        importance=data.importance,
    )
    record = service.retrieve_memory(memory_id)
    if not record:
        raise HTTPException(status_code=500, detail="Failed to store memory")
    return MemoryResponse(**record.model_dump(), id=record.id)


@router.get("/{memory_id}", response_model=MemoryResponse)
def get_memory(
    memory_id: int,
    service: MemoryService = Depends(get_memory_service),
):
    record = service.retrieve_memory(memory_id)
    if not record:
        raise HTTPException(status_code=404, detail="Memory not found")
    return MemoryResponse(**record.model_dump(), id=record.id)


@router.delete("/{memory_id}")
def delete_memory(
    memory_id: int,
    service: MemoryService = Depends(get_memory_service),
):
    if not service.delete_memory(memory_id):
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"status": "deleted", "memory_id": memory_id}


@router.post("/search", response_model=MemorySearchResponse)
def search_memories(
    data: MemorySearchRequest,
    service: MemoryService = Depends(get_memory_service),
):
    results = service.search(
        query=data.query,
        memory_types=data.memory_types,
        agent_id=data.agent_id,
        limit=data.limit,
    )
    memories = [MemoryResponse(**r.model_dump(), id=r.id) for r in results]
    return MemorySearchResponse(memories=memories, total=len(memories))


@router.get("/session/{session_id}")
def get_session_memories(
    session_id: str,
    service: MemoryService = Depends(get_memory_service),
):
    memories = service.get_by_session(session_id)
    return {
        "session_id": session_id,
        "memories": [MemoryResponse(**m.model_dump(), id=m.id) for m in memories],
    }


@router.get("/agent/{agent_id}")
def get_agent_memories(
    agent_id: str,
    service: MemoryService = Depends(get_memory_service),
):
    memories = service.get_by_agent(agent_id)
    return {
        "agent_id": agent_id,
        "memories": [MemoryResponse(**m.model_dump(), id=m.id) for m in memories],
    }


@router.get("/stats", response_model=MemoryStatsResponse)
def get_stats(
    service: MemoryService = Depends(get_memory_service),
):
    stats = service.get_stats()
    return MemoryStatsResponse(**stats)


@router.post("/compact")
def compact_memories(
    data: MemoryCompactRequest,
    service: MemoryService = Depends(get_memory_service),
):
    deleted = service.compact(ttl_days=data.ttl_days, keep_recent=data.keep_recent)
    return {"deleted": deleted}


@router.get("/insights")
def get_insights(
    agent_id: Optional[str] = None,
    service: MemoryService = Depends(get_memory_service),
):
    insights = service.extract_insights(agent_id)
    return {
        "insights": [MemoryResponse(**i.model_dump(), id=i.id) for i in insights],
    }
