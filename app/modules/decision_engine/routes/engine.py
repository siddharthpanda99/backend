"""Decision Engine Core routes — cascaded decisions, plan building, compilation.

This router deliberately declares **no** ``prefix=``. The re-basing of
``/engine/*``, ``/context/*`` and ``/registry/*`` onto the router root is the
served contract and is pinned by ``tests/test_decision_fabric_e2e.py``
(``test_unprefixed_context_engine_intent_routes_exist``). Re-adding a prefix
here would 404 every one of those endpoints.

Mounted paths (relative to the ``/decision-engine`` mount):

POST /route              — cascaded decision pipeline (Tier 1-5)
POST /compile            — compile approved plan to ExecutionContract
POST /validate           — validate a DecisionPlan
POST /preview            — generate human-readable plan preview
POST /claims/extract     — extract claims for grounding
POST /claims/verify      — verify claims against evidence
POST /claims/coverage    — compute grounding coverage

Removed as unreachable dead code (P0, shadowed routes)
------------------------------------------------------
``POST /ground`` and ``POST /plan`` used to be declared here *as well as* on
``ground.py`` and ``plan.py``. Both files mount the same paths, FastAPI
resolves to the first registration, and the handlers below were therefore
never reachable. The survivors are the correct single home for both
capabilities, because the Pydantic schema is the contract (G10):

* ``POST /ground`` -> ``ground.py``. Takes a ``GroundRequest`` and returns a
  ``GroundResponse``. The handler that used to live here took a bare
  ``{"decision_context": ...}`` body and returned an untyped dict, and it
  passed that body to ``DecisionEngineService.ground_claims``, whose real
  signature expects a ``GroundRequest``-shaped dict
  (``{plan_id, node_id, claims, evidence}``). It was doubly dead.
* ``POST /plan`` -> ``plan.py``. Takes a ``PlanCreateRequest`` and returns a
  ``PlanRead``. The handler that used to live here reached the *same*
  ``DecisionEngineService.build_plan`` through its alternate
  ``decision_context=``/``decisions=`` keyword form. The service documents
  that as a second face of one implementation, not a separate capability.

Nothing was lost: the grounding pipeline and plan building remain reachable
at ``POST /ground`` and ``POST /plan``, and both are covered by
``app/modules/decision_engine/tests/test_routes.py``.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.modules.decision_engine.routes._errors import http_error

from app.modules.decision_engine.routes._flags import (
    require_fabric as _require_fabric,
)

router = APIRouter()


# Request/Response models
class RouteDecisionRequest(BaseModel):
    """Request for cascaded decision pipeline."""

    decision_context: dict[str, Any] = Field(..., description="DecisionContext dict")
    decision_type: str = Field(..., description="One of DECISION_TYPES")
    question: str = Field(..., description="Human-readable decision question")
    options: list[dict[str, Any]] = Field(
        ..., description="List of option dicts with id, label, metadata"
    )


class CompilePlanRequest(BaseModel):
    """Request to compile approved plan."""

    plan: dict[str, Any] = Field(..., description="Approved DecisionPlan dict")


class ValidatePlanRequest(BaseModel):
    """Request to validate a DecisionPlan."""

    plan: dict[str, Any] = Field(..., description="DecisionPlan dict to validate")


class GeneratePreviewRequest(BaseModel):
    """Request to generate plan preview."""

    plan: dict[str, Any] = Field(..., description="DecisionPlan dict")


class ExtractClaimsRequest(BaseModel):
    """Request to extract claims."""

    decision_context: dict[str, Any] = Field(..., description="DecisionContext dict")


class VerifyClaimsRequest(BaseModel):
    """Request to verify claims."""

    claims: list[dict[str, Any]] = Field(..., description="List of Claim dicts")
    decision_context: dict[str, Any] = Field(
        ..., description="DecisionContext for evidence lookup"
    )


class ComputeCoverageRequest(BaseModel):
    """Request to compute grounding coverage."""

    verification_results: dict[str, Any] = Field(
        ..., description="Results from verify_claims"
    )


@router.post("/route")
async def route_decision(payload: RouteDecisionRequest) -> dict[str, Any]:
    """POST /engine/route — cascaded decision pipeline (Tier 1-5) for a single decision.

    Tiers:
    1. Rule-based (deterministic, from policy)
    2. Heuristic (pattern matching, from memory)
    3. Model-based (ML model, from registry)
    4. LLM-based (reasoning, from AI gateway)
    5. Human escalation (approval workflow)
    """
    _require_fabric()

    from common_lib.modules.decision_engine.services import DecisionEngineService

    service = DecisionEngineService()
    try:
        result = service.route_decision(
            decision_context=payload.decision_context,
            decision_type=payload.decision_type,
            question=payload.question,
            options=payload.options,
        )
        return result
    except NotImplementedError as e:
        raise http_error(e, prefix="Decision routing not yet implemented")


@router.post("/compile")
async def compile_plan(payload: CompilePlanRequest) -> dict[str, Any]:
    """POST /engine/compile — compile approved DecisionPlan to ExecutionContract."""
    _require_fabric()

    from common_lib.modules.decision_engine.services import DecisionEngineService

    service = DecisionEngineService()
    try:
        result = service.compile_plan(payload.plan)
        return result
    except NotImplementedError as e:
        raise http_error(e, prefix="Plan compilation not yet implemented")


@router.post("/validate")
async def validate_plan(payload: ValidatePlanRequest) -> dict[str, Any]:
    """POST /engine/validate — validate a DecisionPlan for structural and semantic correctness."""
    _require_fabric()

    from common_lib.modules.decision_engine.services import DecisionEngineService

    service = DecisionEngineService()
    try:
        result = service.validate_plan(payload.plan)
        return result
    except NotImplementedError as e:
        raise http_error(e, prefix="Plan validation not yet implemented")


@router.post("/preview")
async def generate_plan_preview(payload: GeneratePreviewRequest) -> dict[str, Any]:
    """POST /engine/preview — generate human-readable preview of a plan."""
    _require_fabric()

    from common_lib.modules.decision_engine.services import DecisionEngineService

    service = DecisionEngineService()
    try:
        result = service.generate_plan_preview(payload.plan)
        return result
    except NotImplementedError as e:
        raise http_error(e, prefix="Plan preview generation not yet implemented")


@router.post("/claims/extract")
async def extract_claims(payload: ExtractClaimsRequest) -> list[dict[str, Any]]:
    """POST /engine/claims/extract — extract claims from decision context for grounding."""
    _require_fabric()

    from common_lib.modules.decision_engine.services import DecisionEngineService

    service = DecisionEngineService()
    try:
        result = service.extract_claims(payload.decision_context)
        return result
    except NotImplementedError as e:
        raise http_error(e, prefix="Claim extraction not yet implemented")


@router.post("/claims/verify")
async def verify_claims(payload: VerifyClaimsRequest) -> dict[str, Any]:
    """POST /engine/claims/verify — verify claims against evidence."""
    _require_fabric()

    from common_lib.modules.decision_engine.services import DecisionEngineService

    service = DecisionEngineService()
    try:
        result = service.verify_claims(payload.claims, payload.decision_context)
        return result
    except NotImplementedError as e:
        raise http_error(e, prefix="Claim verification not yet implemented")


@router.post("/claims/coverage")
async def compute_coverage(payload: ComputeCoverageRequest) -> dict[str, Any]:
    """POST /engine/claims/coverage — compute grounding coverage from verification results."""
    _require_fabric()

    from common_lib.modules.decision_engine.services import DecisionEngineService

    service = DecisionEngineService()
    try:
        result = service.compute_coverage(payload.verification_results)
        return result
    except NotImplementedError as e:
        raise http_error(e, prefix="Coverage computation not yet implemented")
