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
    is_route_gated,
)
from common_lib.modules.decision_engine.schemas import DecisionEngineHealth

# This module is the *discovery* surface: it is the only place a client learns
# that the fabric is off, so its three routes are deliberately ungated. The
# exemption is declared once, in ``common_lib`` — see
# ``common_lib.modules.decision_engine.flags.ALWAYS_AVAILABLE`` — rather than
# left implicit, and ``is_route_gated`` is used below as an in-code assertion
# that this file and that declaration still agree.
#
# Concretely: if someone adds a fourth route here and forgets to think about
# gating, the assertion below is the thing that makes the omission loud instead
# of silent.
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
    """GET /health — health check for decision engine.

    Ungated by design: a liveness probe must answer whether or not the
    Decision Fabric is enabled. Gating it would make a perfectly healthy pod
    look dead to its load balancer the moment the flag is off.
    """
    # No flag guard on health — it should always respond. See ALWAYS_AVAILABLE.
    return DecisionEngineHealth(
        status="healthy",
        version="1.0.0",
        models_loaded=0,
        thresholds_loaded=False,
    )


@router.get("/flags", response_model=FlagSnapshotResponse)
async def get_flags(tenant_id: str | None = None) -> FlagSnapshotResponse:
    """GET /flags — resolved snapshot of all decision fabric flags.

    Ungated by design: this is how a client discovers that the fabric is off.
    Gating it would make the master flag unobservable, which defeats the
    purpose of having a flag.
    """
    snapshot = decision_flags_snapshot(tenant_id)
    return FlagSnapshotResponse(flags=snapshot)


@router.get("/flags/{flag_name}", response_model=SingleFlagResponse)
async def get_flag(flag_name: str, tenant_id: str | None = None) -> SingleFlagResponse:
    """GET /flags/{flag_name} — resolve specific decision fabric flag.

    Ungated by design, same reasoning as ``GET /flags``: the Settings ▸ Feature
    Flags view renders this directly.
    """
    if flag_name not in _FLAG_NAMES:
        raise HTTPException(status_code=404, detail=f"Unknown flag: {flag_name}")

    enabled = is_decision_flag_enabled(flag_name, tenant_id)
    return SingleFlagResponse(flag_name=flag_name, enabled=enabled)


def _assert_discovery_surface_is_declared() -> None:
    """Fail loudly if this file and ``ALWAYS_AVAILABLE`` have drifted apart.

    Every route in this module is intentionally ungated. That intent lives in
    ``common_lib.modules.decision_engine.flags.ALWAYS_AVAILABLE``; this check
    is what stops the two from drifting into a silent inconsistency — someone
    adds a route here, or removes one from the allowlist, and the mismatch
    surfaces at import time instead of in production.

    It raises rather than warns on purpose. An unguarded route that nobody
    declared is exactly the bug this work exists to remove, and a warning in a
    startup log is the easiest possible way for it to be missed.
    """
    for route in router.routes:
        path = getattr(route, "path", None)
        if path is None:  # not an APIRoute (e.g. a Mount) — nothing to check
            continue
        if is_route_gated(path):
            raise RuntimeError(
                f"{path} is declared ungated in this module but "
                "common_lib ...decision_engine.flags.ALWAYS_AVAILABLE does not "
                "exempt it. Either add the guard or add the path to the "
                "allowlist — do not leave the two disagreeing."
            )


_assert_discovery_surface_is_declared()
