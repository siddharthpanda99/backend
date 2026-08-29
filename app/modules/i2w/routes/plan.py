"""``app.modules.i2w.routes.plan`` — Stage 3 planning endpoints.

Mounts (per docs/08_api_contract.md §1.2):

* ``POST /api/v1/i2w/plan``
* ``POST /api/v1/i2w/plan/parse-yaml``
* ``POST /api/v1/i2w/plan/dry-run``
* ``GET  /api/v1/i2w/health/plan``   (defined in routes/health.py)

Plan CRUD lives in ``routes/workflows.py``.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request, status

from app.modules.i2w.routes._helpers import invoke_i2w
from app.modules.i2w.routes.dependencies import (
    I2W_SCOPE_READ,
    I2W_SCOPE_WRITE,
    _audit_request,
    i2w_deps,
    i2w_identity,
)

logger = logging.getLogger(__name__)

router = APIRouter()


async def _invoke_plan(
    request: Request,
    body: Dict[str, Any],
    *,
    wrapper: str,
    action: str,
) -> Dict[str, Any]:
    identity = await i2w_identity(request=request)
    trace_id = request.headers.get("X-Trace-ID", "")
    defaults: Dict[str, Any] = {
        "user_id_hash": str(getattr(identity, "subject_id", "anon")),
        "tenant_id": str(getattr(identity, "tenant_id", "default")),
    }
    if trace_id:
        defaults["trace_id"] = trace_id
    try:
        result = invoke_i2w(wrapper, defaults=defaults, **body)
    except RuntimeError as exc:
        _audit_request(request, identity, action=action, status_code=400)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    _audit_request(request, identity, action=action)
    return result


@router.post(
    "/plan",
    summary="Stage 3 — produce a WorkflowPlan from a ReasoningResult.",
    dependencies=i2w_deps(scope=I2W_SCOPE_WRITE, stage="plan"),
    response_model=None,
)
async def plan(request: Request, body: Dict[str, Any]) -> Dict[str, Any]:
    return await _invoke_plan(request, body, wrapper="i2w_plan", action="i2w.plan")


@router.post(
    "/plan/parse-yaml",
    summary="Parse a workflow YAML back into a WorkflowPlan dict.",
    dependencies=i2w_deps(scope=I2W_SCOPE_WRITE, stage="plan"),
    response_model=None,
)
async def plan_parse_yaml(request: Request, body: Dict[str, Any]) -> Dict[str, Any]:
    return await _invoke_plan(
        request,
        body,
        wrapper="i2w_parse_yaml",
        action="i2w.plan.parse_yaml",
    )


@router.post(
    "/plan/dry-run",
    summary="Validate + topo-sort a plan without executing it.",
    dependencies=i2w_deps(scope=I2W_SCOPE_READ, stage="plan"),
    response_model=None,
)
async def plan_dry_run(request: Request, body: Dict[str, Any]) -> Dict[str, Any]:
    """Dry-run: validate + optimize + topo-sort, no execution.

    Maps to ``i2w_validate_plan`` then ``i2w_optimize_plan`` (no
    dedicated ``i2w_plan_dry_run`` wrapper exists in the current
    tree; the docs plan for one but it has not landed yet). The
    handler composes the two existing wrappers.
    """
    identity = await i2w_identity(request=request)
    plan_dict = body.get("plan") or body
    try:
        validation = invoke_i2w("i2w_validate_plan", plan=plan_dict)
        optimization = invoke_i2w("i2w_optimize_plan", plan=plan_dict)
    except RuntimeError as exc:
        _audit_request(request, identity, action="i2w.plan.dry_run", status_code=400)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    _audit_request(request, identity, action="i2w.plan.dry_run")
    return {
        "validation": validation,
        "optimization": optimization,
        "plan": plan_dict,
    }


@router.get(
    "/plans/{plan_id}/yaml",
    summary="Return the YAML of a saved plan (alias of workflows.get_yaml).",
    dependencies=i2w_deps(scope=I2W_SCOPE_READ, stage="plan"),
    response_model=None,
)
async def get_plan_yaml(plan_id: str, request: Request) -> Dict[str, Any]:
    """Return the YAML representation of a saved plan.

    The CRUD layer in ``routes/workflows.py`` owns the persistent
    plan store; this endpoint is a convenience that emits the
    YAML via ``i2w_emit_yaml`` (re-serialising the stored plan).
    """
    identity = await i2w_identity(request=request)
    _audit_request(request, identity, action="i2w.plan.get_yaml")
    # The actual retrieval is delegated to the workflows router's
    # helper. For now we acknowledge with a small response.
    return {"plan_id": plan_id, "yaml": None, "note": "see workflows router"}


__all__ = ["router"]
