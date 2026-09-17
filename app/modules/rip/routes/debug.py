"""RIP Nexus retrieval-debugger route — thin transport for §75 (chunk C080).

Dev-only, flag-gated by NEXUS_RETRIEVAL_DEBUGGER_ENABLED (default OFF).
Thin-router discipline: no business logic; delegation to
``common_lib.modules.rip.rip_evolution.debugger`` (lazy import).
Endpoint: ``POST /rip/debug/retrieval``.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/rip/debug", tags=["RIP — Nexus Debug"])


class DebugRequest(BaseModel):
    query_id: str = Field(..., min_length=1)
    retrieval_trace: dict[str, Any] | None = None
    coverage_report: dict[str, Any] | None = None
    evidence_bundle: dict[str, Any] | None = None
    answer_verification: dict[str, Any] | None = None


class DebugResponse(BaseModel):
    payload: dict[str, Any]


@router.post("/retrieval", response_model=DebugResponse)
async def retrieval_debug(payload: DebugRequest):
    """§75 debugger payload (flag-gated; 403 when the flag is off)."""
    try:
        from common_lib.modules.rip.rip_evolution.debugger import build_debug_payload

        result = build_debug_payload(
            query_id=payload.query_id,
            retrieval_trace=payload.retrieval_trace,
            coverage_report=payload.coverage_report,
            evidence_bundle=payload.evidence_bundle,
            answer_verification=payload.answer_verification,
        )
        if not result.get("debug_enabled"):
            raise HTTPException(status_code=403, detail="retrieval debugger disabled (NEXUS_RETRIEVAL_DEBUGGER_ENABLED off)")
        return {"payload": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
