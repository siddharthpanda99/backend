"""``app.modules.i2w.routes.health`` — health probes for every stage.

Per docs/08_api_contract.md §1.7:

* ``GET /api/v1/i2w/health``                — composite (all stages)
* ``GET /api/v1/i2w/health/ingest``         — Stage 1
* ``GET /api/v1/i2w/health/reason``         — Stage 2
* ``GET /api/v1/i2w/health/plan``           — Stage 3
* ``GET /api/v1/i2w/health/dispatch``       — Stage 4
* ``GET /api/v1/i2w/health/search``         — search

The composite /health probe aggregates the per-stage health. When the
master I2W flag is off the composite returns ``"skeleton"``; when on
it returns ``"ok"`` plus a per-stage breakdown.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, Request

from app.modules.i2w.routes._helpers import invoke_i2w
from app.modules.i2w.routes.dependencies import (
    I2W_SCOPE_READ,
    _audit_request,
    i2w_identity,
)
from common_lib.modules.orchestration.instruction_to_workflow.feature_flags import (
    is_instruction_to_workflow_enabled,
    INSTRUCTION_TO_WORKFLOW_ENABLED,
)

# Local alias: tests patch this so the composite /health endpoint
# can be exercised with the feature flag "on". In production
# is_instruction_to_workflow_enabled is the source of truth.
_is_i2w_enabled = is_instruction_to_workflow_enabled

logger = logging.getLogger(__name__)

router = APIRouter()


def _stage_health(wrapper: str) -> Dict[str, Any]:
    try:
        return invoke_i2w(wrapper)
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "detail": str(exc)}


@router.get(
    "/health",
    summary="Composite I2W health probe (all stages).",
    description=(
        "Returns ``{status, version, stages}``. When the master I2W flag "
        "is off, ``status`` is ``'skeleton'`` and the per-stage breakdown "
        "is empty. When on, ``status`` is ``'ok'`` and each stage's "
        "own health probe is included."
    ),
    response_model=None,
)
async def health(request: Request) -> Dict[str, Any]:
    """Unauthenticated health probe (load-balancer friendly).

    Per the platform convention (and the platform_controls /health
    pattern) the health endpoint is the ONE I2W endpoint that does
    not require a JWT. The router is registered with ``auth=False``
    in ``Backend/app/core/routers.py`` (see the ``ROUTER_DEFINITIONS``
    entry for this module).
    """
    if not _is_i2w_enabled(INSTRUCTION_TO_WORKFLOW_ENABLED):
        return {
            "status": "skeleton",
            "detail": "I2W framework is disabled (master flag off).",
            "stages": {},
        }
    stages = {
        "ingest": _stage_health("i2w_ingest_health"),
        "reason": _stage_health("i2w_reasoning_health"),
        "plan": _stage_health("i2w_planning_health"),
        "dispatch": _stage_health("i2w_dispatch_health"),
        "search": _stage_health("i2w_search_health"),
        "training": _stage_health("i2w_training_health"),
    }
    composite_status = "ok"
    for s in stages.values():
        if s.get("status") not in {"ok", "available"}:
            composite_status = "degraded"
            break
    return {
        "status": composite_status,
        "stages": stages,
    }


@router.get(
    "/health/ingest",
    summary="Stage 1 health probe.",
    response_model=None,
)
async def health_ingest() -> Dict[str, Any]:
    return _stage_health("i2w_ingest_health")


@router.get(
    "/health/reason",
    summary="Stage 2 health probe.",
    response_model=None,
)
async def health_reason() -> Dict[str, Any]:
    return _stage_health("i2w_reasoning_health")


@router.get(
    "/health/plan",
    summary="Stage 3 health probe.",
    response_model=None,
)
async def health_plan() -> Dict[str, Any]:
    return _stage_health("i2w_planning_health")


@router.get(
    "/health/dispatch",
    summary="Stage 4 health probe.",
    response_model=None,
)
async def health_dispatch() -> Dict[str, Any]:
    return _stage_health("i2w_dispatch_health")


@router.get(
    "/health/search",
    summary="Search health probe.",
    response_model=None,
)
async def health_search() -> Dict[str, Any]:
    return _stage_health("i2w_search_health")


@router.get(
    "/health/training",
    summary="Training health probe.",
    response_model=None,
)
async def health_training() -> Dict[str, Any]:
    return _stage_health("i2w_training_health")


__all__ = ["router"]
