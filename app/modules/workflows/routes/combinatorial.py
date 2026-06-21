"""Combinatorial workflow generation API — thin router delegating to CombinatorialService."""

import logging
from fastapi import APIRouter, HTTPException

from common_lib.modules.workflows.combinatorial_service import combinatorial_service
from common_lib.modules.workflows.generation.combinatorial_schemas import (
    CombinatorialGenerateRequest,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/history")
async def combinatorial_history():
    entries = combinatorial_service.list_history()
    return {"entries": entries}


@router.get("/history/{execution_id}")
async def combinatorial_history_by_id(execution_id: str):
    record = combinatorial_service.get_history_by_id(execution_id)
    if not record:
        raise HTTPException(status_code=404, detail="Execution not found")
    return record


@router.post("/generate")
async def combinatorial_generate(req: CombinatorialGenerateRequest):
    return await combinatorial_service.generate(req)
