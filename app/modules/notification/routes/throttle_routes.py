"""Notification Throttle API Routes — Rate limits and quotas."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications/throttle", tags=["notification-throttle"])


def _get_session():
    from common_lib.modules.integration.adapters.database_adapter import get_db_port
    engine = get_db_port().get_engine()
    return Session(engine)


@router.get("/limits")
def list_limits(session: Session = Depends(_get_session)):
    """List rate limit configurations."""
    from common_lib.modules.notification.throttle.service import ThrottleService
    svc = ThrottleService(session)
    return {"limits": svc.list_limits()}


@router.post("/limits")
def configure_limit(
    key: str = Query(...),
    limit_per_minute: int = Query(60),
    burst_limit: int = Query(10),
    session: Session = Depends(_get_session),
):
    """Configure a rate limit."""
    from common_lib.modules.notification.throttle.service import ThrottleService
    svc = ThrottleService(session)
    return svc.configure_limit(key=key, limit_per_minute=limit_per_minute, burst_limit=burst_limit)


@router.post("/check")
def check_limit(
    key: str = Query(...),
    session: Session = Depends(_get_session),
):
    """Check if a request is allowed under rate limits."""
    from common_lib.modules.notification.throttle.service import ThrottleService
    svc = ThrottleService(session)
    return svc.check_limit(key=key)
