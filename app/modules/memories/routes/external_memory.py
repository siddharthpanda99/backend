from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from app.modules.memories.dependencies import get_memory_service
from common_lib.modules.memory.service import MemoryService
from common_lib.modules.memory.schemas import (
    MemoryCreate,
    MemoryResponse,
    MemorySearchResponse,
    MemoryStatsResponse,
)

router = APIRouter(prefix="", tags=["memory"])


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
        memory_type=str(data.memory_type),
        agent_id=data.agent_id,
        session_id=data.session_id
    )


@router.get("/{memory_id}", response_model=MemoryResponse)
async def get_memory(
    memory_id: str, 
    service: MemoryService = Depends(get_memory_service)
):
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
