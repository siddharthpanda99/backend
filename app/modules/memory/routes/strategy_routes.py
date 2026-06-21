"""Submodule API Routes."""

import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Query, Body

router = APIRouter(prefix="/strategy", tags=["Memory Strategy"])

logger = logging.getLogger(__name__)


@router.post("/goals")
async def create_goal(payload: Dict[str, Any] = Body(...)):
    try:
        from common_lib.modules.memory.memory_strategy.service import (
            get_strategy_service,
        )

        svc = get_strategy_service()
        return await svc.create_goal(**payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/goals")
async def list_goals():
    try:
        from common_lib.modules.memory.memory_strategy.service import (
            get_strategy_service,
        )

        svc = get_strategy_service()
        return await svc.list_goals()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/goals/{goal_id}")
async def get_goal(goal_id: str):
    try:
        from common_lib.modules.memory.memory_strategy.service import (
            get_strategy_service,
        )

        svc = get_strategy_service()
        return await svc.get_goal(goal_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/goals/{goal_id}")
async def update_goal(goal_id: str, payload: Dict[str, Any] = Body(...)):
    try:
        from common_lib.modules.memory.memory_strategy.service import (
            get_strategy_service,
        )

        svc = get_strategy_service()
        return await svc.update_goal(goal_id, **payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/plans/generate")
async def generate_plan(payload: Dict[str, Any] = Body(...)):
    try:
        from common_lib.modules.memory.memory_strategy.service import (
            get_strategy_service,
        )

        svc = get_strategy_service()
        return await svc.generate_plan(**payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/arbitrate")
async def arbitrate(payload: Dict[str, Any] = Body(...)):
    try:
        from common_lib.modules.memory.memory_strategy.service import (
            get_strategy_service,
        )

        svc = get_strategy_service()
        return await svc.arbitrate(**payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_status():
    try:
        from common_lib.modules.memory.memory_strategy.service import (
            get_strategy_service,
        )

        svc = get_strategy_service()
        return await svc.get_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/telemetry")
async def get_strategic_telemetry():
    try:
        from common_lib.modules.memory.memory_strategy.service import (
            get_strategy_service,
        )

        svc = get_strategy_service()
        return await svc.get_strategic_telemetry()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
