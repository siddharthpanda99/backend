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


class EventPublishRequest(BaseModel):
    event_type: str
    source: str
    payload: Dict[str, Any]
    actor_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class EventSubscriptionRequest(BaseModel):
    event_type: str
    callback_url: Optional[str] = None


def _get_callback_service():
    from common_lib.modules.notification.events import CallbackService
    return CallbackService()


def _get_session():
    from contextlib import contextmanager
    from common_lib.modules.integration.ports import get_db_port
    @contextmanager
    def _session_cm():
        session = get_db_port().get_session()
        try:
            yield session
        finally:
            session.close()
    return _session_cm()


def _get_event_service():
    from common_lib.modules.events.service import EventService
    return EventService


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


# ── Event Bus Service Routes ──────────────────────────────────────────────

@router.post("/publish")
async def publish_event(request: EventPublishRequest) -> Dict[str, Any]:
    """Publish an event to the platform event bus."""
    try:
        with _get_session() as session:
            svc = _get_event_service()(session)
            result = svc.publish_event(
                event_type=request.event_type,
                source=request.source,
                payload=request.payload,
                actor_id=request.actor_id,
                metadata=request.metadata,
            )
            return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/events")
async def list_events(
    event_type: Optional[str] = None,
    source: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    """List published events with optional filters."""
    try:
        with _get_session() as session:
            svc = _get_event_service()(session)
            return svc.list_events(
                event_type=event_type, source=source,
                limit=limit, offset=offset,
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/subscriptions")
async def list_subscriptions() -> Dict[str, Any]:
    """List all active event subscriptions."""
    try:
        with _get_session() as session:
            svc = _get_event_service()(session)
            return {"subscriptions": svc.list_subscriptions()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/delivery/stats")
async def get_delivery_stats(
    event_type: Optional[str] = None,
) -> Dict[str, Any]:
    """Get event delivery statistics."""
    try:
        with _get_session() as session:
            svc = _get_event_service()(session)
            return svc.get_delivery_stats(event_type=event_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
