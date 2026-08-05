"""Notification Routing API Routes — Route rules and channel priority."""

from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications/routing", tags=["notification-routing"])


def _get_session():
    from common_lib.modules.integration.adapters.database_adapter import get_db_port
    engine = get_db_port().get_engine()
    return Session(engine)


@router.get("/rules")
def list_rules(
    notification_type: Optional[str] = Query(None),
    session: Session = Depends(_get_session),
):
    """List route rules."""
    from common_lib.modules.notification.routing.service import RoutingService
    svc = RoutingService(session)
    return {"rules": svc.list_rules(notification_type=notification_type)}


@router.post("/rules")
def create_rule(
    name: str = Query(...),
    notification_type: str = Query(...),
    channel_order: str = Query("in_app,email,push"),
    priority: str = Query("medium"),
    session: Session = Depends(_get_session),
):
    """Create a route rule."""
    from common_lib.modules.notification.routing.service import RoutingService
    svc = RoutingService(session)
    return svc.create_route_rule(
        name=name, notification_type=notification_type,
        channel_order=[c.strip() for c in channel_order.split(",")],
        priority=priority,
    )


@router.get("/resolve")
def resolve_channels(
    notification_type: str = Query(...),
    session: Session = Depends(_get_session),
):
    """Resolve channel order for a notification type."""
    from common_lib.modules.notification.routing.service import RoutingService
    svc = RoutingService(session)
    return svc.resolve_channels(notification_type=notification_type)


@router.post("/channel-priority")
def set_channel_priority(
    tenant_id: str = Query(...),
    channel: str = Query(...),
    priority_order: int = Query(0),
    session: Session = Depends(_get_session),
):
    """Set channel priority for a tenant."""
    from common_lib.modules.notification.routing.service import RoutingService
    svc = RoutingService(session)
    return svc.set_channel_priority(tenant_id=tenant_id, channel=channel, priority_order=priority_order)
