"""Submodule API Routes."""

import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Query, Body

router = APIRouter(prefix="/causal", tags=["Memory Causal"])

logger = logging.getLogger(__name__)


@router.post("/discover")
async def discover(payload: Dict[str, Any] = Body(...)):
    try:
        from common_lib.modules.memory.memory_causal.service import get_causal_service

        svc = get_causal_service()
        return await svc.discover(**payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/do-calculus")
async def do_calculus(payload: Dict[str, Any] = Body(...)):
    try:
        from common_lib.modules.memory.memory_causal.service import get_causal_service

        svc = get_causal_service()
        return await svc.do_calculus(**payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/root-causes/{agent_id}")
async def find_root_causes(agent_id: str, outcome: str = Query(...)):
    try:
        from common_lib.modules.memory.memory_causal.service import get_causal_service

        svc = get_causal_service()
        return await svc.find_root_causes(agent_id=agent_id, outcome=outcome)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/edges")
async def add_edge(payload: Dict[str, Any] = Body(...)):
    try:
        from common_lib.modules.memory.memory_causal.service import get_causal_service

        svc = get_causal_service()
        return await svc.add_edge(**payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/graph/{agent_id}")
async def get_graph(agent_id: str):
    try:
        from common_lib.modules.memory.memory_causal.service import get_causal_service

        svc = get_causal_service()
        return await svc.get_graph(agent_id=agent_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
