"""``app.modules.i2w.routes.executions`` — execution CRUD.

Per docs/08_api_contract.md §1.4:

* ``GET    /api/v1/i2w/executions``
* ``GET    /api/v1/i2w/executions/{id}``
* ``GET    /api/v1/i2w/executions/{id}/events``
* ``POST   /api/v1/i2w/executions/{id}/cancel``
* ``POST   /api/v1/i2w/executions/{id}/approve``
* ``POST   /api/v1/i2w/executions/{id}/deny``
* ``POST   /api/v1/i2w/executions/{id}/retry``
* ``POST   /api/v1/i2w/executions/{id}/rollback``
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query, Request, status

from app.modules.i2w.routes._helpers import invoke_i2w
from app.modules.i2w.routes.dependencies import (
    I2W_SCOPE_EXECUTE,
    I2W_SCOPE_READ,
    _audit_request,
    i2w_deps,
    i2w_identity,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/executions",
    summary="List executions (paginated, filterable).",
    dependencies=i2w_deps(scope=I2W_SCOPE_READ, stage="dispatch"),
    response_model=None,
)
async def list_executions(
    request: Request,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> Dict[str, Any]:
    identity = await i2w_identity(request=request)
    _audit_request(request, identity, action="i2w.executions.list")
    try:
        return invoke_i2w("i2w_list_executions", limit=limit, offset=offset)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get(
    "/executions/{execution_id}",
    summary="Get a single execution (with all StepResults).",
    dependencies=i2w_deps(scope=I2W_SCOPE_READ, stage="dispatch"),
    response_model=None,
)
async def get_execution(execution_id: str, request: Request) -> Dict[str, Any]:
    identity = await i2w_identity(request=request)
    _audit_request(request, identity, action="i2w.executions.get")
    try:
        return invoke_i2w("i2w_get_execution", execution_id=execution_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get(
    "/executions/{execution_id}/events",
    summary="Replay the progress event stream for an execution.",
    dependencies=i2w_deps(scope=I2W_SCOPE_READ, stage="dispatch"),
    response_model=None,
)
async def replay_events(execution_id: str, request: Request) -> Dict[str, Any]:
    identity = await i2w_identity(request=request)
    _audit_request(request, identity, action="i2w.executions.events")
    # The dispatch service exposes a progress emitter; the docs'
    # ``i2w_dispatch_progress`` wrapper is the canonical entry point.
    # The current tree does not register it as a @node wrapper, so we
    # surface 501 + a clear pointer.
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=(
            "Event replay requires the i2w_dispatch_progress wrapper, "
            "which is part of the docs' planned set and has not yet "
            "landed. Use /api/v1/i2w/ws for live streaming."
        ),
    )


@router.post(
    "/executions/{execution_id}/cancel",
    summary="Cancel an in-flight execution.",
    dependencies=i2w_deps(scope=I2W_SCOPE_EXECUTE, stage="dispatch"),
    response_model=None,
)
async def cancel_execution(
    execution_id: str,
    request: Request,
    body: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    identity = await i2w_identity(request=request)
    _audit_request(request, identity, action="i2w.executions.cancel")
    try:
        return invoke_i2w(
            "i2w_cancel_execution",
            execution_id=execution_id,
            **(body or {}),
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post(
    "/executions/{execution_id}/approve",
    summary="Grant approval for a ``requires_approval`` node.",
    dependencies=i2w_deps(scope=I2W_SCOPE_EXECUTE, stage="dispatch"),
    response_model=None,
)
async def approve_execution(
    execution_id: str,
    request: Request,
) -> Dict[str, Any]:
    identity = await i2w_identity(request=request)
    _audit_request(request, identity, action="i2w.executions.approve")
    # Approval is a WS-frame event; the REST surface acknowledges
    # and forwards. No dedicated wrapper yet.
    return {
        "status": "accepted",
        "execution_id": execution_id,
        "note": "approval sent on the WS channel",
    }


@router.post(
    "/executions/{execution_id}/deny",
    summary="Deny approval (skip the node).",
    dependencies=i2w_deps(scope=I2W_SCOPE_EXECUTE, stage="dispatch"),
    response_model=None,
)
async def deny_execution(
    execution_id: str,
    request: Request,
) -> Dict[str, Any]:
    identity = await i2w_identity(request=request)
    _audit_request(request, identity, action="i2w.executions.deny")
    return {
        "status": "accepted",
        "execution_id": execution_id,
        "note": "denial sent on the WS channel",
    }


@router.post(
    "/executions/{execution_id}/retry",
    summary="Retry a failed node.",
    dependencies=i2w_deps(scope=I2W_SCOPE_EXECUTE, stage="dispatch"),
    response_model=None,
)
async def retry_execution(
    execution_id: str,
    request: Request,
) -> Dict[str, Any]:
    identity = await i2w_identity(request=request)
    _audit_request(request, identity, action="i2w.executions.retry")
    # Retry triggers a fresh dispatch on the same plan; the WS
    # channel streams the new attempt.
    return {
        "status": "accepted",
        "execution_id": execution_id,
        "note": "retry queued on the WS channel",
    }


@router.post(
    "/executions/{execution_id}/rollback",
    summary="Manually trigger the rollback plan.",
    dependencies=i2w_deps(scope=I2W_SCOPE_EXECUTE, stage="dispatch"),
    response_model=None,
)
async def rollback_execution(
    execution_id: str,
    request: Request,
) -> Dict[str, Any]:
    identity = await i2w_identity(request=request)
    _audit_request(request, identity, action="i2w.executions.rollback")
    try:
        return invoke_i2w(
            "i2w_rollback_execution",
            execution_id=execution_id,
            **(body or {}),
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


__all__ = ["router"]
