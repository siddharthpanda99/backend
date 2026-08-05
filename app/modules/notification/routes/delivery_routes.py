"""Notification Delivery API Routes — Attempts, DLQ, retry policies."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications/delivery", tags=["notification-delivery"])


def _get_session():
    from common_lib.modules.integration.adapters.database_adapter import get_db_port
    engine = get_db_port().get_engine()
    return Session(engine)


@router.get("/attempts/{event_id}")
def get_attempts(
    event_id: str,
    limit: int = Query(10),
    session: Session = Depends(_get_session),
):
    """Get delivery attempts for an event."""
    from common_lib.modules.notification.delivery.service import DeliveryService
    svc = DeliveryService(session)
    return {"attempts": svc.get_attempts(event_id=event_id, limit=limit)}


@router.get("/dlq")
def list_dlq(
    status: Optional[str] = Query(None),
    limit: int = Query(50),
    session: Session = Depends(_get_session),
):
    """List dead letter queue entries."""
    from common_lib.modules.notification.delivery.service import DeliveryService
    svc = DeliveryService(session)
    return {"entries": svc.dlq.list(status=status, limit=limit), "count": svc.dlq.count()}


@router.post("/dlq/{entry_id}/retry")
def retry_dlq(entry_id: str, session: Session = Depends(_get_session)):
    """Retry a dead letter queue entry."""
    from common_lib.modules.notification.delivery.service import DeliveryService
    svc = DeliveryService(session)
    result = svc.dlq.retry(entry_id)
    if not result:
        raise HTTPException(status_code=404, detail="DLQ entry not found")
    return result


@router.post("/retry-policies")
def create_retry_policy(
    name: str = Query(...),
    max_attempts: int = Query(3),
    session: Session = Depends(_get_session),
):
    """Create a retry policy."""
    from common_lib.modules.notification.delivery.service import DeliveryService
    svc = DeliveryService(session)
    return svc.create_retry_policy(name=name, max_attempts=max_attempts)
