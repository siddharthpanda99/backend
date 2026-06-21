"""Submodule API Routes."""

import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, Body

router = APIRouter(prefix="/stores", tags=["Memory Stores"])

logger = logging.getLogger(__name__)


@router.get("/")
async def list_stores():
    try:
        from common_lib.modules.memory.memory_stores.service import get_stores_service

        svc = get_stores_service()
        return await svc.list_stores()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{store_id}")
async def get_store(store_id: str):
    try:
        from common_lib.modules.memory.memory_stores.service import get_stores_service

        svc = get_stores_service()
        return await svc.get_store(store_id=store_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/episodic")
async def store_episodic(payload: Dict[str, Any] = Body(...)):
    try:
        from common_lib.modules.memory.memory_stores.service import get_stores_service

        svc = get_stores_service()
        return await svc.store_episodic(**payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/semantic")
async def store_semantic(payload: Dict[str, Any] = Body(...)):
    try:
        from common_lib.modules.memory.memory_stores.service import get_stores_service

        svc = get_stores_service()
        return await svc.store_semantic(**payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/procedural")
async def store_procedural(payload: Dict[str, Any] = Body(...)):
    try:
        from common_lib.modules.memory.memory_stores.service import get_stores_service

        svc = get_stores_service()
        return await svc.store_procedural(**payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{store_id}/stats")
async def get_store_stats(store_id: str):
    try:
        from common_lib.modules.memory.memory_stores.service import get_stores_service

        svc = get_stores_service()
        return await svc.get_store_stats(store_id=store_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{store_id}/health")
async def check_store_health(store_id: str):
    try:
        from common_lib.modules.memory.memory_stores.service import get_stores_service

        svc = get_stores_service()
        return await svc.check_store_health(store_id=store_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
