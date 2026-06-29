"""SSE streaming endpoint for the drift alert feed.

Provides real-time Server-Sent Events streaming so the AlertFeedPanel
can show new alerts and remediation events without polling.

Uses the existing ``get_alert_feed()`` function from ``drift_routes.py``
at regular intervals and sends only new events since the last snapshot.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

# How often to poll the DB for new events (seconds)
POLL_INTERVAL = 3.0
# Heartbeat interval (seconds) — keeps the connection alive through proxies
HEARTBEAT_INTERVAL = 15.0


async def alert_feed_event_generator(
    event_type: Optional[str] = None,
    severity: Optional[str] = None,
) -> str:
    """Generator that yields SSE-encoded alert feed events.

    On first connection, sends the full feed snapshot. Then polls every
    ``POLL_INTERVAL`` seconds for new events, sending only events with
    timestamps newer than the previously seen latest timestamp.

    Heartbeats (``: heartbeat`` comments) are sent every
    ``HEARTBEAT_INTERVAL`` to keep the connection alive through proxies
    that might otherwise time out idle connections.

    Args:
        event_type: Optional filter — ``alert`` | ``remediation`` | ``system``.
        severity: Optional filter — ``critical`` | ``high`` | ``medium`` | ``low`` | ``info``.
    """
    # Late import to avoid circular dependency — drift_routes imports from
    # drift_feed_stream so the actual feed function is imported at runtime.
    from app.modules.orchestration.drift_routes import get_alert_feed

    latest_timestamp: Optional[str] = None
    poll_counter = 0

    try:
        # ── Initial full snapshot ───────────────────────────────────
        initial_feed = await get_alert_feed(
            limit=100,
            event_type=event_type,
            severity=severity,
        )
        if initial_feed:
            latest_timestamp = initial_feed[0]["timestamp"]
            for event in initial_feed:
                yield f"event: alert\ndata: {json.dumps(event)}\n\n"

        yield f"event: snapshot_complete\ndata: {json.dumps({'count': len(initial_feed), 'latest_timestamp': latest_timestamp})}\n\n"

        # ── Polling loop ────────────────────────────────────────────
        while True:
            poll_counter += 1

            # Periodic heartbeat
            if poll_counter % int(HEARTBEAT_INTERVAL / POLL_INTERVAL) == 0:
                yield ": heartbeat\n\n"

            await asyncio.sleep(POLL_INTERVAL)

            try:
                feed_since = await get_alert_feed(
                    limit=100,
                    event_type=event_type,
                    severity=severity,
                    since=latest_timestamp,
                )

                if feed_since:
                    # Update latest timestamp from newest event
                    latest_timestamp = feed_since[0]["timestamp"]

                    for event in feed_since:
                        yield f"event: alert\ndata: {json.dumps(event)}\n\n"

            except Exception as exc:
                logger.debug("SSE poll error (non-fatal): %s", exc)
                yield f"event: error\ndata: {json.dumps({'message': str(exc)})}\n\n"

    except asyncio.CancelledError:
        logger.info("SSE alert feed connection closed by client")
    except Exception as exc:
        logger.error("SSE alert feed generator error: %s", exc)
        yield f"event: error\ndata: {json.dumps({'message': str(exc)})}\n\n"


def add_feed_stream_routes(router: APIRouter) -> None:
    """Register the SSE streaming endpoint on the given router.

    Defined as a separate function so it can be called from
    ``drift_routes.py`` after the router is created, avoiding
    circular imports.
    """

    @router.get(
        "/drift/feed/stream",
        summary="SSE stream for real-time alert feed",
        description="Server-Sent Events endpoint that streams drift alerts and auto-remediation events as they occur. Sends an initial full snapshot, then polls for new events every 3 seconds.",
        responses={
            200: {
                "description": "SSE event stream",
                "content": {
                    "text/event-stream": {
                        "schema": {"type": "string"},
                        "example": "event: alert\\ndata: {...}\\n\\nevent: snapshot_complete\\ndata: {...}\\n\\n: heartbeat\\n\\n",
                    }
                },
            }
        },
    )
    async def stream_alert_feed(
        event_type: Optional[str] = None,
        severity: Optional[str] = None,
    ):
        """SSE streaming endpoint for the unified alert feed.

        Args:
            event_type: Optional filter — ``alert`` | ``remediation`` | ``system``.
            severity: Optional filter — ``critical`` | ``high`` | ``medium``  | ``low`` | ``info``.
        """
        return StreamingResponse(
            alert_feed_event_generator(event_type=event_type, severity=severity),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )


__all__ = [
    "add_feed_stream_routes",
    "alert_feed_event_generator",
]
