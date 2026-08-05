"""Notification Bus API Routes — Topics, consumer groups."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications/bus", tags=["notification-bus"])


def _get_session():
    from common_lib.modules.integration.adapters.database_adapter import get_db_port
    engine = get_db_port().get_engine()
    return Session(engine)


@router.get("/topics")
def list_topics(session: Session = Depends(_get_session)):
    """List bus topics."""
    from common_lib.modules.notification.bus.service import EventBus
    bus = EventBus(session)
    return {"topics": bus.list_topics()}


@router.post("/topics")
def create_topic(
    name: str = Query(...),
    description: str = Query(""),
    partitions: int = Query(1),
    session: Session = Depends(_get_session),
):
    """Create a bus topic."""
    from common_lib.modules.notification.bus.service import EventBus
    bus = EventBus(session)
    return bus.create_topic(name=name, description=description, partitions=partitions)


@router.get("/consumer-groups")
def list_consumer_groups(
    topic_id: Optional[str] = Query(None),
    session: Session = Depends(_get_session),
):
    """List consumer groups."""
    from common_lib.modules.notification.bus.service import EventBus
    bus = EventBus(session)
    return {"consumer_groups": bus.list_consumer_groups(topic_id=topic_id)}


@router.post("/consumer-groups")
def create_consumer_group(
    name: str = Query(...),
    topic_id: str = Query(...),
    session: Session = Depends(_get_session),
):
    """Create a consumer group."""
    from common_lib.modules.notification.bus.service import EventBus
    bus = EventBus(session)
    return bus.create_consumer_group(name=name, topic_id=topic_id)
