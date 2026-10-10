"""Offline eval runs — thin delegates to common_lib (NEX-P7-002).

All logic lives in
``common_lib.modules.evaluation.offline``. Every endpoint except
``/status`` answers 404 while the flag
``evaluation.offline.enabled`` is OFF (the feature does not exist from
the client's point of view until enabled).

G1: thin routes only. G4: additive — new module, no touched baselines.
G9: mutating ops refuse while OFF; pure policy stays in common_lib.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/evaluations", tags=["Evaluations"])

_FLAG = "evaluation.offline.enabled"


def _require_enabled() -> None:
    try:
        from common_lib.modules.evaluation.offline.flags import (
            is_enabled as _enabled,
        )
    except ImportError:
        raise HTTPException(status_code=404, detail="Offline evaluations unavailable")
    if _enabled(_FLAG):
        return
    raise HTTPException(
        status_code=404,
        detail=(
            "Offline evaluations are gated behind the feature flag "
            f"'{_FLAG}', which is currently OFF. Enable "
            "EVAL_OFFLINE_ENABLED=true and restart."
        ),
    )


def _service():
    from common_lib.modules.evaluation.offline.service import (
        get_eval_offline_service,
    )

    return get_eval_offline_service()


class EvalRunCreate(BaseModel):
    name: str = ""
    baseline_cases: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)
    candidate_cases: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)
    suites: list[str] | None = None
    k: int = Field(default=5, ge=1, le=100)
    redteam_baseline_outputs: dict[str, str] = Field(default_factory=dict)
    redteam_candidate_outputs: dict[str, str] = Field(default_factory=dict)
    trace_refs: list[str] = Field(default_factory=list)


class RedteamRunRequest(BaseModel):
    baseline_outputs: dict[str, str] = Field(default_factory=dict)
    candidate_outputs: dict[str, str] = Field(default_factory=dict)


class CanaryStartRequest(BaseModel):
    workload: str = ""
    candidate_id: str = ""
    baseline_id: str = ""


class CanaryRecordRequest(BaseModel):
    workload: str = ""
    observation: dict[str, Any] = Field(default_factory=dict)


class PromotionCreate(BaseModel):
    trace_id: str = ""
    candidate_case: dict[str, Any] = Field(default_factory=dict)
    requested_by: str = "unknown"


class PromotionReview(BaseModel):
    reviewer: str = "unknown"
    approve: bool = False


@router.get("/status")
def evaluations_status() -> dict[str, Any]:
    """Flag state + counts (always visible, never 404)."""
    return dict(_service().status())


@router.post("/runs", status_code=201)
def create_eval_run(body: EvalRunCreate) -> dict[str, Any]:
    """Baseline-vs-candidate on the same harness + red-team + gate."""
    _require_enabled()
    return dict(
        _service().create_run(
            name=body.name,
            baseline_cases=body.baseline_cases,
            candidate_cases=body.candidate_cases,
            suites=body.suites,
            k=body.k,
            redteam_baseline_outputs=body.redteam_baseline_outputs,
            redteam_candidate_outputs=body.redteam_candidate_outputs,
            trace_refs=body.trace_refs,
        )
    )


@router.get("/runs/{run_id}")
def get_eval_run(run_id: str) -> dict[str, Any]:
    """Fetch one eval run by id."""
    _require_enabled()
    run = _service().get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Eval run {run_id} not found")
    return dict(run)


@router.post("/redteam")
def run_redteam(body: RedteamRunRequest) -> dict[str, Any]:
    """Score both arms against the red-team probe catalog."""
    _require_enabled()
    return dict(
        _service().run_redteam(
            baseline_outputs=body.baseline_outputs,
            candidate_outputs=body.candidate_outputs,
        )
    )


@router.post("/canary/start", status_code=201)
def canary_start(body: CanaryStartRequest) -> dict[str, Any]:
    """Open a staged canary (1% → 10% → 50% → 100%)."""
    _require_enabled()
    return dict(
        _service().canary_start(
            workload=body.workload,
            candidate_id=body.candidate_id,
            baseline_id=body.baseline_id,
        )
    )


@router.post("/canary/record")
def canary_record(body: CanaryRecordRequest) -> dict[str, Any]:
    """Record one canary observation (auto-rollback on regression)."""
    _require_enabled()
    return dict(
        _service().canary_record(workload=body.workload, observation=body.observation)
    )


@router.post("/promotions", status_code=201)
def propose_promotion(body: PromotionCreate) -> dict[str, Any]:
    """File a governed trace→test-case promotion proposal (no dataset write)."""
    _require_enabled()
    if not body.trace_id:
        raise HTTPException(status_code=400, detail="trace_id is required")
    return dict(
        _service().propose_promotion(
            trace_id=body.trace_id,
            candidate_case=body.candidate_case,
            requested_by=body.requested_by,
        )
    )


@router.post("/promotions/{proposal_id}/approve")
def approve_promotion(proposal_id: str, body: PromotionReview) -> dict[str, Any]:
    """Review a promotion proposal (approval performs no dataset write)."""
    _require_enabled()
    result = _service().approve_promotion(
        proposal_id=proposal_id, reviewer=body.reviewer, approve=body.approve
    )
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return dict(result)


__all__ = ["router"]
