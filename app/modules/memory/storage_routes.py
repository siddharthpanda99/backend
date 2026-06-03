"""Memory Storage API Routes."""

import logging
from typing import Any, Dict
from fastapi import APIRouter, HTTPException, Body, Query

router = APIRouter(prefix="/storage", tags=["Memory Storage"])

logger = logging.getLogger(__name__)


@router.post("/store")
async def store(payload: Dict[str, Any] = Body(...)):
    try:
        from common_lib.modules.memory.memory_storage.service import get_storage_service

        svc = get_storage_service()
        return await svc.store(**payload)
    except Exception as e:
        logger.error(f"Failed to store memory: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/retrieve/{memory_id}")
async def retrieve(memory_id: str):
    try:
        from common_lib.modules.memory.memory_storage.service import get_storage_service

        svc = get_storage_service()
        return await svc.retrieve(memory_id=memory_id)
    except Exception as e:
        logger.error(f"Failed to retrieve memory: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{memory_id}")
async def delete(memory_id: str, hard: bool = Query(False)):
    try:
        from common_lib.modules.memory.memory_storage.service import get_storage_service

        svc = get_storage_service()
        return await svc.delete(memory_id=memory_id, hard=hard)
    except Exception as e:
        logger.error(f"Failed to delete memory: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/list")
async def list_memories(payload: Dict[str, Any] = Body(...)):
    try:
        from common_lib.modules.memory.memory_storage.service import get_storage_service

        svc = get_storage_service()
        return await svc.list_memories(**payload)
    except Exception as e:
        logger.error(f"Failed to list memories: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cache/stats")
async def get_cache_stats():
    try:
        from common_lib.modules.memory.memory_storage.service import get_storage_service

        svc = get_storage_service()
        return await svc.get_cache_stats()
    except Exception as e:
        logger.error(f"Failed to get cache stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cache/clear")
async def clear_cache():
    try:
        from common_lib.modules.memory.memory_storage.service import get_storage_service

        svc = get_storage_service()
        return await svc.clear_cache()
    except Exception as e:
        logger.error(f"Failed to clear cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tiers")
async def get_tiers():
    try:
        from common_lib.modules.memory.memory_storage.service import get_storage_service

        svc = get_storage_service()
        return await svc.get_tiers()
    except Exception as e:
        logger.error(f"Failed to get tiers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/migrate")
async def migrate_tier(payload: Dict[str, Any] = Body(...)):
    try:
        from common_lib.modules.memory.memory_storage.service import get_storage_service

        svc = get_storage_service()
        return await svc.migrate_tier(**payload)
    except Exception as e:
        logger.error(f"Failed to migrate tier: {e}")
        raise HTTPException(status_code=500, detail=str(e))
