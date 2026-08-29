"""``app.modules.i2w.routes.reason`` — Stage 2 reasoning endpoint.

Mounts (per docs/08_api_contract.md §1.2):

* ``POST /api/v1/i2w/reason``
* ``GET  /api/v1/i2w/health/reason``   (defined in routes/health.py)
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request, status

from app.modules.i2w.routes._helpers import invoke_i2w
from app.modules.i2w.routes.dependencies import (
    I2W_SCOPE_WRITE,
    _audit_request,
    i2w_deps,
    i2w_identity,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/reason",
    summary="Stage 2 — reason over a raw instruction.",
    description=(
        "Body: { raw_instruction, model? }. Returns a ``ReasoningResult`` "
        "with extracted steps, dependencies, confidences, and (optional) "
        "ambiguities. Delegates to ``i2w_reason``."
    ),
    dependencies=i2w_deps(scope=I2W_SCOPE_WRITE, stage="reason"),
    response_model=None,
)
async def reason(request: Request, body: Dict[str, Any]) -> Dict[str, Any]:
    identity = await i2w_identity(request=request)
    trace_id = request.headers.get("X-Trace-ID", "")
    defaults: Dict[str, Any] = {
        "user_id_hash": str(getattr(identity, "subject_id", "anon")),
        "tenant_id": str(getattr(identity, "tenant_id", "default")),
    }
    if trace_id:
        defaults["trace_id"] = trace_id
    try:
        result = invoke_i2w("i2w_reason", defaults=defaults, **body)
    except RuntimeError as exc:
        _audit_request(request, identity, action="i2w.reason", status_code=400)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    _audit_request(request, identity, action="i2w.reason")
    return result


__all__ = ["router"]
