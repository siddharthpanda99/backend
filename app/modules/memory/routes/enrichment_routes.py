"""Memory Enrichment API Routes — thin wrappers delegating to common_lib."""

import logging
from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/enrichment", tags=["Memory Enrichment"])


@router.post("/{memory_id}")
async def enrich_memory(memory_id: str):
    try:
        from common_lib.modules.memory.memory_semantics.service import (
            get_semantics_service,
        )
        svc = get_semantics_service()
        result = await svc.enrich_memory(memory_id)
        return {"enrichment": result}
    except Exception as e:
        logger.exception(f"Failed to enrich memory {memory_id}")
        raise HTTPException(500, detail=str(e))


@router.post("/batch")
async def enrich_batch(
    limit: int = Query(50, ge=1, le=200),
    min_importance: float = Query(0.0, ge=0.0, le=1.0),
):
    try:
        from common_lib.modules.memory.memory_semantics.service import (
            get_semantics_service,
        )
        svc = get_semantics_service()
        results = await svc.enrich_batch(limit=limit, min_importance=min_importance)
        return {"enriched": results, "total": len(results)}
    except Exception as e:
        logger.exception("Failed to enrich batch")
        raise HTTPException(500, detail=str(e))


__all__ = ["router"]
