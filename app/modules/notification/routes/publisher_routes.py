"""Notification Publisher API Routes — Publish events, list published."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications/publisher", tags=["notification-publisher"])


def _get_session():
    from common_lib.modules.integration.adapters.database_adapter import get_db_port
    engine = get_db_port().get_engine()
    return Session(engine)


@router.post("/publish")
def publish_event(
    event_type: str = Query(...),
    topic: str = Query("global"),
    payload: dict = {},
    session: Session = Depends(_get_session),
):
    """Publish a notification event."""
    from common_lib.modules.notification.publisher.service import PublisherService
    svc = PublisherService(session)
    result = svc.publish(event_type=event_type, payload=payload, topic=topic)
    return result


@router.get("/events")
def list_events(
    topic: Optional[str] = Query(None),
    limit: int = Query(50),
    session: Session = Depends(_get_session),
):
    """List published events."""
    from common_lib.modules.notification.publisher.service import PublisherService
    svc = PublisherService(session)
    return {"events": svc.list_published(topic=topic, limit=limit)}


@router.get("/events/{event_id}")
def get_event(event_id: str, session: Session = Depends(_get_session)):
    """Get a published event by ID."""
    from common_lib.modules.notification.publisher.service import PublisherService
    svc = PublisherService(session)
    event = svc.get_published(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event
