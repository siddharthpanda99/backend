"""Knowledge Synthesis API Routes — thin wrappers delegating to common_lib."""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/knowledge", tags=["Memory Knowledge Synthesis"])


class SynthesiseRequest(BaseModel):
    project_id: str
    since_hours: int = 24
    limit: int = 30


@router.get("/items")
async def list_knowledge_items(
    project_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    insight_type: Optional[str] = Query(None),
):
    try:
        from common_lib.modules.memory.memory_semantics.service import (
            get_semantics_service,
        )
        svc = get_semantics_service()
        items = await svc.list_knowledge_items(
            project_id=project_id,
            limit=limit,
            insight_type=insight_type,
        )
        return {"items": items, "total": len(items)}
    except Exception as e:
        logger.exception("Failed to list knowledge items")
        raise HTTPException(500, detail=str(e))


@router.post("/synthesise")
async def synthesise_knowledge(request: SynthesiseRequest):
    try:
        from common_lib.modules.memory.memory_semantics.service import (
            get_semantics_service,
        )
        svc = get_semantics_service()
        items = await svc.synthesise_knowledge(
            project_id=request.project_id,
            since_hours=request.since_hours,
            limit=request.limit,
        )
        return {"items": items, "total": len(items)}
    except Exception as e:
        logger.exception("Failed to synthesize knowledge")
        raise HTTPException(500, detail=str(e))


__all__ = ["router"]
