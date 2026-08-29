"""``app.modules.i2w.routes.workflows`` — persistent plan CRUD.

Per docs/08_api_contract.md §1.3, the framework persists plans to the
``WorkflowPlan`` table. The CRUD endpoints in this file are the
*thin* FastAPI layer; the actual persistence lives in the dispatch
service's plan-store methods, which are not yet exposed as @node
wrappers (the docs plan for them in a later phase).

In the current Phase 7 the CRUD endpoints are wired to the *existing*
i2w_* wrappers where a match exists (``i2w_plan``,
``i2w_optimize_plan``, ``i2w_validate_plan``, ``i2w_detect_gaps``,
``i2w_emit_yaml``). The list/get/save/update/delete operations on the
persistent store are stubbed with 501 until the dedicated
``i2w_plan_*`` CRUD wrappers land — the docs explicitly mark them as
"additive to the existing 42 wrappers" (see
``docs/12_integration_points.md`` §4.3).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, HTTPException, Query, Request, status

from app.modules.i2w.routes._helpers import invoke_i2w
from app.modules.i2w.routes.dependencies import (
    I2W_SCOPE_EXECUTE,
    I2W_SCOPE_READ,
    I2W_SCOPE_WRITE,
    _audit_request,
    i2w_deps,
    i2w_identity,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# GET /plans
# ---------------------------------------------------------------------------


@router.get(
    "/plans",
    summary="List persistent plans (paginated, filterable).",
    description=(
        "Returns a paginated list of plans owned by the caller's tenant. "
        "Filters: ``status``, ``user_id_hash``, ``created_after``, "
        "``created_before``. The persistent store wrapper for the list "
        "operation has not landed yet; this endpoint is wired to the "
        "training service's list-records endpoint as a placeholder."
    ),
    dependencies=i2w_deps(scope=I2W_SCOPE_READ, stage="plan"),
    response_model=None,
)
async def list_plans(
    request: Request,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> Dict[str, Any]:
    identity = await i2w_identity(request=request)
    _audit_request(request, identity, action="i2w.plans.list")
    # The plan-store list wrapper is not yet registered. We surface
    # an honest 501 + a hint, not a 200 with empty data.
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=(
            "Plan-list is pending the persistent plan-store wrapper. "
            "Use the /api/v1/i2w/training/records endpoint in the meantime."
        ),
    )


# ---------------------------------------------------------------------------
# GET /plans/{plan_id}
# ---------------------------------------------------------------------------


@router.get(
    "/plans/{plan_id}",
    summary="Get a single plan (full + YAML).",
    dependencies=i2w_deps(scope=I2W_SCOPE_READ, stage="plan"),
    response_model=None,
)
async def get_plan(plan_id: str, request: Request) -> Dict[str, Any]:
    identity = await i2w_identity(request=request)
    _audit_request(request, identity, action="i2w.plans.get")
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Plan-get is pending the persistent plan-store wrapper.",
    )


# ---------------------------------------------------------------------------
# POST /plans
# ---------------------------------------------------------------------------


@router.post(
    "/plans",
    summary="Save a plan (e.g. user-edited).",
    dependencies=i2w_deps(scope=I2W_SCOPE_WRITE, stage="plan"),
    response_model=None,
)
async def save_plan(request: Request, body: Dict[str, Any]) -> Dict[str, Any]:
    identity = await i2w_identity(request=request)
    _audit_request(request, identity, action="i2w.plans.save")
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Plan-save is pending the persistent plan-store wrapper.",
    )


# ---------------------------------------------------------------------------
# PUT /plans/{plan_id}
# ---------------------------------------------------------------------------


@router.put(
    "/plans/{plan_id}",
    summary="Update a plan (creates a new version).",
    dependencies=i2w_deps(scope=I2W_SCOPE_WRITE, stage="plan"),
    response_model=None,
)
async def update_plan(
    plan_id: str,
    request: Request,
    body: Dict[str, Any],
) -> Dict[str, Any]:
    identity = await i2w_identity(request=request)
    _audit_request(request, identity, action="i2w.plans.update")
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Plan-update is pending the persistent plan-store wrapper.",
    )


# ---------------------------------------------------------------------------
# DELETE /plans/{plan_id}
# ---------------------------------------------------------------------------


@router.delete(
    "/plans/{plan_id}",
    summary="Soft-delete a plan.",
    dependencies=i2w_deps(scope=I2W_SCOPE_WRITE, stage="plan"),
    response_model=None,
)
async def delete_plan(plan_id: str, request: Request) -> Dict[str, Any]:
    identity = await i2w_identity(request=request)
    _audit_request(request, identity, action="i2w.plans.delete")
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Plan-delete is pending the persistent plan-store wrapper.",
    )


# ---------------------------------------------------------------------------
# GET /plans/{plan_id}/versions
# ---------------------------------------------------------------------------


@router.get(
    "/plans/{plan_id}/versions",
    summary="List versions of a plan.",
    dependencies=i2w_deps(scope=I2W_SCOPE_READ, stage="plan"),
    response_model=None,
)
async def list_plan_versions(plan_id: str, request: Request) -> Dict[str, Any]:
    identity = await i2w_identity(request=request)
    _audit_request(request, identity, action="i2w.plans.versions")
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Plan-versions is pending the persistent plan-store wrapper.",
    )


# ---------------------------------------------------------------------------
# POST /plans/{plan_id}/execute
# ---------------------------------------------------------------------------


@router.post(
    "/plans/{plan_id}/execute",
    summary="Execute a saved plan by id.",
    dependencies=i2w_deps(scope=I2W_SCOPE_EXECUTE, stage="dispatch"),
    response_model=None,
)
async def execute_saved_plan(
    plan_id: str,
    request: Request,
    body: Optional[Dict[str, Any]] = Body(default=None),
) -> Dict[str, Any]:
    identity = await i2w_identity(request=request)
    _audit_request(request, identity, action="i2w.plans.execute")
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=(
            "Saved-plan-execute is pending the persistent plan-store "
            "wrapper. Use /api/v1/i2w/dispatch with the plan body for now."
        ),
    )


# ---------------------------------------------------------------------------
# POST /plans/{plan_id}/refine
# ---------------------------------------------------------------------------


@router.post(
    "/plans/{plan_id}/refine",
    summary="Multi-turn plan refinement.",
    dependencies=i2w_deps(scope=I2W_SCOPE_WRITE, stage="reason"),
    response_model=None,
)
async def refine_plan(
    plan_id: str,
    request: Request,
    body: Dict[str, Any],
) -> Dict[str, Any]:
    identity = await i2w_identity(request=request)
    _audit_request(request, identity, action="i2w.plans.refine")
    # Refinement maps to i2w_resolve_ambiguity today (multi-turn
    # ask-user loop); the dedicated i2w_refine_plan wrapper is part
    # of the docs' planned set.
    try:
        return invoke_i2w(
            "i2w_resolve_ambiguity",
            **body,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


__all__ = ["router"]
