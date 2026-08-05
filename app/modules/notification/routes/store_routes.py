"""Notification Event Store API Routes — Event persistence and replay."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications/store", tags=["notification-store"])


def _get_session():
    from common_lib.modules.integration.adapters.database_adapter import get_db_port
    engine = get_db_port().get_engine()
    return Session(engine)


@router.get("/events")
def query_events(
    event_type: Optional[str] = Query(None),
    topic: Optional[str] = Query(None),
    limit: int = Query(100),
    offset: int = Query(0),
    session: Session = Depends(_get_session),
):
    """Query stored events."""
    from common_lib.modules.notification.event_store.service import EventStoreService
    svc = EventStoreService(session)
    return svc.query(event_type=event_type, topic=topic, limit=limit, offset=offset)


@router.get("/stats")
def store_stats(session: Session = Depends(_get_session)):
    """Get event store statistics."""
    from common_lib.modules.notification.event_store.service import EventStoreService
    svc = EventStoreService(session)
    return svc.stats()
