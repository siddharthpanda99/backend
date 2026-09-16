"""``app.modules.knowledge_engine.acquisition.routes.router`` — Nexus Cluster 4 transport.

Thin router layer (no business logic): every handler validates the request,
checks the Cluster 4 feature-flag gate, and delegates to `common_lib`
services. Auth is enforced at registration (`auth: True` in
`app/core/routers.py`); flag gates return 503 with an explicit message when
the cluster (or the endpoint's sub-flag) is OFF.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/context-acquisition", tags=["Nexus Context Acquisition"])


# ── Request models ──────────────────────────────────────────────


class ContextBuildRequest(BaseModel):
    system_instructions: str = ""
    memory_blocks: list[str] = Field(default_factory=list)
    evidence_items: list[dict[str, Any]] = Field(default_factory=list)
    contradictions: list[dict[str, Any]] = Field(default_factory=list)
    gaps: list[dict[str, Any]] = Field(default_factory=list)
    max_tokens: int = Field(default=8000, ge=100, le=200000)


class GapDetectRequest(BaseModel):
    query: str = Field(..., min_length=1)
    bundle: dict[str, Any] = Field(default_factory=dict)
    requirements: dict[str, Any] = Field(default_factory=dict)
    threshold: float = Field(default=0.7, ge=0.0, le=1.0)


class AcquisitionPlanRequest(BaseModel):
    query: str = Field(..., min_length=1)
    gaps: list[dict[str, Any]] = Field(default_factory=list)


# ── Flag guard ──────────────────────────────────────────────────


def _require_flag(flag_name: str) -> None:
    """503 when the master or a sub-flag gate is OFF (explicit, never silent)."""
    from common_lib.modules.rip.rip_context.flags import is_context_flag_enabled

    if not is_context_flag_enabled("NEXUS_CONTEXT_ACQUISITION_ENABLED"):
        raise HTTPException(
            status_code=503,
            detail="Nexus Cluster 4 disabled (NEXUS_CONTEXT_ACQUISITION_ENABLED=OFF)",
        )
    if not is_context_flag_enabled(flag_name):
        raise HTTPException(
            status_code=503, detail=f"Feature disabled ({flag_name}=OFF)"
        )


# ── Endpoints ───────────────────────────────────────────────────


@router.post("/context/build", response_model=dict[str, Any])
async def build_context(request: ContextBuildRequest):
    """Optimize evidence under the token budget, then assemble final context."""
    _require_flag("CONTEXT_BUDGET_OPTIMIZER_ENABLED")
    from common_lib.modules.rip.rip_context.assembler import assemble_final_context
    from common_lib.modules.rip.rip_context.budget_optimizer import (
        optimize_context_budget,
    )

    optimized = optimize_context_budget(
        request.evidence_items, max_tokens=request.max_tokens
    )
    assembled = assemble_final_context(
        system_instructions=request.system_instructions,
        memory_blocks=request.memory_blocks,
        evidence_items=optimized["admitted"],
        contradictions=request.contradictions,
        gaps=request.gaps,
        max_tokens=request.max_tokens,
    )
    return {
        **assembled,
        "admitted_count": len(optimized["admitted"]),
        "excluded": optimized["excluded"],
        "budget": optimized["budget"],
    }


@router.post("/gaps/detect", response_model=dict[str, Any])
async def detect_gaps(request: GapDetectRequest):
    """Evaluate sufficiency; classify + record gaps when evidence is thin."""
    _require_flag("KNOWLEDGE_GAP_DETECTION_ENABLED")
    from common_lib.modules.knowledge_engine.acquisition.gap_classifier import (
        classify_knowledge_gaps,
    )
    from common_lib.modules.knowledge_engine.acquisition.gap_ledger import (
        record_knowledge_gap,
    )
    from common_lib.modules.knowledge_engine.acquisition.sufficiency import (
        evaluate_evidence_sufficiency,
    )

    evaluation = evaluate_evidence_sufficiency(
        request.bundle, request.requirements, request.threshold
    )
    gaps: list[dict[str, Any]] = []
    if not evaluation["sufficient"]:
        classified = classify_knowledge_gaps(request.query, evaluation["unsatisfied"])
        for gap in classified["gaps"]:
            recorded = record_knowledge_gap(gap)
            gaps.append(recorded["gap"])
    return {"evaluation": evaluation, "gaps": gaps}


@router.post("/acquisition/plan", response_model=dict[str, Any])
async def plan_acquisition(request: AcquisitionPlanRequest):
    """Decompose gaps into sub-queries and route each to its best channel."""
    _require_flag("AUTONOMOUS_ACQUISITION_ENABLED")
    from common_lib.modules.knowledge_engine.acquisition.decomposition import (
        decompose_gap_queries,
    )
    from common_lib.modules.knowledge_engine.acquisition.source_selector import (
        select_acquisition_source,
    )

    decomposed = decompose_gap_queries(request.query, request.gaps)
    plan = []
    for gap in request.gaps:
        if not isinstance(gap, dict):
            continue
        selection = select_acquisition_source(gap)
        plan.append(
            {
                "gap_id": selection["gap_id"],
                "channel": selection["selected"],
                "ranking": selection["ranking"],
            }
        )
    return {"sub_queries": decomposed["sub_queries"], "plan": plan}


@router.get("/gaps/{gap_id}", response_model=dict[str, Any])
async def get_gap(gap_id: str):
    """Fetch a recorded knowledge gap by id (404 when unknown)."""
    _require_flag("KNOWLEDGE_GAP_DETECTION_ENABLED")
    from common_lib.modules.knowledge_engine.acquisition.gap_ledger import (
        get_gap as _get,
    )

    gap = _get(gap_id)
    if gap is None:
        raise HTTPException(status_code=404, detail=f"unknown gap {gap_id}")
    return {"gap": gap}
