"""Memory Semantics API Routes."""

import logging
from typing import Any, Dict
from fastapi import APIRouter, HTTPException, Body

router = APIRouter(prefix="/semantics", tags=["Memory Semantics"])

logger = logging.getLogger(__name__)


@router.get("/clusters")
async def cluster():
    try:
        from common_lib.modules.memory.memory_semantics.service import (
            get_semantics_service,
        )

        svc = get_semantics_service()
        return await svc.cluster()
    except Exception as e:
        logger.error(f"Failed to get clusters: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/crystallize")
async def crystallize(payload: Dict[str, Any] = Body(...)):
    try:
        from common_lib.modules.memory.memory_semantics.service import (
            get_semantics_service,
        )

        svc = get_semantics_service()
        return await svc.crystallize(**payload)
    except Exception as e:
        logger.error(f"Failed to crystallize: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/topology")
async def get_topology():
    try:
        from common_lib.modules.memory.memory_semantics.service import (
            get_semantics_service,
        )

        svc = get_semantics_service()
        return await svc.get_topology()
    except Exception as e:
        logger.error(f"Failed to get topology: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/concepts")
async def get_concepts():
    try:
        from common_lib.modules.memory.memory_semantics.service import (
            get_semantics_service,
        )

        svc = get_semantics_service()
        return await svc.get_concepts()
    except Exception as e:
        logger.error(f"Failed to get concepts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/refresh")
async def refresh_topology():
    try:
        from common_lib.modules.memory.memory_semantics.service import (
            get_semantics_service,
        )

        svc = get_semantics_service()
        return await svc.refresh_topology()
    except Exception as e:
        logger.error(f"Failed to refresh topology: {e}")
        raise HTTPException(status_code=500, detail=str(e))
