"""``app.modules.i2w.routes.dispatch`` — Stage 4 dispatch endpoints.

Mounts (per docs/08_api_contract.md §1.2 + §1.4):

* ``POST /api/v1/i2w/dispatch``
* ``POST /api/v1/i2w/dispatch/{execution_id}/cancel``
* ``GET  /api/v1/i2w/health/dispatch``   (in routes/health.py)

The execution CRUD (list, get, events, approve, deny, retry, rollback)
lives in ``routes/executions.py`` because it operates on a different
HTTP resource.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request, status

from app.modules.i2w.routes._helpers import invoke_i2w
from app.modules.i2w.routes.dependencies import (
    I2W_SCOPE_EXECUTE,
    _audit_request,
    i2w_deps,
    i2w_identity,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/dispatch",
    summary="Stage 4 — execute a frozen WorkflowPlan.",
    description=(
        "Body: { plan, user_id_hash, tenant_id?, max_concurrent_nodes?, "
        "auto_rollback?, dry_run? }. Returns the final ``WorkflowExecution``."
    ),
    dependencies=i2w_deps(scope=I2W_SCOPE_EXECUTE, stage="dispatch"),
    response_model=None,
)
async def dispatch(request: Request, body: Dict[str, Any]) -> Dict[str, Any]:
    identity = await i2w_identity(request=request)
    trace_id = request.headers.get("X-Trace-ID", "")
    defaults: Dict[str, Any] = {
        "user_id_hash": str(getattr(identity, "subject_id", "anon")),
        "tenant_id": str(getattr(identity, "tenant_id", "default")),
    }
    if trace_id:
        defaults["trace_id"] = trace_id
    try:
        result = invoke_i2w("i2w_execute", defaults=defaults, **body)
    except RuntimeError as exc:
        _audit_request(request, identity, action="i2w.dispatch", status_code=400)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    _audit_request(request, identity, action="i2w.dispatch")
    return result


@router.post(
    "/dispatch/{execution_id}/cancel",
    summary="Cancel an in-flight execution.",
    dependencies=i2w_deps(scope=I2W_SCOPE_EXECUTE, stage="dispatch"),
    response_model=None,
)
async def cancel_dispatch(
    execution_id: str,
    request: Request,
    body: Dict[str, Any] = {},
) -> Dict[str, Any]:
    identity = await i2w_identity(request=request)
    _audit_request(request, identity, action="i2w.dispatch.cancel")
    try:
        return invoke_i2w(
            "i2w_cancel_execution",
            execution_id=execution_id,
            **body,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


__all__ = ["router"]
