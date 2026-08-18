"""Memory Working Area API Routes."""

import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Query, Body

router = APIRouter(prefix="/working", tags=["Memory Working"])

logger = logging.getLogger(__name__)


@router.post("/push")
async def push(
    content: Any = Body(...),
    agent_id: Optional[str] = Body(None),
    session_id: Optional[str] = Body(None),
    priority: int = Body(0),
):
    try:
        from common_lib.modules.memory.memory_working import get_working_memory_service

        svc = get_working_memory_service()
        return await svc.push(
            content=content,
            agent_id=agent_id,
            session_id=session_id,
            priority=priority,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/focus")
async def set_focus(
    memory_id: str = Body(...),
    agent_id: Optional[str] = Body(None),
    session_id: Optional[str] = Body(None),
):
    try:
        from common_lib.modules.memory.memory_working import get_focus_service

        svc = get_focus_service()
        return await svc.set_focus(
            memory_id=memory_id,
            agent_id=agent_id,
            session_id=session_id,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/focus/{session_id}")
async def get_focus(session_id: str):
    try:
        from common_lib.modules.memory.memory_working import get_focus_service

        svc = get_focus_service()
        focus = await svc.get_focus(session_id=session_id)
        if not focus:
            raise HTTPException(
                status_code=404, detail=f"No focus set for session: {session_id}"
            )
        return focus
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/buffer/{session_id}")
async def get_buffer(
    session_id: str,
    limit: int = Query(50),
    offset: int = Query(0),
):
    try:
        from common_lib.modules.memory.memory_working import get_buffer_service

        svc = get_buffer_service()
        return await svc.get_buffer(
            session_id=session_id,
            limit=limit,
            offset=offset,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/promote")
async def promote(
    memory_id: str = Body(...),
    target_tier: str = Body("long_term"),
    agent_id: Optional[str] = Body(None),
):
    try:
        from common_lib.modules.memory.memory_working import get_promotion_service

        svc = get_promotion_service()
        return await svc.promote(
            memory_id=memory_id,
            target_tier=target_tier,
            agent_id=agent_id,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/clear")
async def clear(
    session_id: Optional[str] = Body(None),
    agent_id: Optional[str] = Body(None),
):
    try:
        from common_lib.modules.memory.memory_working import get_working_memory_service

        svc = get_working_memory_service()
        return await svc.clear(
            session_id=session_id,
            agent_id=agent_id,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/buffers/{agent_id}")
async def list_buffers(agent_id: str):
    try:
        from common_lib.modules.memory.memory_working import get_buffer_service

        svc = get_buffer_service()
        return await svc.list_buffers(agent_id=agent_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
