"""Submodule API Routes."""

import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Query, Body

router = APIRouter(prefix="/adaptation", tags=["Memory Adaptation"])

logger = logging.getLogger(__name__)


@router.post("/adapt")
async def adapt(payload: Dict[str, Any] = Body(...)):
    try:
        from common_lib.modules.memory.memory_adaptation.service import (
            get_adaptation_service,
        )

        svc = get_adaptation_service()
        return await svc.adapt(**payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reinforce")
async def reinforce(payload: Dict[str, Any] = Body(...)):
    try:
        from common_lib.modules.memory.memory_adaptation.service import (
            get_adaptation_service,
        )

        svc = get_adaptation_service()
        return await svc.reinforce(**payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bandit")
async def select_bandit_arm(context: str = Query(...)):
    try:
        from common_lib.modules.memory.memory_adaptation.service import (
            get_adaptation_service,
        )

        svc = get_adaptation_service()
        return await svc.select_bandit_arm(context=context)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/telemetry")
async def get_telemetry():
    try:
        from common_lib.modules.memory.memory_adaptation.service import (
            get_adaptation_service,
        )

        svc = get_adaptation_service()
        return await svc.get_telemetry()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
