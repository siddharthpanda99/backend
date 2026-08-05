"""Secrets Manager Events — FastAPI routes for events, alerts, and subscriptions."""

from __future__ import annotations

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session
from pydantic import BaseModel

from common_lib.modules.data_storage.database.connection import get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/secrets/events", tags=["secrets-events"])


class EmitEventRequest(BaseModel):
    event_type: str
    actor_id: Optional[str] = None
    actor_type: Optional[str] = None
    resource_id: Optional[str] = None
    resource_name: Optional[str] = None
    mount: Optional[str] = None
    path: Optional[str] = None
    metadata: Optional[dict] = None


class CreateAlertRuleRequest(BaseModel):
    name: str
    event_type: str
    severity: str = "warning"
    description: Optional[str] = None
    notification_channel: Optional[str] = None
    notification_target: Optional[str] = None


class CreateSubscriptionRequest(BaseModel):
    name: str
    webhook_url: str
    event_types: Optional[list[str]] = None


@router.post("")
def emit_event(data: EmitEventRequest, session: Session = Depends(get_session)):
    """Emit a secret lifecycle event."""
    from common_lib.modules.secrets_manager.events.service import EventService
    svc = EventService(session)
    return svc.emit(**data.model_dump())


@router.get("")
def query_events(
    event_type: Optional[str] = Query(None),
    actor_id: Optional[str] = Query(None),
    resource_id: Optional[str] = Query(None),
    mount: Optional[str] = Query(None),
    limit: int = Query(100),
    offset: int = Query(0),
    session: Session = Depends(get_session),
):
    """Query secret lifecycle events."""
    from common_lib.modules.secrets_manager.events.service import EventService
    svc = EventService(session)
    return svc.query_events(
        event_type=event_type,
        actor_id=actor_id,
        resource_id=resource_id,
        mount=mount,
        limit=limit,
        offset=offset,
    )


@router.post("/alert-rules")
def create_alert_rule(data: CreateAlertRuleRequest, session: Session = Depends(get_session)):
    """Create an alert rule for secret events."""
    from common_lib.modules.secrets_manager.events.service import EventService
    svc = EventService(session)
    return svc.create_alert_rule(**data.model_dump())


@router.get("/alert-rules")
def list_alert_rules(
    event_type: Optional[str] = Query(None),
    session: Session = Depends(get_session),
):
    """List alert rules."""
    from common_lib.modules.secrets_manager.events.service import EventService
    svc = EventService(session)
    return {"rules": svc.list_alert_rules(event_type=event_type)}


@router.post("/alert-rules/{rule_id}/toggle")
def toggle_alert_rule(rule_id: str, enabled: bool = Query(True),
                      session: Session = Depends(get_session)):
    """Enable or disable an alert rule."""
    from common_lib.modules.secrets_manager.events.service import EventService
    svc = EventService(session)
    if not svc.toggle_alert_rule(rule_id, enabled):
        raise HTTPException(status_code=404, detail="Alert rule not found")
    return {"success": True}


@router.post("/subscriptions")
def create_subscription(data: CreateSubscriptionRequest,
                        session: Session = Depends(get_session)):
    """Create a webhook subscription for secret events."""
    from common_lib.modules.secrets_manager.events.service import EventService
    svc = EventService(session)
    return svc.create_subscription(**data.model_dump())


@router.get("/subscriptions")
def list_subscriptions(session: Session = Depends(get_session)):
    """List event subscriptions."""
    from common_lib.modules.secrets_manager.events.service import EventService
    svc = EventService(session)
    return {"subscriptions": svc.list_subscriptions()}
