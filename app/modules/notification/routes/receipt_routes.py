"""Notification Receipts API Routes — Delivery receipts and engagement."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications/receipts", tags=["notification-receipts"])


def _get_session():
    from common_lib.modules.integration.adapters.database_adapter import get_db_port
    engine = get_db_port().get_engine()
    return Session(engine)


@router.get("/{delivery_id}")
def get_receipt(delivery_id: str, session: Session = Depends(_get_session)):
    """Get delivery receipt for a delivery."""
    from common_lib.modules.notification.receipts.service import ReceiptService
    svc = ReceiptService(session)
    receipt = svc.get_receipt(delivery_id=delivery_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    return receipt


@router.post("/{delivery_id}/read")
def mark_read(delivery_id: str, session: Session = Depends(_get_session)):
    """Mark a delivery as read."""
    from common_lib.modules.notification.receipts.service import ReceiptService
    svc = ReceiptService(session)
    success = svc.record_read(delivery_id=delivery_id)
    if not success:
        raise HTTPException(status_code=404, detail="Delivery not found")
    return {"success": True}


@router.get("/stats/{notification_id}")
def receipt_stats(notification_id: str, session: Session = Depends(_get_session)):
    """Get receipt statistics for a notification."""
    from common_lib.modules.notification.receipts.service import ReceiptService
    svc = ReceiptService(session)
    return svc.get_stats(notification_id=notification_id)
