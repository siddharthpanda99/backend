"""Request Evaluator API Router — Thin Transport Layer"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException

from common_lib.modules.request_evaluator.schemas import (
    EvalRequest,
    EvalResult,
    GateResult,
    AssessmentResult,
    MandateRead,
    RevalidateRequest,
    PolicyEffectsRequest,
    PolicyEffectsResult,
)
from common_lib.modules.request_evaluator.service import get_request_evaluator_service
from common_lib.modules.request_evaluator.exceptions import (
    RequestEvaluatorError,
    GateError,
    AssessmentError,
    MandateError,
    MandateNotFoundError,
    MandateExpiredError,
    MandateRevokedError,
    PolicyError,
    PolicyVersionMismatchError,
)

router = APIRouter(prefix="/request-evaluator", tags=["request-evaluator"])


@router.post("/evaluate", response_model=EvalResult)
async def evaluate(payload: EvalRequest) -> EvalResult:
    """Run full evaluation on a trigger."""
    try:
        svc = get_request_evaluator_service()
        result = await svc.evaluate(
            trigger={"id": payload.trigger_id},
            thread={"id": payload.thread_id},
            tickets=[],
        )
        return EvalResult(**result)
    except (GateError, AssessmentError, RequestEvaluatorError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/gate", response_model=GateResult)
def gate(
    trigger: dict[str, Any],
    thread: dict[str, Any],
    tickets: list[dict[str, Any]] | None = None,
) -> GateResult:
    """Run deterministic gate only."""
    try:
        svc = get_request_evaluator_service()
        result = svc.gate(trigger, thread, tickets or [])
        return GateResult(**result)
    except (GateError, RequestEvaluatorError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/assess", response_model=AssessmentResult)
async def assess(
    trigger: dict[str, Any],
    thread: dict[str, Any],
    tickets: list[dict[str, Any]] | None = None,
    gate_result: dict[str, Any] | None = None,
    policy: dict[str, Any] | None = None,
) -> AssessmentResult:
    """Run model-based assessment."""
    try:
        svc = get_request_evaluator_service()
        result = await svc.assess(
            trigger, thread, tickets or [], gate_result or {}, policy or {}
        )
        return AssessmentResult(**result)
    except (AssessmentError, RequestEvaluatorError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/mandates/{mandate_id}", response_model=MandateRead)
def get_mandate(mandate_id: UUID) -> MandateRead:
    """Get a mandate by ID."""
    svc = get_request_evaluator_service()
    mandate = svc.get_mandate(mandate_id)
    if not mandate:
        raise HTTPException(status_code=404, detail="Mandate not found")
    return MandateRead.model_validate(mandate)


@router.post("/mandates/{mandate_id}/revalidate", response_model=dict[str, Any])
def revalidate_mandate(mandate_id: UUID, _: RevalidateRequest) -> dict[str, Any]:
    """Revalidate a mandate against current policy."""
    try:
        svc = get_request_evaluator_service()
        return svc.revalidate_mandate(mandate_id)
    except MandateNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except MandateExpiredError as exc:
        raise HTTPException(status_code=410, detail=str(exc))
    except MandateRevokedError as exc:
        raise HTTPException(status_code=410, detail=str(exc))
    except PolicyVersionMismatchError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post("/mandates/{mandate_id}/revoke", response_model=MandateRead)
def revoke_mandate(mandate_id: UUID, reason: str) -> MandateRead:
    """Revoke a mandate."""
    try:
        svc = get_request_evaluator_service()
        mandate = svc.revoke_mandate(mandate_id, reason)
        return MandateRead.model_validate(mandate)
    except MandateNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/policy-effects", response_model=PolicyEffectsResult)
def policy_effects(payload: PolicyEffectsRequest) -> PolicyEffectsResult:
    """Compute policy change effects on live tickets."""
    try:
        svc = get_request_evaluator_service()
        return PolicyEffectsResult(
            **svc.policy_effects(payload.old_version, payload.new_version)
        )
    except PolicyError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/policy")
def current_policy() -> dict[str, Any]:
    """Get current policy."""
    svc = get_request_evaluator_service()
    return svc.get_current_policy()
