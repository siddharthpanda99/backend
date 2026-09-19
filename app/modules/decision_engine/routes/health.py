"""Decision Engine Health & Flags routes.

GET /api/v1/decision-engine/health                 — health check
GET /api/v1/decision-engine/flags                  — get all decision fabric flags
GET /api/v1/decision-engine/flags/{flag_name}      — resolve specific flag
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from common_lib.modules.decision_engine.flags import (
    DECISION_AUTO_APPROVAL_ENABLED,
    DECISION_COORDINATION_ENABLED,
    DECISION_COORDINATION_SHADOW,
    DECISION_HUMAN_REVIEW_ENABLED,
    DECISION_LEARNING_ENABLED,
    NEXUS_DECISION_FABRIC_ENABLED,
    _FLAG_NAMES,
    decision_flags_snapshot,
    is_decision_flag_enabled,
)
from common_lib.modules.decision_engine.schemas import DecisionEngineHealth

router = APIRouter()


# Response models
class FlagSnapshotResponse(BaseModel):
    """Response for flag snapshot."""

    flags: dict[str, bool]


class SingleFlagResponse(BaseModel):
    """Response for single flag resolution."""

    flag_name: str
    enabled: bool


@router.get("/health")
async def health_check() -> DecisionEngineHealth:
    """GET /health — health check for decision engine."""
    # Note: No flag guard on health — it should always respond
    return DecisionEngineHealth(
        status="healthy",
        version="1.0.0",
        models_loaded=0,
        thresholds_loaded=False,
    )


@router.get("/flags", response_model=FlagSnapshotResponse)
async def get_flags(tenant_id: str | None = None) -> FlagSnapshotResponse:
    """GET /flags — resolved snapshot of all decision fabric flags."""
    snapshot = decision_flags_snapshot(tenant_id)
    return FlagSnapshotResponse(flags=snapshot)


@router.get("/flags/{flag_name}", response_model=SingleFlagResponse)
async def get_flag(flag_name: str, tenant_id: str | None = None) -> SingleFlagResponse:
    """GET /flags/{flag_name} — resolve specific decision fabric flag."""
    if flag_name not in _FLAG_NAMES:
        raise HTTPException(status_code=404, detail=f"Unknown flag: {flag_name}")

    enabled = is_decision_flag_enabled(flag_name, tenant_id)
    return SingleFlagResponse(flag_name=flag_name, enabled=enabled)
