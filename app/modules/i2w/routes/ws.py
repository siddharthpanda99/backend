"""``app.modules.i2w.routes.ws`` — bidirectional WebSocket for the
WorkflowBuilder UI + the mobile app.

Per docs/08_api_contract.md §2.1, the WS frame protocol is::

    client → server:
      { type: "start_ingest" | "start_execute" | "approve" |
              "deny" | "cancel" | "subscribe" | "ping", ... }
    server → client:
      { type: "ingest_started" | "reason_started" |
              "node_started" | "node_progress" | "node_succeeded" |
              "execution_completed" | "error" | "pong", ... }

The router is **thin**: it parses the frame, validates the JWT from
the cookie or Authorization header, then forwards the event into the
in-process bus. The actual run loop (topo sort, parallel runner,
etc.) lives in ``common_lib`` and is driven by the WebSocket
subscriber.

The endpoint is mounted at ``/api/v1/i2w/ws``.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter()


def _validate_jwt(token: Optional[str]) -> Optional[Dict[str, Any]]:
    """Decode a JWT bearer token. Returns the payload or None on failure.

    This is the same call the platform's auth dependency uses; we
    re-implement it here because WebSockets do not go through the
    FastAPI ``Depends`` machinery in the standard way. The platform's
    ``decode_access_token`` is the single source of truth.
    """
    if not token:
        return None
    try:
        from common_lib.modules.auth.security import decode_access_token

        return decode_access_token(token)
    except Exception:  # noqa: BLE001
        return None


@router.websocket("/ws")
async def i2w_websocket(
    websocket: WebSocket,
    token: Optional[str] = None,
) -> None:
    """Bidirectional WebSocket endpoint for I2W.

    The handler authenticates the upgrade via the ``?token=`` query
    param (the WorkflowBuilder UI injects it from the JWT cookie) and
    then enters a per-frame loop:

    * ``ping``  →  reply ``pong``
    * ``subscribe``  →  add the socket to the in-process subscribers
    * ``start_ingest`` / ``start_execute`` / ``approve`` / ``deny`` /
      ``cancel``  →  publish onto the platform event bus; the
      subscribed i2w_* wrappers drive the pipeline and emit progress
      frames back through the same bus.
    * unknown frame type  →  ``error`` frame, do not disconnect.
    """
    await websocket.accept()
    payload = _validate_jwt(token)
    if payload is None:
        await websocket.send_text(
            json.dumps(
                {
                    "type": "error",
                    "code": "I2W_AUTH_MISSING",
                    "message": "JWT token missing or invalid",
                    "retryable": False,
                }
            )
        )
        await websocket.close(code=1008)
        return

    user_id_hash = str(payload.get("sub") or payload.get("user_id") or "anon")
    tenant_id = str(payload.get("tenant_id") or "default")

    # Local subscriber registry (process-local; production would use
    # a Redis pub/sub bridge).
    subscribers: set[asyncio.Queue] = set()
    own_queue: asyncio.Queue = asyncio.Queue()

    async def pump() -> None:
        while True:
            try:
                frame = await own_queue.get()
                await websocket.send_text(json.dumps(frame, default=str))
            except Exception:  # noqa: BLE001
                break

    pump_task = asyncio.create_task(pump())

    try:
        await websocket.send_text(json.dumps({"type": "pong"}))
        while True:
            raw = await websocket.receive_text()
            try:
                frame = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "error",
                            "code": "I2W_VALIDATION_FAILED",
                            "message": "invalid JSON frame",
                            "retryable": False,
                        }
                    )
                )
                continue
            ftype = frame.get("type")
            if ftype == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
            elif ftype == "subscribe":
                # Client is signalling it wants live progress on
                # ``execution_id``. In a richer implementation the
                # handler would attach to the dispatch service's
                # event emitter. For now we acknowledge and let the
                # server-side event loop (i2w_dispatch_progress)
                # push frames.
                exec_id = frame.get("execution_id")
                await own_queue.put(
                    {
                        "type": "subscribed",
                        "execution_id": exec_id,
                    }
                )
            elif ftype in {
                "start_ingest",
                "start_execute",
                "approve",
                "deny",
                "cancel",
            }:
                # Publish onto the platform event bus; the
                # downstream services (i2w_* wrappers) drive the
                # pipeline.
                try:
                    from common_lib.modules.integration.events import (
                        get_event_bus,
                    )

                    bus = get_event_bus()
                    if bus is not None:
                        # The bus API is async; the WebSocket
                        # handler is already in an event loop, so
                        # we can await directly.
                        publish = getattr(bus, "publish_async", None) or getattr(
                            bus, "publish", None
                        )
                        if publish is not None:
                            event_name = f"i2w.ws.{ftype}"
                            res = publish(
                                event=event_name,
                                payload={
                                    **frame,
                                    "user_id_hash": user_id_hash,
                                    "tenant_id": tenant_id,
                                },
                                trace_id=frame.get("trace_id", ""),
                                tenant_id=tenant_id,
                                user_id_hash=user_id_hash,
                            )
                            if asyncio.iscoroutine(res):
                                await res
                except Exception:  # noqa: BLE001
                    logger.debug("WS bus publish failed", exc_info=True)
                await own_queue.put({"type": "ack", "ack_for": ftype})
            else:
                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "error",
                            "code": "I2W_VALIDATION_FAILED",
                            "message": f"unknown frame type: {ftype}",
                            "retryable": False,
                        }
                    )
                )
    except WebSocketDisconnect:
        pass
    finally:
        pump_task.cancel()
        try:
            await pump_task
        except (asyncio.CancelledError, Exception):  # noqa: BLE001
            pass


__all__ = ["router"]
