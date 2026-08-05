"""Notification Deduplication API Routes — Dedup rules and checking."""

from __future__ import annotations

import logging
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications/dedup", tags=["notification-dedup"])


def _get_session():
    from common_lib.modules.integration.adapters.database_adapter import get_db_port
    engine = get_db_port().get_engine()
    return Session(engine)


@router.get("/rules")
def list_rules(session: Session = Depends(_get_session)):
    """List deduplication rules."""
    from common_lib.modules.notification.deduplication.service import DeduplicationService
    svc = DeduplicationService(session)
    return {"rules": svc.list_rules()}


@router.post("/rules")
def create_rule(
    name: str = Query(...),
    notification_type: str = Query(...),
    strategy: str = Query("content_hash"),
    window_seconds: int = Query(300),
    session: Session = Depends(_get_session),
):
    """Create a deduplication rule."""
    from common_lib.modules.notification.deduplication.service import DeduplicationService
    svc = DeduplicationService(session)
    return svc.configure_rule(name=name, notification_type=notification_type, strategy=strategy, window_seconds=window_seconds)


@router.post("/check")
def check_duplicate(
    notification_type: str = Query(...),
    payload: dict = {},
    session: Session = Depends(_get_session),
):
    """Check if a notification is a duplicate."""
    from common_lib.modules.notification.deduplication.service import DeduplicationService
    svc = DeduplicationService(session)
    return svc.is_duplicate(notification_type=notification_type, payload=payload)
