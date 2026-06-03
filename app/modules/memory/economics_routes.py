"""Memory Economics API Routes."""

import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Query, Body

router = APIRouter(prefix="/economics", tags=["Memory Economics"])

logger = logging.getLogger(__name__)


@router.post("/cost/track")
async def track_cost(
    agent_id: str = Body(...),
    operation: str = Body(...),
    tokens: Optional[int] = Body(None),
    storage_bytes: Optional[int] = Body(None),
    metadata: Optional[Dict[str, Any]] = Body(None),
):
    try:
        from common_lib.modules.memory.economics.costing import get_costing_service

        svc = get_costing_service()
        return await svc.track_cost(
            agent_id=agent_id,
            operation=operation,
            tokens=tokens,
            storage_bytes=storage_bytes,
            metadata=metadata,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/budget/{agent_id}")
async def check_budget(agent_id: str):
    try:
        from common_lib.modules.memory.economics.budget import get_budget_service

        svc = get_budget_service()
        budget = await svc.check_budget(agent_id=agent_id)
        if budget is None:
            raise HTTPException(
                status_code=404, detail=f"No budget found for agent: {agent_id}"
            )
        return budget
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/budget/{agent_id}")
async def set_limit(
    agent_id: str,
    monthly_limit: float = Body(...),
    hard_cap: bool = Body(True),
):
    try:
        from common_lib.modules.memory.economics.budget import get_budget_service

        svc = get_budget_service()
        return await svc.set_limit(
            agent_id=agent_id,
            monthly_limit=monthly_limit,
            hard_cap=hard_cap,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/report/{agent_id}")
async def get_report(
    agent_id: str,
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
):
    try:
        from common_lib.modules.memory.economics.reporting import (
            get_economics_reporting_service,
        )

        svc = get_economics_reporting_service()
        report = await svc.get_report(
            agent_id=agent_id,
            start_date=start_date,
            end_date=end_date,
        )
        if not report:
            raise HTTPException(
                status_code=404, detail=f"No report found for agent: {agent_id}"
            )
        return report
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bandit")
async def get_bandit_stats(agent_id: Optional[str] = Query(None)):
    try:
        from common_lib.modules.memory.economics.bandit import get_bandit_service

        svc = get_bandit_service()
        return await svc.get_stats(agent_id=agent_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
