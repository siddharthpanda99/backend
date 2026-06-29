"""RIP Memory routes — Store and search agent memories.

Uses the Memory connector for real implementations with configurable
retention policies, index types, and match methods.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from common_lib.modules.rip.rip_memory.schemas import (
    MemoryStoreRequest,
    MemorySearchRequest,
    MemoryResponse,
)

router = APIRouter(prefix="/rip/memory", tags=["RIP — Memory"])


@router.post("/store", response_model=MemoryResponse)
async def store_memory(payload: MemoryStoreRequest):
    """Store a memory record (episodic, semantic, or procedural).

    Retention policies: session, persistent, decay.
    Uses the Memory connector for real storage backends.
    """
    try:
        from common_lib.modules.rip.rip_connectors import create_memory_fn

        memory_fn = await create_memory_fn(agent_id=payload.agent_id)
        result = await memory_fn.store(
            memory_type=payload.memory_type,
            content=payload.content,
            summary=payload.summary,
            importance=payload.importance,
            source=payload.source,
            metadata=payload.metadata,
            session_id=payload.session_id,
            ttl_seconds=payload.ttl_seconds,
            tenant_id=payload.tenant_id,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search")
async def search_memory(payload: MemorySearchRequest):
    """Search memory records by semantic similarity and importance.

    Index types: vector, keyword, hybrid.
    Match methods: template, semantic, exact.
    """
    try:
        from common_lib.modules.rip.rip_connectors import create_memory_search_fn
        import time

        start = time.perf_counter()

        search_fn = await create_memory_search_fn(
            agent_id=payload.agent_id,
            index_type="hybrid",
            match_method="semantic",
        )
        results = await search_fn(
            query=payload.query,
            agent_id=payload.agent_id,
            memory_types=payload.memory_types,
            top_k=payload.top_k,
            min_importance=payload.min_importance,
            include_ephemeral=payload.include_ephemeral,
            tenant_id=payload.tenant_id,
        )
        elapsed = (time.perf_counter() - start) * 1000

        return {
            "query": payload.query,
            "agent_id": payload.agent_id,
            "results": list(results) if results else [],
            "count": len(results) if results else 0,
            "latency_ms": elapsed,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
