"""Submodule API Routes."""

import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Query, Body

router = APIRouter(prefix="/execution", tags=["Memory Execution"])

logger = logging.getLogger(__name__)


@router.post("/chains/start")
async def start_chain(payload: Dict[str, Any] = Body(...)):
    try:
        from common_lib.modules.memory.memory_execution.service import (
            get_execution_service,
        )

        svc = get_execution_service()
        return await svc.start_chain(**payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chains/{chain_id}/steps")
async def add_step(chain_id: str, payload: Dict[str, Any] = Body(...)):
    try:
        from common_lib.modules.memory.memory_execution.service import (
            get_execution_service,
        )

        svc = get_execution_service()
        return await svc.add_step(chain_id=chain_id, **payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chains/{chain_id}/complete")
async def complete_chain(chain_id: str, payload: Optional[Dict[str, Any]] = Body(None)):
    try:
        from common_lib.modules.memory.memory_execution.service import (
            get_execution_service,
        )

        svc = get_execution_service()
        kwargs = payload or {}
        return await svc.complete_chain(chain_id=chain_id, **kwargs)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chains/{chain_id}")
async def get_chain(chain_id: str):
    try:
        from common_lib.modules.memory.memory_execution.service import (
            get_execution_service,
        )

        svc = get_execution_service()
        return await svc.get_chain(chain_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chains")
async def list_chains(session_id: Optional[str] = Query(None)):
    try:
        from common_lib.modules.memory.memory_execution.service import (
            get_execution_service,
        )

        svc = get_execution_service()
        return await svc.list_chains(session_id=session_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/latency-budget")
async def get_latency_budget():
    try:
        from common_lib.modules.memory.memory_execution.service import (
            get_execution_service,
        )

        svc = get_execution_service()
        return await svc.get_latency_budget()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
