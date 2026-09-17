"""RIP Nexus answer routes — thin transport for §56/§61 (chunk C069).

Thin-router discipline: no business logic here; delegation to
``common_lib.modules.rip.rip_synthesis.*`` (lazy imports inside handlers).
Endpoints:
* ``POST /rip/answer/contract``  — §56 pre-generation AnswerContract (C066)
* ``POST /rip/answer/verify``    — §59-§61 post-generation verification +
                                   ReliabilityVector (C068)
* ``POST /rip/answer/generate``  — §57/§58 rule check over a client-generated
                                   answer (rules enforcement; C067)

The route intentionally does NOT own an LLM: generation stays with the agent
runtime; this surface binds answers to the §56 contract + §57 rules + §59
verification so every answer ships with an auditable ReliabilityVector.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/rip/answer", tags=["RIP — Nexus Answer"])


class ContractRequest(BaseModel):
    plan: dict[str, Any]
    coverage: dict[str, Any] | None = None


class ContractResponse(BaseModel):
    contract: dict[str, Any]


class VerifyRequest(BaseModel):
    answer: str = Field(..., min_length=1)
    contract: dict[str, Any] = Field(default_factory=dict)
    context_items: list[dict[str, Any]] = Field(default_factory=list)
    bundle: dict[str, Any] | None = None


class VerifyResponse(BaseModel):
    verification: dict[str, Any]


class GenerateCheckRequest(BaseModel):
    answer: str = Field(..., min_length=1)
    contract: dict[str, Any] = Field(default_factory=dict)
    coverage_ok: bool = True
    flagged_claims: list[str] = Field(default_factory=list)
    contradictions: list[dict[str, Any]] = Field(default_factory=list)
    memory_items: list[dict[str, Any]] = Field(default_factory=list)
    scope_documents: list[str] = Field(default_factory=list)


class GenerateCheckResponse(BaseModel):
    check: dict[str, Any]


@router.post("/contract", response_model=ContractResponse)
async def build_contract_route(payload: ContractRequest) -> ContractResponse:
    """§56 AnswerContract — emitted pre-generation from plan + coverage."""
    try:
        from common_lib.modules.rip.rip_synthesis.answer_contract import (
            build_answer_contract,
        )

        return ContractResponse(
            contract=build_answer_contract(payload.plan, payload.coverage)["contract"]
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/generate", response_model=GenerateCheckResponse)
async def check_generation_route(payload: GenerateCheckRequest) -> GenerateCheckResponse:
    """§57/§58 generation-rules enforcement over a generated answer."""
    try:
        from common_lib.modules.rip.rip_synthesis.answer_rules import (
            check_generation_rules,
        )

        check = check_generation_rules(
            payload.answer,
            payload.contract,
            payload.coverage_ok,
            payload.flagged_claims,
            payload.contradictions,
            payload.memory_items,
            payload.scope_documents,
        )
        return GenerateCheckResponse(check=check)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/verify", response_model=VerifyResponse)
async def verify_answer_route(payload: VerifyRequest) -> VerifyResponse:
    """§59-§61 claim-to-evidence verification + ReliabilityVector."""
    try:
        from common_lib.modules.rip.rip_synthesis.answer_verification import (
            verify_answer,
        )

        verification = verify_answer(
            payload.answer,
            payload.contract,
            payload.context_items,
            payload.bundle,
        )
        return VerifyResponse(verification=verification)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
