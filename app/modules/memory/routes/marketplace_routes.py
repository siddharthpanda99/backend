"""Submodule API Routes."""

import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Query, Body

router = APIRouter(prefix="/marketplace", tags=["Memory Marketplace"])

logger = logging.getLogger(__name__)


@router.get("/items")
async def list_items(category: Optional[str] = Query(None)):
    try:
        from common_lib.modules.memory.memory_marketplace.service import (
            get_marketplace_service,
        )

        svc = get_marketplace_service()
        return await svc.list_items(category=category)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/items/{item_id}")
async def get_item(item_id: str):
    try:
        from common_lib.modules.memory.memory_marketplace.service import (
            get_marketplace_service,
        )

        svc = get_marketplace_service()
        return await svc.get_item(item_id=item_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/profiles/apply")
async def apply_profile(payload: Dict[str, Any] = Body(...)):
    try:
        from common_lib.modules.memory.memory_marketplace.service import (
            get_marketplace_service,
        )

        svc = get_marketplace_service()
        return await svc.apply_profile(**payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/profiles")
async def list_profiles():
    try:
        from common_lib.modules.memory.memory_marketplace.service import (
            get_marketplace_service,
        )

        svc = get_marketplace_service()
        return await svc.list_profiles()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/profiles/recommended")
async def get_recommended_profiles():
    try:
        from common_lib.modules.memory.memory_marketplace.service import (
            get_marketplace_service,
        )

        svc = get_marketplace_service()
        return await svc.get_recommended_profiles()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
