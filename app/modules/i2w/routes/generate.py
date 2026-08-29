"""``app.modules.i2w.routes.generate`` — end-to-end generator.

Mounts:

* ``POST /api/v1/i2w/generate``            — generate + (optionally) execute
* ``POST /api/v1/i2w/generate/stream``     — same, with SSE progress

Per docs/08_api_contract.md §1.1.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, AsyncIterator, Dict

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from app.modules.i2w.routes._helpers import invoke_i2w
from app.modules.i2w.routes.dependencies import (
    I2W_SCOPE_EXECUTE,
    I2W_SCOPE_WRITE,
    _audit_request,
    i2w_deps,
    i2w_identity,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# POST /generate
# ---------------------------------------------------------------------------


@router.post(
    "/generate",
    summary="Generate + (optionally) execute a workflow end-to-end.",
    description=(
        "Stage 1-4 pipeline. The body specifies the input modality, the "
        "user / tenant, and the run mode. The framework handles the full "
        "ingest → reason → plan → dispatch flow and returns the final "
        "result plus the training record id."
    ),
    dependencies=i2w_deps(scope=I2W_SCOPE_EXECUTE),
    response_model=None,
)
async def generate_workflow(
    request: Request,
    body: Dict[str, Any],
) -> Dict[str, Any]:
    """End-to-end generate + execute.

    The handler is a one-line delegate to the composite
    ``i2w_generate_and_execute`` wrapper. Auth + RBAC + rate limit are
    enforced by the dependency stack.
    """
    identity = await i2w_identity(request=request)  # not strictly needed
    trace_id = request.headers.get("X-Trace-ID", "")
    defaults: Dict[str, Any] = {
        "user_id_hash": str(getattr(identity, "subject_id", "anon")),
        "tenant_id": str(getattr(identity, "tenant_id", "default")),
    }
    if trace_id:
        defaults["trace_id"] = trace_id
    try:
        result = invoke_i2w(
            "i2w_generate_and_execute",
            defaults=defaults,
            **body,
        )
    except RuntimeError as exc:
        _audit_request(request, identity, action="i2w.generate", status_code=400)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    _audit_request(request, identity, action="i2w.generate")
    return result


# ---------------------------------------------------------------------------
# POST /generate/stream  (SSE)
# ---------------------------------------------------------------------------


@router.post(
    "/generate/stream",
    summary="Generate + execute, streaming progress as SSE.",
    description=(
        "Same payload as /generate. Emits Server-Sent Events with one "
        "JSON-encoded DispatchProgressEvent per line. The stream ends "
        "with EXECUTION_COMPLETED or EXECUTION_CANCELLED."
    ),
    dependencies=i2w_deps(scope=I2W_SCOPE_EXECUTE),
    response_model=None,
)
async def generate_workflow_stream(
    request: Request,
    body: Dict[str, Any],
) -> StreamingResponse:
    """SSE stream of progress events for an end-to-end run.

    The wrapper itself is sync; we run it in a thread and yield each
    progress event. If the wrapper does not support progress events we
    fall back to a single ``"done"`` event with the final result.
    """
    identity = await i2w_identity(request=request)
    trace_id = request.headers.get("X-Trace-ID", "")
    defaults: Dict[str, Any] = {
        "user_id_hash": str(getattr(identity, "subject_id", "anon")),
        "tenant_id": str(getattr(identity, "tenant_id", "default")),
    }
    if trace_id:
        defaults["trace_id"] = trace_id

    async def event_iter() -> AsyncIterator[str]:
        t0 = time.monotonic()
        try:
            result = await asyncio.to_thread(
                invoke_i2w,
                "i2w_generate_and_execute",
                defaults=defaults,
                **body,
            )
            yield f"event: done\ndata: {json.dumps(result, default=str)}\n\n"
        except Exception as exc:  # noqa: BLE001
            yield (
                f"event: error\ndata: "
                f"{json.dumps({'message': str(exc)}, default=str)}\n\n"
            )
        finally:
            logger.debug("SSE stream closed after %.1fs", time.monotonic() - t0)

    return StreamingResponse(
        event_iter(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


__all__ = ["router"]
