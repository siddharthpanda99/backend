"""Notification Subscriber API Routes — Subscribe, list subscriptions, dispatch."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications/subscriptions", tags=["notification-subscriptions"])


def _get_session():
    from common_lib.modules.integration.adapters.database_adapter import get_db_port
    engine = get_db_port().get_engine()
    return Session(engine)


@router.get("")
def list_subscriptions(
    event_type: Optional[str] = Query(None),
    session: Session = Depends(_get_session),
):
    """List event subscriptions."""
    from common_lib.modules.notification.subscriber.service import SubscriberService
    svc = SubscriberService(session)
    return {"subscriptions": svc.list_subscriptions(event_type=event_type)}


@router.post("")
def create_subscription(
    name: str = Query(...),
    event_type: str = Query(...),
    handler_type: str = Query("webhook"),
    session: Session = Depends(_get_session),
):
    """Register an event subscription."""
    from common_lib.modules.notification.subscriber.service import SubscriberService
    svc = SubscriberService(session)
    return svc.subscribe(name=name, event_type=event_type, handler_type=handler_type)


@router.post("/dispatch")
def dispatch_event(
    event_type: str = Query(...),
    payload: dict = {},
    session: Session = Depends(_get_session),
):
    """Dispatch an event to matching subscriptions."""
    from common_lib.modules.notification.subscriber.service import SubscriberService
    svc = SubscriberService(session)
    return {"results": svc.dispatch(event_type=event_type, payload=payload)}
