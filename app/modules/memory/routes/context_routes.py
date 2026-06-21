"""Memory Context API Routes."""

import logging
from typing import Any, Dict
from fastapi import APIRouter, HTTPException, Body

router = APIRouter(prefix="/context", tags=["Memory Context"])

logger = logging.getLogger(__name__)


@router.post("/build")
async def build_context(payload: Dict[str, Any] = Body(...)):
    try:
        from common_lib.modules.memory.memory_context.service import get_context_service

        svc = get_context_service()
        return await svc.build_context(**payload)
    except Exception as e:
        logger.error(f"Failed to build context: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compress")
async def compress(payload: Dict[str, Any] = Body(...)):
    try:
        from common_lib.modules.memory.memory_context.service import get_context_service

        svc = get_context_service()
        return await svc.compress(**payload)
    except Exception as e:
        logger.error(f"Failed to compress context: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tokenize")
async def tokenize(payload: Dict[str, Any] = Body(...)):
    try:
        from common_lib.modules.memory.memory_context.service import get_context_service

        svc = get_context_service()
        return await svc.tokenize(**payload)
    except Exception as e:
        logger.error(f"Failed to tokenize context: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/prioritize")
async def prioritize(payload: Dict[str, Any] = Body(...)):
    try:
        from common_lib.modules.memory.memory_context.service import get_context_service

        svc = get_context_service()
        return await svc.prioritize(**payload)
    except Exception as e:
        logger.error(f"Failed to prioritize context: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/session/start")
async def start_session(payload: Dict[str, Any] = Body(...)):
    try:
        from common_lib.modules.memory.memory_context.service import get_context_service

        svc = get_context_service()
        return await svc.start_session(**payload)
    except Exception as e:
        logger.error(f"Failed to start session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/session/end")
async def end_session(payload: Dict[str, Any] = Body(...)):
    try:
        from common_lib.modules.memory.memory_context.service import get_context_service

        svc = get_context_service()
        return await svc.end_session(**payload)
    except Exception as e:
        logger.error(f"Failed to end session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/session/{session_id}")
async def get_session_state(session_id: str):
    try:
        from common_lib.modules.memory.memory_context.service import get_context_service

        svc = get_context_service()
        return await svc.get_session_state(session_id=session_id)
    except Exception as e:
        logger.error(f"Failed to get session state: {e}")
        raise HTTPException(status_code=500, detail=str(e))
