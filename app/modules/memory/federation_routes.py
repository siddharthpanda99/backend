"""Submodule API Routes."""

import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Query, Body

router = APIRouter(prefix="/federation", tags=["Memory Federation"])

logger = logging.getLogger(__name__)


@router.post("/sync")
async def sync(payload: Dict[str, Any] = Body(...)):
    try:
        from common_lib.modules.memory.memory_federation.service import (
            get_federation_service,
        )

        svc = get_federation_service()
        return await svc.sync(**payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/topology")
async def discover_topology():
    try:
        from common_lib.modules.memory.memory_federation.service import (
            get_federation_service,
        )

        svc = get_federation_service()
        return await svc.discover_topology()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/push")
async def push(payload: Dict[str, Any] = Body(...)):
    try:
        from common_lib.modules.memory.memory_federation.service import (
            get_federation_service,
        )

        svc = get_federation_service()
        return await svc.push(**payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pull")
async def pull(payload: Dict[str, Any] = Body(...)):
    try:
        from common_lib.modules.memory.memory_federation.service import (
            get_federation_service,
        )

        svc = get_federation_service()
        return await svc.pull(**payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_status():
    try:
        from common_lib.modules.memory.memory_federation.service import (
            get_federation_service,
        )

        svc = get_federation_service()
        return await svc.get_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_stats():
    try:
        from common_lib.modules.memory.memory_federation.service import (
            get_federation_service,
        )

        svc = get_federation_service()
        return await svc.get_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
