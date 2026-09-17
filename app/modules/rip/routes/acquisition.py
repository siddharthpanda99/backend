"""RIP Nexus acquisition routes — thin transport for §67 gap acquisition (chunk C041).

Thin-router discipline: no business logic here; delegation to
``common_lib.modules.rip.rip_acquisition.*`` (lazy imports inside handlers).
Endpoints:
* ``POST /rip/acquisition/plan``        — per-gap source plans (C036, §68)
* ``POST /rip/acquisition/resolve-gaps`` — concurrent §69 loop (C040/C039; §97 blocked-mode when seams are absent)
* ``GET  /rip/acquisition/status``       — capability/flag status for operators
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/rip/acquisition", tags=["RIP — Nexus Acquisition"])


class PlanRequest(BaseModel):
    gaps: list[dict[str, Any]] = Field(default_factory=list)
    sources: list[dict[str, Any]] = Field(default_factory=list)
    weights: dict[str, float] | None = None


class PlanResponse(BaseModel):
    plans: list[dict[str, Any]]


class ResolveRequest(BaseModel):
    gaps: list[dict[str, Any]] = Field(default_factory=list)
    sources: list[dict[str, Any]] = Field(default_factory=list)
    existing_evidence_ids: list[str] | None = None
    max_concurrency: int = Field(default=4, ge=1, le=32)
    max_source_attempts: int = Field(default=3, ge=1, le=10)


class ResolveResponse(BaseModel):
    result: dict[str, Any]


@router.post("/plan", response_model=PlanResponse)
async def plan_acquisition_route(payload: PlanRequest) -> PlanResponse:
    """Per-gap ordered source plans (§68 deterministic utility)."""
    try:
        from common_lib.modules.rip.rip_acquisition.planner import plan_acquisition

        return PlanResponse(
            plans=plan_acquisition(
                gaps=payload.gaps, sources=payload.sources, weights=payload.weights
            )["plans"]
        )
    except Exception as exc:  # noqa: BLE001 — transport error mapping only
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/resolve-gaps", response_model=ResolveResponse)
async def resolve_gaps_route(payload: ResolveRequest) -> ResolveResponse:
    """Concurrent §69 gap resolution.

    Transport note (§97 explicit, never silent): provider/verification seams are
    callables and cannot cross HTTP transport, so the service runs here in its
    blocked-mode — every gap returns an explicit BLOCKED record with the
    seam-absent blocker instead of a fabricated success or a silent pass.
    """
    try:
        from common_lib.modules.rip.rip_acquisition.concurrent import (
            aresolve_gaps_concurrently,
        )

        result = await aresolve_gaps_concurrently(
            gaps=payload.gaps,
            sources=payload.sources,
            fetch_fn=lambda req: {
                "evidence": [],
                "matches": [],
                "blockers": ["fetch_fn seam unavailable via HTTP transport"],
            },
            verify_fn=lambda gap, batch: [],
            existing_evidence_ids=payload.existing_evidence_ids,
            max_concurrency=payload.max_concurrency,
            max_source_attempts=payload.max_source_attempts,
        )
        return ResolveResponse(result=result)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/status")
async def acquisition_status() -> dict[str, Any]:
    """Operator-facing capability status (flag + subpackage availability)."""
    try:
        from common_lib.modules.rip.feature_flags import is_enabled

        return {
            "flag": "NEXUS_ACQUISITION_ENABLED",
            "enabled": bool(is_enabled("NEXUS_ACQUISITION_ENABLED")),
            "external_gate": "NEXUS_EXTERNAL_ACQUISITION_ENABLED",
            "external_enabled": bool(is_enabled("NEXUS_EXTERNAL_ACQUISITION_ENABLED")),
        }
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
