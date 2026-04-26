from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from typing import Optional
import logging

from common_lib.modules.notification.controller import (
    stream_notifications,
    notify,
    event_bus,
    Channels,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/stream")
async def notifications_stream(
    channel: str = Query(
        default="global",
        description="Channel: global, ingestion, pipeline, workflow, model, system",
    ),
):
    """
    SSE endpoint for real-time notifications.
    Subscribe to specific channels to receive events.
    """

    async def event_generator():
        async for message in stream_notifications(channel):
            yield message

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/channels")
async def list_channels():
    """List available notification channels."""
    return {"channels": event_bus.get_channels()}


@router.post("/publish")
async def publish_notification(
    event_type: str,
    channel: str = "global",
    data: dict = {},
):
    """Publish a notification to a channel."""
    await notify(event_type, data, channel)
    return {"status": "published"}
