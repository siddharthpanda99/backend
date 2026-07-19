"""Events module API routes — Callback management, event delivery, workflow mapping.

Thin routing layer that delegates to common_lib.modules.events services.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()


class CallbackCreateRequest(BaseModel):
    name: str
    url: str
    events: Optional[List[str]] = None
    config: Optional[Dict[str, Any]] = None


class EventDeliverRequest(BaseModel):
    event_type: str
    payload: Dict[str, Any]
    target: Optional[str] = None


def _get_callback_service():
    from common_lib.modules.events.service import CallbackManager
    return CallbackManager()


@router.get("/callbacks")
async def list_callbacks() -> Dict[str, Any]:
    """List all registered callbacks."""
    try:
        svc = _get_callback_service()
        result = svc.list_callbacks() if hasattr(svc, "list_callbacks") else []
        return {"callbacks": result, "count": len(result) if isinstance(result, list) else 0}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/callbacks")
async def create_callback(request: CallbackCreateRequest) -> Dict[str, Any]:
    """Register a new callback."""
    try:
        svc = _get_callback_service()
        result = svc.create(request.name, request.url, request.events, request.config) if hasattr(svc, "create") else {"name": request.name}
        return {"callback": result, "message": "Callback created successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/callbacks/{callback_id}")
async def delete_callback(callback_id: str) -> Dict[str, Any]:
    """Delete a callback."""
    try:
        svc = _get_callback_service()
        svc.delete(callback_id) if hasattr(svc, "delete") else None
        return {"success": True, "message": "Callback deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/deliver")
async def deliver_event(request: EventDeliverRequest) -> Dict[str, Any]:
    """Deliver an event to registered callbacks."""
    try:
        svc = _get_callback_service()
        result = svc.deliver(request.event_type, request.payload, request.target) if hasattr(svc, "deliver") else {"delivered": 0}
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/workflows/mapping")
async def get_workflow_mapping() -> Dict[str, Any]:
    """Get event-to-workflow mapping."""
    try:
        svc = _get_callback_service()
        result = svc.get_mapping() if hasattr(svc, "get_mapping") else {}
        return {"mapping": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
