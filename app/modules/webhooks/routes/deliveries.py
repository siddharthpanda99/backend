"""
Webhook Manager — Delivery Logs CRUD Routes

/api/v1/webhooks/deliveries — list, filter, create, and manage delivery logs
Supports test-sending webhooks and clearing stale logs.
"""

import uuid
import logging
import json
from datetime import datetime, timezone
from typing import Optional
from urllib.request import Request, urlopen
from urllib.error import URLError

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, delete as sql_delete

from common_lib.modules.data_storage.database.connection import get_session
from ..models import WebhookDeliveryRecord, WebhookEndpointRecord
from ..schemas import (
    DeliveryCreate, DeliveryUpdate, DeliveryResponse,
    DeliveryListResponse, TestSendRequest, TestSendResponse, APIResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/deliveries", tags=["Webhook Deliveries"])


@router.get("/", response_model=DeliveryListResponse)
async def list_deliveries(
    endpoint_id: Optional[str] = Query(None),
    direction: Optional[str] = Query(None, pattern=r"^(inbound|outbound)?$"),
    status: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_session),
):
    query = select(WebhookDeliveryRecord).order_by(
        WebhookDeliveryRecord.created_at.desc()
    )

    if endpoint_id:
        query = query.where(WebhookDeliveryRecord.endpoint_id == endpoint_id)
    if direction:
        query = query.where(WebhookDeliveryRecord.direction == direction)
    if status:
        query = query.where(WebhookDeliveryRecord.status == status)
    if event_type:
        query = query.where(WebhookDeliveryRecord.event_type == event_type)

    total = len(db.execute(query).scalars().all())
    items = db.execute(query.offset(offset).limit(limit)).scalars().all()

    return DeliveryListResponse(
        items=[DeliveryResponse.model_validate(d) for d in items],
        total=total,
    )


@router.get("/{delivery_id}", response_model=DeliveryResponse)
async def get_delivery(
    delivery_id: str,
    db: Session = Depends(get_session),
):
    delivery = db.execute(
        select(WebhookDeliveryRecord).where(
            WebhookDeliveryRecord.id == delivery_id
        )
    ).scalar_one_or_none()
    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery not found")
    return DeliveryResponse.model_validate(delivery)


@router.post("/", response_model=DeliveryResponse, status_code=201)
async def create_delivery(
    data: DeliveryCreate,
    db: Session = Depends(get_session),
):
    delivery = WebhookDeliveryRecord(
        id=str(uuid.uuid4()),
        endpoint_id=data.endpoint_id,
        endpoint_name=data.endpoint_name,
        direction=data.direction,
        event_type=data.event_type,
        status=data.status,
        request_url=data.request_url,
        request_headers=data.request_headers,
        request_body=data.request_body,
        response_status=data.response_status,
        response_body=data.response_body,
        error=data.error,
        duration_ms=data.duration_ms,
        attempt=data.attempt,
        max_attempts=data.max_attempts,
    )
    db.add(delivery)
    db.commit()
    db.refresh(delivery)
    return DeliveryResponse.model_validate(delivery)


@router.patch("/{delivery_id}", response_model=DeliveryResponse)
async def update_delivery(
    delivery_id: str,
    data: DeliveryUpdate,
    db: Session = Depends(get_session),
):
    delivery = db.execute(
        select(WebhookDeliveryRecord).where(
            WebhookDeliveryRecord.id == delivery_id
        )
    ).scalar_one_or_none()
    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery not found")

    update_dict = data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(delivery, key, value)

    db.commit()
    db.refresh(delivery)
    return DeliveryResponse.model_validate(delivery)


@router.delete("/", response_model=APIResponse)
async def clear_deliveries(
    endpoint_id: Optional[str] = Query(None),
    db: Session = Depends(get_session),
):
    """Clear delivery logs, optionally filtered by endpoint_id."""
    if endpoint_id:
        db.execute(
            sql_delete(WebhookDeliveryRecord).where(
                WebhookDeliveryRecord.endpoint_id == endpoint_id
            )
        )
        msg = f"Deliveries cleared for endpoint '{endpoint_id}'"
    else:
        db.execute(sql_delete(WebhookDeliveryRecord))
        msg = "All delivery logs cleared"

    db.commit()
    logger.info(msg)
    return APIResponse(success=True, message=msg)


