"""Golden-dataset routes — thin delegates to common_lib (NEX-P7-001).

All logic lives in ``common_lib.modules.evaluation.golden``.
Every endpoint except ``/status`` and ``/holdout-check`` answers 404
while the flag ``evaluation.golden.enabled`` is OFF.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/golden", tags=["Cognitive Golden Datasets"])

_FLAG = "evaluation.golden.enabled"


def _require_enabled() -> None:
    try:
        from common_lib.modules.evaluation.golden.flags import (
            is_enabled as _enabled,
        )
    except ImportError:
        raise HTTPException(status_code=404, detail="Golden datasets unavailable")
    if _enabled(_FLAG):
        return
    raise HTTPException(
        status_code=404,
        detail=(
            "Golden datasets are gated behind the feature flag "
            f"'{_FLAG}', which is currently OFF. Enable "
            "GOLDEN_DATASETS_ENABLED=true and restart."
        ),
    )


def _service():
    from common_lib.modules.evaluation.golden.service import get_golden_service

    return get_golden_service()


class ScoreRequest(BaseModel):
    workload: str = Field(default="retrieval")
    actual: list[dict[str, Any]] = Field(default_factory=list)
    judge_score: float | None = Field(default=None)


class HoldoutCheckRequest(BaseModel):
    accessed_splits: list[str] = Field(default_factory=list)
    purpose: str = Field(default="")


class PromoteRequest(BaseModel):
    trace: dict[str, Any] = Field(default_factory=dict)
    privacy_reviewed: bool = Field(default=False)
    approval: str = Field(default="")


@router.get("/status")
def golden_status() -> dict[str, Any]:
    """Flag state + workloads (always visible, never 404)."""
    return dict(_service().status())


@router.get("/inventory")
def golden_inventory() -> dict[str, Any]:
    """Per-workload versions + split counts (404 while OFF)."""
    _require_enabled()
    return dict(_service().inventory())


@router.get("/datasets/{workload}")
def golden_dataset(workload: str, split: str | None = None) -> dict[str, Any]:
    """Versioned cases for one workload, optionally one split (404 while OFF)."""
    _require_enabled()
    out = _service().dataset(workload, split=split)
    if "error" in out:
        raise HTTPException(status_code=404, detail=str(out["error"]))
    return dict(out)


@router.post("/score")
def golden_score(body: ScoreRequest) -> dict[str, Any]:
    """Score actuals vs the workload's dev cases (404 while OFF)."""
    _require_enabled()
    out = _service().score(
        workload=body.workload, actual=body.actual, judge_score=body.judge_score
    )
    if "error" in out:
        raise HTTPException(status_code=404, detail=str(out["error"]))
    return dict(out)


@router.post("/holdout-check")
def golden_holdout_check(body: HoldoutCheckRequest) -> dict[str, Any]:
    """Holdout-discipline gate (always visible, pure check)."""
    return dict(_service().holdout_check(body.accessed_splits, body.purpose))


@router.post("/promote")
def golden_promote(body: PromoteRequest) -> dict[str, Any]:
    """Governed trace→case promotion (404 while OFF; refused unless reviewed+approved)."""
    _require_enabled()
    return dict(
        _service().promote(
            trace=body.trace,
            privacy_reviewed=body.privacy_reviewed,
            approval=body.approval,
        )
    )


__all__ = ["router"]
