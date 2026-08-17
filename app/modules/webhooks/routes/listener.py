"""
Webhook Manager — Inbound Webhook Listener

/api/v1/webhooks/in/{slug} — Accept events from external systems (GitHub, GitLab, Stripe, etc.)
routes them to the EventRouter and WorkflowMapper for processing.
"""

import hashlib
import hmac
import logging
import time
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import select

from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.integration.events.event_models import (
    PlatformEvent,
    EventSource,
    EventSeverity,
)
from common_lib.modules.integration.events.workflow_mapper import get_workflow_mapper
from common_lib.modules.integration.core.event_router import get_event_router
from ..models import WebhookEndpointRecord, WebhookDeliveryRecord
from ..schemas import InboundEventRequest, InboundEventResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/in", tags=["Webhook Listener"])


@router.post("/{slug:path}", response_model=InboundEventResponse)
async def receive_inbound_webhook(
    slug: str,
    request: Request,
    db: Session = Depends(get_session),
):
    """
    Receive events from external systems (GitHub, GitLab, Stripe, Slack, etc.).

    Matches the request to a configured inbound webhook endpoint by URL slug.
    Verifies HMAC signature if the endpoint has a secret configured.
    Routes the event to connected workflows and the integration EventRouter.
    """
    endpoint_path = f"/api/v1/webhooks/in/{slug}"

    ep = db.execute(
        select(WebhookEndpointRecord).where(
            WebhookEndpointRecord.url == endpoint_path,
            WebhookEndpointRecord.direction == "inbound",
            WebhookEndpointRecord.enabled == True,
        )
    ).scalar_one_or_none()

    if not ep:
        raise HTTPException(
            status_code=404, detail="No inbound endpoint found for this path"
        )

    try:
        body = await request.json()
    except Exception:
        body = {}

    raw_headers = dict(request.headers)

    if ep.secret:
        if not _verify_signature(body, raw_headers, ep.secret):
            _record_delivery(db, ep, "inbound", "verification.failed", body, 401)
            raise HTTPException(status_code=401, detail="Invalid signature")

    event_type = (
        body.get("event_type")
        or body.get("event")
        or body.get("action")
        or "webhook.received"
    )
    headers = {k: v for k, v in raw_headers.items() if k.lower().startswith("x-")}

    platform_event = PlatformEvent(
        event_type=event_type,
        source=EventSource.WEBHOOK,
        payload=body,
        metadata={
            "endpoint_id": ep.id,
            "endpoint_name": ep.name,
            "slug": slug,
            "headers": headers,
        },
        severity=EventSeverity.INFO,
        timestamp=time.time(),
    )

    _record_delivery(db, ep, "inbound", event_type, body, 200)

    ep.last_triggered_at = datetime.now(timezone.utc)
    db.commit()

    try:
        event_router = get_event_router()
        await event_router.fire_event(
            event_type=event_type,
            data=body,
            channel="webhook",
            source="webhook",
            metadata={"endpoint_id": ep.id, "endpoint_name": ep.name},
        )
    except Exception as e:
        logger.warning(f"EventRouter dispatch failed: {e}")

    try:
        workflow_mapper = get_workflow_mapper()
        results = await workflow_mapper.route_event(platform_event)
        workflows_triggered = len(
            [r for r in results if r.get("status") == "triggered"]
        )
    except Exception as e:
        logger.warning(f"WorkflowMapper dispatch failed: {e}")
        workflows_triggered = 0

    return InboundEventResponse(
        success=True,
        event_id=platform_event.id,
        workflows_triggered=workflows_triggered,
        message=f"Event '{event_type}' processed",
    )


def _verify_signature(
    body: dict,
    headers: dict,
    secret: str,
) -> bool:
    signature = (
        headers.get("x-webhook-signature")
        or headers.get("x-hub-signature-256")
        or headers.get("x-signature-256")
    )
    if not signature:
        return False

    import json

    payload_bytes = json.dumps(body, sort_keys=True).encode("utf-8")
    expected = hmac.new(
        secret.encode("utf-8"), payload_bytes, hashlib.sha256
    ).hexdigest()

    if signature.startswith("sha256="):
        signature = signature[7:]

    return hmac.compare_digest(expected, signature)


def _record_delivery(
    db: Session,
    ep: WebhookEndpointRecord,
    direction: str,
    event_type: str,
    body: dict,
    status_code: int,
):
    import json
    import uuid

    delivery = WebhookDeliveryRecord(
        id=str(uuid.uuid4()),
        endpoint_id=ep.id,
        endpoint_name=ep.name,
        direction=direction,
        event_type=event_type,
        status="success" if 200 <= status_code < 300 else "failed",
        request_url=ep.url,
        request_headers=None,
        request_body=json.dumps(body)[:5000],
        response_status=status_code,
        attempt=1,
        max_attempts=3,
    )
    db.add(delivery)
    db.commit()
