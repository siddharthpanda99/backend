"""RIP Nexus coverage routes — thin transport for the §21 Coverage Engine (chunk C035).

Thin-router discipline: no business logic here; delegation to
``common_lib.modules.rip.rip_coverage.*`` (lazy imports inside handlers).
Endpoints:
* ``POST /rip/coverage/assess``      — deterministic coverage measurement (C030)
* ``POST /rip/coverage/gaps``        — gap detection from a report (C031)
* ``POST /rip/coverage/rank-next``   — information-gain ranking of candidates (C032)
* ``POST /rip/coverage/exhaustion``  — §25 tri-state classification (C034)
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/rip/coverage", tags=["RIP — Nexus Coverage"])


class AssessRequest(BaseModel):
    query: str = Field(..., min_length=1)
    scope: str = Field(default="ALL_ALLOWED")
    requirements: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    matches: list[dict[str, Any]] = Field(default_factory=list)
    coverage_threshold: float = Field(default=0.0, ge=0.0, le=1.0)


class AssessResponse(BaseModel):
    report: dict[str, Any]


class GapsRequest(BaseModel):
    report: dict[str, Any]
    candidate_sources: list[str] | None = None


class GapsResponse(BaseModel):
    gaps: list[dict[str, Any]]


class RankRequest(BaseModel):
    candidates: list[dict[str, Any]] = Field(default_factory=list)
    gaps: list[dict[str, Any]] = Field(default_factory=list)
    attempted: list[dict[str, Any]] | None = None
    weights: dict[str, float] | None = None


class RankResponse(BaseModel):
    ranked: list[dict[str, Any]]


class ExhaustionRequest(BaseModel):
    found_count: int = Field(default=0, ge=0)
    all_admissible_searched: bool
    blockers: list[str] | None = None


class ExhaustionResponse(BaseModel):
    exhaustion: dict[str, Any]


@router.post("/assess", response_model=AssessResponse)
async def assess_coverage(payload: AssessRequest) -> AssessResponse:
    """Deterministic coverage measurement (§21/§22/§93)."""
    try:
        from common_lib.modules.rip.rip_coverage.engine import measure_coverage

        report = measure_coverage(
            query=payload.query,
            scope=payload.scope,
            requirements=payload.requirements,
            evidence=payload.evidence,
            matches=payload.matches,
            coverage_threshold=payload.coverage_threshold,
        )
        return AssessResponse(report=report)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 — transport error mapping only
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/gaps", response_model=GapsResponse)
async def detect_coverage_gaps(payload: GapsRequest) -> GapsResponse:
    """Gap detection from a CoverageReport (§26)."""
    try:
        from common_lib.modules.rip.rip_coverage.gaps import detect_gaps

        gaps = detect_gaps(payload.report, candidate_sources=payload.candidate_sources)
        return GapsResponse(gaps=gaps)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/rank-next", response_model=RankResponse)
async def rank_next(payload: RankRequest) -> RankResponse:
    """Information-gain ranking of acquisition candidates (§27)."""
    try:
        from common_lib.modules.rip.rip_coverage.info_gain import (
            rank_acquisition_candidates,
        )

        ranked = rank_acquisition_candidates(
            candidates=payload.candidates,
            gaps=payload.gaps,
            attempted=payload.attempted,
            weights=payload.weights,
        )
        return RankResponse(ranked=ranked)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/exhaustion", response_model=ExhaustionResponse)
async def classify_exhaustion(payload: ExhaustionRequest) -> ExhaustionResponse:
    """§25 tri-state exhaustion classification (§97 explicit semantics)."""
    try:
        from common_lib.modules.rip.rip_coverage.exhaustion import (
            resolve_exhaustion,
            exhaustion_to_dict,
        )

        state = resolve_exhaustion(
            found_count=payload.found_count,
            all_admissible_searched=payload.all_admissible_searched,
            blockers=payload.blockers,
        )
        return ExhaustionResponse(exhaustion=exhaustion_to_dict(state))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
