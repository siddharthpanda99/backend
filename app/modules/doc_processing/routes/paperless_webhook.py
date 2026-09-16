"""Paperless-ngx webhook ingestion router (W5-L01).

Receives post-consume events from the paperless-webserver container hook,
validates HMAC signature or shared secret, and queues background processing.
"""

from __future__ import annotations

import os
from typing import Any, Dict

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request, status

from app.modules.doc_processing.services.paperless_sync import handle_paperless_post_consume
from common_lib.modules.doc_processing.config.flags import (
    PAPERLESS_INTEGRATION_ENABLED,
    is_enabled,
)
from common_lib.modules.doc_processing.paperless_client.events import (
    PaperlessPostConsumePayload,
)

router = APIRouter(prefix="/paperless", tags=["Paperless DMS Webhook"])


@router.post(
    "/webhook",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Paperless-ngx Post-Consume Webhook Receiver",
    response_model=Dict[str, Any],
)
async def paperless_post_consume_webhook(
    request: Request,
    payload: PaperlessPostConsumePayload,
    background_tasks: BackgroundTasks,
    x_paperless_webhook_secret: str | None = Header(default=None),
) -> Dict[str, Any]:
    """Handle post-consume notification sent by Paperless-ngx post-consume.sh script."""
    if not is_enabled(PAPERLESS_INTEGRATION_ENABLED):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Paperless integration is currently disabled via feature flag.",
        )

    expected_secret = os.environ.get("PLATFORM_WEBHOOK_SECRET", "paperless-platform-shared-secret")
    if expected_secret and x_paperless_webhook_secret != expected_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-Paperless-Webhook-Secret header.",
        )

    # Dispatch to background task to respond immediately to Paperless script
    background_tasks.add_task(handle_paperless_post_consume, payload)

    return {
        "status": "ACCEPTED",
        "document_id": payload.document_id,
        "message": "Queued for deep extraction and RIP synchronization.",
    }