# ─── Test Send ─────────────────────────────────────────────────────


@router.post("/test-send/{endpoint_id}", response_model=TestSendResponse)
async def test_send_webhook(
    endpoint_id: str,
    data: TestSendRequest = TestSendRequest(),
    db: Session = Depends(get_session),
):
    """
    Send a test payload to the webhook endpoint URL.
    Records the delivery attempt in the log.
    """
    ep = db.execute(
        select(WebhookEndpointRecord).where(WebhookEndpointRecord.id == endpoint_id)
    ).scalar_one_or_none()
    if not ep:
        raise HTTPException(status_code=404, detail="Webhook endpoint not found")

    if not ep.url:
        raise HTTPException(status_code=400, detail="Endpoint has no URL configured")

    import time
    start = time.monotonic()

    try:
        payload_bytes = json.dumps(
            data.payload or {
                "event": data.event_type,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "test": True,
            }
        ).encode("utf-8")

        req = Request(
            ep.url,
            data=payload_bytes,
            headers={
                "Content-Type": "application/json",
                "X-Webhook-Test": "true",
                **({} if not ep.secret else {"X-Webhook-Signature": ep.secret[:16]}),
            },
            method="POST",
        )

        with urlopen(req, timeout=10) as response:
            response_body = response.read().decode("utf-8")[:2000]
            duration = (time.monotonic() - start) * 1000

            # Record delivery log
            delivery = WebhookDeliveryRecord(
                id=str(uuid.uuid4()),
                endpoint_id=ep.id,
                endpoint_name=ep.name,
                direction=ep.direction,
                event_type=data.event_type,
                status="success" if 200 <= response.status < 300 else "failed",
                request_url=ep.url,
                request_headers={"Content-Type": "application/json"},
                request_body=payload_bytes.decode("utf-8"),
                response_status=response.status,
                response_body=response_body,
                duration_ms=round(duration, 1),
                attempt=1,
                max_attempts=ep.retry_config.get("max_retries", 3) if ep.retry_config else 3,
            )
            db.add(delivery)
            db.commit()

            success = 200 <= response.status < 300
            return TestSendResponse(
                success=success,
                response_status=response.status,
                duration_ms=round(duration, 1),
            )

    except URLError as e:
        duration = (time.monotonic() - start) * 1000
        error_msg = str(e.reason) if hasattr(e, "reason") else str(e)[:500]

        delivery = WebhookDeliveryRecord(
            id=str(uuid.uuid4()),
            endpoint_id=ep.id,
            endpoint_name=ep.name,
            direction=ep.direction,
            event_type=data.event_type,
            status="failed",
            request_url=ep.url,
            request_headers={"Content-Type": "application/json"},
            request_body=json.dumps(data.payload) if data.payload else '{"event":"test"}',
            error=error_msg,
            duration_ms=round(duration, 1),
            attempt=1,
            max_attempts=ep.retry_config.get("max_retries", 3) if ep.retry_config else 3,
        )
        db.add(delivery)
        db.commit()

        return TestSendResponse(
            success=False,
            error=error_msg,
            duration_ms=round(duration, 1),
        )

    except Exception as e:
        duration = (time.monotonic() - start) * 1000
        error_msg = str(e)[:500]

        delivery = WebhookDeliveryRecord(
            id=str(uuid.uuid4()),
            endpoint_id=ep.id,
            endpoint_name=ep.name,
            direction=ep.direction,
            event_type=data.event_type,
            status="failed",
            request_url=ep.url,
            request_headers={"Content-Type": "application/json"},
            request_body=json.dumps(data.payload) if data.payload else '{"event":"test"}',
            error=error_msg,
            duration_ms=round(duration, 1),
            attempt=1,
            max_attempts=ep.retry_config.get("max_retries", 3) if ep.retry_config else 3,
        )
        db.add(delivery)
        db.commit()

        return TestSendResponse(
            success=False,
            error=error_msg,
            duration_ms=round(duration, 1),
        )
