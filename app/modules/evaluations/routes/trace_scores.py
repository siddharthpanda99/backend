"""Trace scores — thin delegates to common_lib (NEX-P7-002).

``POST /traces/{trace_id}/scores`` attaches a score map to a trace
(human or automated scorer). 404 while ``evaluation.offline.enabled``
is OFF. G1: thin routes only. G4: additive.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/traces", tags=["Trace Scores"])

_FLAG = "evaluation.offline.enabled"


def _require_enabled() -> None:
    try:
        from common_lib.modules.evaluation.offline.flags import (
            is_enabled as _enabled,
        )
    except ImportError:
        raise HTTPException(status_code=404, detail="Trace scoring unavailable")
    if _enabled(_FLAG):
        return
    raise HTTPException(
        status_code=404,
        detail=(
            "Trace scoring is gated behind the feature flag "
            f"'{_FLAG}', which is currently OFF. Enable "
            "EVAL_OFFLINE_ENABLED=true and restart."
        ),
    )


def _service():
    from common_lib.modules.evaluation.offline.service import (
        get_eval_offline_service,
    )

    return get_eval_offline_service()


class TraceScoreCreate(BaseModel):
    scores: dict[str, float] = Field(default_factory=dict)
    scorer: str = "human"
    comment: str = ""


@router.post("/{trace_id}/scores", status_code=201)
def score_trace(trace_id: str, body: TraceScoreCreate) -> dict[str, Any]:
    """Attach scores to a trace (clamped to [0, 1])."""
    _require_enabled()
    return dict(
        _service().score_trace(
            trace_id=trace_id,
            scores=body.scores,
            scorer=body.scorer,
            comment=body.comment,
        )
    )


@router.get("/{trace_id}/scores")
def get_trace_scores(trace_id: str) -> dict[str, Any]:
    """List scores attached to a trace."""
    _require_enabled()
    return {"trace_id": trace_id, "scores": _service().get_trace_scores(trace_id)}


__all__ = ["router"]
