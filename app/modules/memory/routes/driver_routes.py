"""Submodule API Routes."""

import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Query, Body

router = APIRouter(prefix="/driver", tags=["Memory Driver"])

logger = logging.getLogger(__name__)


@router.get("/blocks")
async def list_blocks(category: Optional[str] = Query(None)):
    try:
        from common_lib.modules.memory.memory_driver.service import get_driver_service

        svc = get_driver_service()
        return await svc.list_blocks(category=category)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/blocks/{block_id}")
async def get_block(block_id: str):
    try:
        from common_lib.modules.memory.memory_driver.service import get_driver_service

        svc = get_driver_service()
        return await svc.get_block(block_id=block_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/profiles")
async def list_profiles():
    try:
        from common_lib.modules.memory.memory_driver.service import get_driver_service

        svc = get_driver_service()
        return await svc.list_profiles()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/profiles/load")
async def load_profile(payload: Dict[str, Any] = Body(...)):
    try:
        from common_lib.modules.memory.memory_driver.service import get_driver_service

        svc = get_driver_service()
        return await svc.load_profile(**payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/blocks/{block_id}/execute")
async def execute_block(block_id: str, payload: Dict[str, Any] = Body(...)):
    try:
        from common_lib.modules.memory.memory_driver.service import get_driver_service

        svc = get_driver_service()
        return await svc.execute_block(block_id=block_id, input_data=payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_status():
    try:
        from common_lib.modules.memory.memory_driver.service import get_driver_service

        svc = get_driver_service()
        return await svc.get_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
