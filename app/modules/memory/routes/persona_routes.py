"""Submodule API Routes."""

import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Query, Body

router = APIRouter(prefix="/persona", tags=["Memory Persona"])

logger = logging.getLogger(__name__)


@router.get("/")
async def list_personas():
    try:
        from common_lib.modules.memory.memory_persona.service import get_persona_service

        svc = get_persona_service()
        return await svc.list_personas()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{agent_id}")
async def get_persona(agent_id: str):
    try:
        from common_lib.modules.memory.memory_persona.service import get_persona_service

        svc = get_persona_service()
        return await svc.get_persona(agent_id=agent_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{agent_id}")
async def create_persona(agent_id: str, payload: Dict[str, Any] = Body(...)):
    try:
        from common_lib.modules.memory.memory_persona.service import get_persona_service

        svc = get_persona_service()
        return await svc.create_persona(agent_id=agent_id, config=payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{agent_id}/interaction")
async def update_interaction(agent_id: str, payload: Dict[str, Any] = Body(...)):
    try:
        from common_lib.modules.memory.memory_persona.service import get_persona_service

        svc = get_persona_service()
        return await svc.update_interaction(agent_id=agent_id, interaction=payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{agent_id}/context")
async def generate_context(agent_id: str, scenario: str = Body(..., embed=True)):
    try:
        from common_lib.modules.memory.memory_persona.service import get_persona_service

        svc = get_persona_service()
        return await svc.generate_context(agent_id=agent_id, scenario=scenario)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{agent_id}")
async def delete_persona(agent_id: str):
    try:
        from common_lib.modules.memory.memory_persona.service import get_persona_service

        svc = get_persona_service()
        return await svc.delete_persona(agent_id=agent_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
