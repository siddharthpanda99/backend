"""RIP Nexus truth routes — thin transport for §30/§32 (chunk C048).

Thin-router discipline: no business logic here; delegation to
``common_lib.modules.rip.rip_synthesis.*`` (lazy imports inside handlers).
Endpoints:
* ``POST /rip/truth/verify-claim``     — §30 five-question verification (C043)
* ``POST /rip/truth/assess``           — §31 TruthAssessment assembly (C044)
* ``POST /rip/truth/contradictions``   — §32/§33 claim-pair classification (C045)
* ``POST /rip/truth/resolve``          — §34/§35 resolution outcome (C046)
* ``POST /rip/truth/retain``           — §36 both-sides retention (C047)
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/rip/truth", tags=["RIP — Nexus Truth"])


class VerifyClaimRequest(BaseModel):
    claim: str = Field(..., min_length=1)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    matches: list[dict[str, Any]] = Field(default_factory=list)
    contradictions: list[dict[str, Any]] = Field(default_factory=list)
    claim_fact: dict[str, Any] | None = None
    kb_id: str | None = None
    valid_window: dict[str, Any] | None = None
    at_time: str | None = None


class VerifyClaimResponse(BaseModel):
    verification: dict[str, Any]


class AssessRequest(BaseModel):
    claim: str = Field(..., min_length=1)
    answers: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    supporting_evidence_ids: list[str] | None = None
    contradicting_evidence_ids: list[str] | None = None
    temporal_scope: dict[str, Any] | None = None
    provenance: dict[str, Any] | None = None


class AssessResponse(BaseModel):
    assessment: dict[str, Any]


class ContradictionsRequest(BaseModel):
    claims: list[dict[str, Any]] = Field(default_factory=list)


class ContradictionsResponse(BaseModel):
    result: dict[str, Any]


class ResolveRequest(BaseModel):
    contradiction: dict[str, Any]


class ResolveResponse(BaseModel):
    resolution: dict[str, Any]


class RetainRequest(BaseModel):
    contradiction: dict[str, Any]
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    matches: list[dict[str, Any]] = Field(default_factory=list)


class RetainResponse(BaseModel):
    retained: dict[str, Any]


@router.post("/verify-claim", response_model=VerifyClaimResponse)
async def verify_claim(payload: VerifyClaimRequest) -> VerifyClaimResponse:
    """§30 five-question fact verification (deterministic, §93)."""
    try:
        from common_lib.modules.rip.rip_synthesis.verification import verify_fact

        out = verify_fact(
            claim=payload.claim,
            evidence=payload.evidence,
            matches=payload.matches,
            contradictions=payload.contradictions,
            claim_fact=payload.claim_fact,
            kb_id=payload.kb_id,
            valid_window=payload.valid_window,
            at_time=payload.at_time,
        )
        return VerifyClaimResponse(verification=out)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 — transport error mapping only
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/assess", response_model=AssessResponse)
async def assess_truth_route(payload: AssessRequest) -> AssessResponse:
    """§31 TruthAssessment assembly (deterministic status precedence)."""
    try:
        from common_lib.modules.rip.rip_synthesis.truth import assess_truth

        assessment = assess_truth(
            claim=payload.claim,
            answers=payload.answers,
            evidence=payload.evidence,
            supporting_evidence_ids=payload.supporting_evidence_ids,
            contradicting_evidence_ids=payload.contradicting_evidence_ids,
            temporal_scope=payload.temporal_scope,
            provenance=payload.provenance,
        )
        return AssessResponse(assessment=assessment.to_dict())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/contradictions", response_model=ContradictionsResponse)
async def detect_contradictions_route(payload: ContradictionsRequest) -> ContradictionsResponse:
    """§32/§33 deterministic claim-pair classification."""
    try:
        from common_lib.modules.rip.rip_synthesis.contradictions import (
            detect_contradictions,
        )

        return ContradictionsResponse(result=detect_contradictions(payload.claims))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/resolve", response_model=ResolveResponse)
async def resolve_contradiction_route(payload: ResolveRequest) -> ResolveResponse:
    """§34/§35 resolution outcome (never a silent winner)."""
    try:
        from common_lib.modules.rip.rip_synthesis.resolution import resolve_contradiction

        return ResolveResponse(resolution=resolve_contradiction(payload.contradiction))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/retain", response_model=RetainResponse)
async def retain_contradiction_route(payload: RetainRequest) -> RetainResponse:
    """§36 both-sides retention."""
    try:
        from common_lib.modules.rip.rip_synthesis.retention import (
            retain_contradiction_evidence,
        )

        retained = retain_contradiction_evidence(
            contradiction=payload.contradiction,
            evidence=payload.evidence,
            matches=payload.matches,
        )
        return RetainResponse(retained=retained)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
