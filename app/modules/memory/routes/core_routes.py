"""Core Memory API Routes."""

import logging
from typing import Any, Dict
from fastapi import APIRouter, HTTPException, Query, Body

router = APIRouter(prefix="/core", tags=["Memory Core"])

logger = logging.getLogger(__name__)


@router.get("/types")
async def get_memory_types():
    try:
        from common_lib.modules.memory.memory_core.service import get_core_service

        svc = get_core_service()
        return await svc.get_memory_types()
    except Exception as e:
        logger.error(f"Failed to get memory types: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scopes")
async def get_memory_scopes():
    try:
        from common_lib.modules.memory.memory_core.service import get_core_service

        svc = get_core_service()
        return await svc.get_memory_scopes()
    except Exception as e:
        logger.error(f"Failed to get memory scopes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tiers")
async def get_storage_tiers():
    try:
        from common_lib.modules.memory.memory_core.service import get_core_service

        svc = get_core_service()
        return await svc.get_storage_tiers()
    except Exception as e:
        logger.error(f"Failed to get storage tiers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/quota/{agent_id}")
async def check_quota(agent_id: str, current_count: int = Query(0)):
    try:
        from common_lib.modules.memory.memory_core.service import get_core_service

        svc = get_core_service()
        return await svc.check_quota(agent_id=agent_id, current_count=current_count)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/decay")
async def apply_decay(payload: Dict[str, Any] = Body(...)):
    try:
        from common_lib.modules.memory.memory_core.service import get_core_service

        svc = get_core_service()
        return await svc.apply_decay(**payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/forget")
async def schedule_forget(payload: Dict[str, Any] = Body(...)):
    try:
        from common_lib.modules.memory.memory_core.service import get_core_service

        svc = get_core_service()
        return await svc.schedule_forget(**payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/deduplicate")
async def check_duplicate(payload: Dict[str, Any] = Body(...)):
    try:
        from common_lib.modules.memory.memory_core.service import get_core_service

        svc = get_core_service()
        return await svc.check_duplicate(**payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/deletion-certificate")
async def create_deletion_certificate(payload: Dict[str, Any] = Body(...)):
    try:
        from common_lib.modules.memory.memory_core.service import get_core_service

        svc = get_core_service()
        return await svc.create_deletion_certificate(**payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
