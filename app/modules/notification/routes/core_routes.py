"""Notification Core API Routes — Topic registry, schema management."""

from __future__ import annotations

import logging
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications/core", tags=["notification-core"])


def _get_session():
    from common_lib.modules.integration.adapters.database_adapter import get_db_port
    engine = get_db_port().get_engine()
    return Session(engine)


@router.get("/topics")
def list_topics(
    active_only: bool = Query(True),
    session: Session = Depends(_get_session),
):
    """List all notification topics."""
    from common_lib.modules.notification.core.service import TopicRegistry
    reg = TopicRegistry(session)
    return {"topics": reg.list_topics(active_only=active_only)}


@router.post("/topics")
def create_topic(
    name: str = Query(...),
    description: str = Query(""),
    session: Session = Depends(_get_session),
):
    """Create a notification topic."""
    from common_lib.modules.notification.core.service import TopicRegistry
    reg = TopicRegistry(session)
    result = reg.register_topic(name=name, description=description)
    return result


@router.get("/schemas")
def list_schemas(
    active_only: bool = Query(True),
    session: Session = Depends(_get_session),
):
    """List all event schemas."""
    from common_lib.modules.notification.core.service import SchemaRegistry
    reg = SchemaRegistry(session)
    return {"schemas": reg.list_schemas(active_only=active_only)}


@router.post("/schemas")
def create_schema(
    event_type: str = Query(...),
    version: str = Query("1.0.0"),
    session: Session = Depends(_get_session),
):
    """Register an event schema."""
    from common_lib.modules.notification.core.service import SchemaRegistry
    reg = SchemaRegistry(session)
    result = reg.register_schema(event_type=event_type, version=version)
    return result
