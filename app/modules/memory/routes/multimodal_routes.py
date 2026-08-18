"""Memory Multimodal API Routes."""

import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Query, Body

router = APIRouter(prefix="/multimodal", tags=["Memory Multimodal"])

logger = logging.getLogger(__name__)


@router.post("/image")
async def store_image(
    data: str = Body(...),
    metadata: Optional[Dict[str, Any]] = Body(None),
    agent_id: Optional[str] = Body(None),
    session_id: Optional[str] = Body(None),
):
    try:
        from common_lib.modules.memory.memory_multimodal.service import (
            get_multimodal_service,
        )

        svc = get_multimodal_service()
        return await svc.store_image(
            data=data,
            metadata=metadata,
            agent_id=agent_id,
            session_id=session_id,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/audio")
async def store_audio(
    data: str = Body(...),
    metadata: Optional[Dict[str, Any]] = Body(None),
    agent_id: Optional[str] = Body(None),
    session_id: Optional[str] = Body(None),
):
    try:
        from common_lib.modules.memory.memory_multimodal.service import (
            get_multimodal_service,
        )

        svc = get_multimodal_service()
        return await svc.store_audio(
            data=data,
            metadata=metadata,
            agent_id=agent_id,
            session_id=session_id,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/video")
async def store_video(
    data: str = Body(...),
    metadata: Optional[Dict[str, Any]] = Body(None),
    agent_id: Optional[str] = Body(None),
    session_id: Optional[str] = Body(None),
):
    try:
        from common_lib.modules.memory.memory_multimodal.service import (
            get_multimodal_service,
        )

        svc = get_multimodal_service()
        return await svc.store_video(
            data=data,
            metadata=metadata,
            agent_id=agent_id,
            session_id=session_id,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search")
async def cross_modal_search(
    query: str = Body(...),
    modalities: list = Body(["image", "audio", "video"]),
    limit: int = Body(20),
):
    try:
        from common_lib.modules.memory.memory_multimodal.search import (
            get_multimodal_search_service,
        )

        svc = get_multimodal_search_service()
        return await svc.search(
            query=query,
            modalities=modalities,
            limit=limit,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/assets/{memory_id}")
async def list_assets(memory_id: str):
    try:
        from common_lib.modules.memory.memory_multimodal.assets import get_asset_service

        svc = get_asset_service()
        assets = await svc.list_assets(memory_id=memory_id)
        return {"memory_id": memory_id, "assets": assets, "count": len(assets)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
