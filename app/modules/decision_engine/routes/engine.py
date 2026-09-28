"""Decision Engine Core routes — cascaded decisions, plan building, compilation.

POST /api/v1/decision-engine/engine/route            — cascaded decision pipeline (Tier 1-5)
POST /api/v1/decision-engine/engine/ground            — grounding pipeline for claims
POST /api/v1/decision-engine/engine/plan              — build decision graph and plan
POST /api/v1/decision-engine/engine/compile           — compile approved plan to ExecutionContract
POST /api/v1/decision-engine/engine/validate          — validate a DecisionPlan
POST /api/v1/decision-engine/engine/preview           — generate human-readable plan preview
POST /api/v1/decision-engine/engine/claims/extract    — extract claims for grounding
POST /api/v1/decision-engine/engine/claims/verify     — verify claims against evidence
POST /api/v1/decision-engine/engine/claims/coverage   — compute grounding coverage
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from common_lib.modules.decision_engine.flags import (
    NEXUS_DECISION_FABRIC_ENABLED,
    is_decision_flag_enabled,
)

router = APIRouter()


def _require_fabric() -> None:
    """Fail-closed flag guard: 503 until NEXUS_DECISION_FABRIC_ENABLED is on."""
    if not is_decision_flag_enabled(NEXUS_DECISION_FABRIC_ENABLED):
        raise HTTPException(
            status_code=503,
            detail="Decision Fabric is disabled (NEXUS_DECISION_FABRIC_ENABLED=off)",
        )


# Request/Response models
class RouteDecisionRequest(BaseModel):
    """Request for cascaded decision pipeline."""

    decision_context: dict[str, Any] = Field(..., description="DecisionContext dict")
    decision_type: str = Field(..., description="One of DECISION_TYPES")
    question: str = Field(..., description="Human-readable decision question")
    options: list[dict[str, Any]] = Field(
        ..., description="List of option dicts with id, label, metadata"
    )


class GroundClaimsRequest(BaseModel):
    """Request for grounding pipeline."""

    decision_context: dict[str, Any] = Field(..., description="DecisionContext dict")


class BuildPlanRequest(BaseModel):
    """Request to build decision graph and plan."""

    decision_context: dict[str, Any] = Field(..., description="DecisionContext dict")
    decisions: list[dict[str, Any]] = Field(
        ..., description="List of Decision dicts from route_decision"
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
    except NotImplementedError:
        raise HTTPException(
            status_code=501, detail="Decision routing not yet implemented"
        )


@router.post("/ground")
async def ground_claims(payload: GroundClaimsRequest) -> dict[str, Any]:
    """POST /engine/ground — grounding pipeline: claim extraction → verification → coverage."""
    _require_fabric()

    from common_lib.modules.decision_engine.services import DecisionEngineService

    service = DecisionEngineService()
    try:
        result = service.ground_claims(payload.decision_context)
        return result
    except NotImplementedError:
        raise HTTPException(status_code=501, detail="Grounding not yet implemented")


@router.post("/plan")
async def build_plan(payload: BuildPlanRequest) -> dict[str, Any]:
    """POST /engine/plan — build decision graph, validate, generate preview."""
    _require_fabric()

    from common_lib.modules.decision_engine.services import DecisionEngineService

    service = DecisionEngineService()
    try:
        result = service.build_plan(
            decision_context=payload.decision_context,
            decisions=payload.decisions,
        )
        return result
    except NotImplementedError:
        raise HTTPException(status_code=501, detail="Plan building not yet implemented")


@router.post("/compile")
async def compile_plan(payload: CompilePlanRequest) -> dict[str, Any]:
    """POST /engine/compile — compile approved DecisionPlan to ExecutionContract."""
    _require_fabric()

    from common_lib.modules.decision_engine.services import DecisionEngineService

    service = DecisionEngineService()
    try:
        result = service.compile_plan(payload.plan)
        return result
    except NotImplementedError:
        raise HTTPException(
            status_code=501, detail="Plan compilation not yet implemented"
        )


@router.post("/validate")
async def validate_plan(payload: ValidatePlanRequest) -> dict[str, Any]:
    """POST /engine/validate — validate a DecisionPlan for structural and semantic correctness."""
    _require_fabric()

    from common_lib.modules.decision_engine.services import DecisionEngineService

    service = DecisionEngineService()
    try:
        result = service.validate_plan(payload.plan)
        return result
    except NotImplementedError:
        raise HTTPException(
            status_code=501, detail="Plan validation not yet implemented"
        )


@router.post("/preview")
async def generate_plan_preview(payload: GeneratePreviewRequest) -> dict[str, Any]:
    """POST /engine/preview — generate human-readable preview of a plan."""
    _require_fabric()

    from common_lib.modules.decision_engine.services import DecisionEngineService

    service = DecisionEngineService()
    try:
        result = service.generate_plan_preview(payload.plan)
        return result
    except NotImplementedError:
        raise HTTPException(
            status_code=501, detail="Plan preview generation not yet implemented"
        )


@router.post("/claims/extract")
async def extract_claims(payload: ExtractClaimsRequest) -> list[dict[str, Any]]:
    """POST /engine/claims/extract — extract claims from decision context for grounding."""
    _require_fabric()

    from common_lib.modules.decision_engine.services import DecisionEngineService

    service = DecisionEngineService()
    try:
        result = service.extract_claims(payload.decision_context)
        return result
    except NotImplementedError:
        raise HTTPException(
            status_code=501, detail="Claim extraction not yet implemented"
        )


@router.post("/claims/verify")
async def verify_claims(payload: VerifyClaimsRequest) -> dict[str, Any]:
    """POST /engine/claims/verify — verify claims against evidence."""
    _require_fabric()

    from common_lib.modules.decision_engine.services import DecisionEngineService

    service = DecisionEngineService()
    try:
        result = service.verify_claims(payload.claims, payload.decision_context)
        return result
    except NotImplementedError:
        raise HTTPException(
            status_code=501, detail="Claim verification not yet implemented"
        )


@router.post("/claims/coverage")
async def compute_coverage(payload: ComputeCoverageRequest) -> dict[str, Any]:
    """POST /engine/claims/coverage — compute grounding coverage from verification results."""
    _require_fabric()

    from common_lib.modules.decision_engine.services import DecisionEngineService

    service = DecisionEngineService()
    try:
        result = service.compute_coverage(payload.verification_results)
        return result
    except NotImplementedError:
        raise HTTPException(
            status_code=501, detail="Coverage computation not yet implemented"
        )
