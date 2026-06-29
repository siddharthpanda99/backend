"""Daily Summaries API Routes — thin wrappers delegating to common_lib."""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/summaries", tags=["Memory Summaries"])


class GenerateSummaryRequest(BaseModel):
    project_id: str
    date: Optional[str] = None
    agent_id: Optional[str] = None


@router.get("")
async def list_summaries(
    project_id: Optional[str] = Query(None),
    limit: int = Query(30, ge=1, le=200),
):
    try:
        from common_lib.modules.memory.memory_semantics.service import (
            get_semantics_service,
        )
        svc = get_semantics_service()
        return {"summaries": await svc.list_summaries(project_id=project_id, limit=limit)}
    except Exception as e:
        logger.exception("Failed to list summaries")
        raise HTTPException(500, detail=str(e))


@router.post("/generate")
async def generate_summary(request: GenerateSummaryRequest):
    try:
        from common_lib.modules.memory.memory_semantics.service import (
            get_semantics_service,
        )
        svc = get_semantics_service()
        result = await svc.generate_daily_summary(
            project_id=request.project_id,
            date=request.date,
            agent_id=request.agent_id,
        )
        return {"summary": result}
    except Exception as e:
        logger.exception("Failed to generate summary")
        raise HTTPException(500, detail=str(e))


__all__ = ["router"]
