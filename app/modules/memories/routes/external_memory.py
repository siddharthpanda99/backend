from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from app.modules.memories.dependencies import get_memory_service
from common_lib.modules.memory.service import MemoryService, MemoryType

router = APIRouter(prefix="", tags=["memory"])


class MemoryCreate(BaseModel):
    content: str
    memory_type: str = "episodic"
    agent_id: Optional[str] = None
    session_id: Optional[str] = None
    turn: Optional[int] = None
    importance: float = 0.5


class MemoryResponse(BaseModel):
    id: str
    content: str
    memory_type: str
    agent_id: Optional[str] = None
    session_id: Optional[str] = None


class MemorySearchResponse(BaseModel):
    results: list
    total: int


class MemoryStatsResponse(BaseModel):
    total_memories: int
    retrievals: int
    active_sessions: int
    by_type: dict


@router.post("/", response_model=MemoryResponse)
async def store_memory(
    data: MemoryCreate, 
    service: MemoryService = Depends(get_memory_service)
):
    memory_id = await service.store_memory(
        content=data.content,
        memory_type=data.memory_type,
        agent_id=data.agent_id,
        session_id=data.session_id,
        importance=data.importance
    )
    return MemoryResponse(
        id=memory_id, 
        content=data.content, 
        memory_type=data.memory_type,
        agent_id=data.agent_id,
        session_id=data.session_id
    )


@router.get("/{memory_id}", response_model=MemoryResponse)
async def get_memory(
    memory_id: str, 
    service: MemoryService = Depends(get_memory_service)
):
    # This assumes the service has a get method, but it doesn't yet. 
    # For now, we'll return a stub or mock it from the repository
    if service.repository:
        record = await service.repository.get_memory(memory_id)
        if record:
            return MemoryResponse(
                id=memory_id,
                content=record.get("content", ""),
                memory_type=record.get("memory_type", "episodic"),
                agent_id=record.get("agent_id"),
                session_id=record.get("session_id")
            )
    
    raise HTTPException(status_code=404, detail="Memory not found")


@router.post("/search", response_model=MemorySearchResponse)
async def search_memory(
    q: str = Query(...), 
    service: MemoryService = Depends(get_memory_service)
):
    results = await service.search(q)
    return MemorySearchResponse(results=results, total=len(results))


@router.get("/stats", response_model=MemoryStatsResponse)
async def get_stats(service: MemoryService = Depends(get_memory_service)):
    stats = await service.get_stats()
    return MemoryStatsResponse(
        total_memories=stats.get("total_memories", 0),
        retrievals=stats.get("retrievals", 0),
        active_sessions=stats.get("active_sessions", 0),
        by_type={}
    )


__all__ = ["router"]
