"""Graph-benchmark routes — thin delegates to common_lib (NEX-P6-002).

All logic lives in
``common_lib.modules.knowledge_engine.retrieval.graph_benchmark``.
Every endpoint except ``/status`` answers 404 while the flag
``knowledge_engine.retrieval.graph_benchmark.enabled`` is OFF (the
feature does not exist from the client's point of view until enabled).
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/graph-benchmark", tags=["Knowledge Graph Benchmark"])

_FLAG = "knowledge_engine.retrieval.graph_benchmark.enabled"


def _require_enabled() -> None:
    try:
        from common_lib.modules.knowledge_engine.retrieval.graph_benchmark.flags import (
            is_enabled as _enabled,
        )
    except ImportError:
        raise HTTPException(status_code=404, detail="Graph benchmark unavailable")
    if _enabled(_FLAG):
        return
    raise HTTPException(
        status_code=404,
        detail=(
            "Graph benchmark is gated behind the feature flag "
            f"'{_FLAG}', which is currently OFF. Enable "
            "GRAPH_BENCHMARK_ENABLED=true and restart."
        ),
    )


def _service():
    from common_lib.modules.knowledge_engine.retrieval.graph_benchmark.service import (
        get_graph_benchmark_service,
    )

    return get_graph_benchmark_service()


class CompareRequest(BaseModel):
    top_k: int = Field(default=20, ge=1, le=100)
    token_budget: int = Field(default=4000, ge=100)


@router.get("/status")
def benchmark_status() -> dict[str, Any]:
    """Flag state + available suites (always visible, never 404)."""
    return dict(_service().status())


@router.post("/compare")
def benchmark_compare(body: CompareRequest) -> dict[str, Any]:
    """Graph branch vs baseline: win/hold/loss + latency + rollback."""
    _require_enabled()
    return dict(_service().compare(top_k=body.top_k, token_budget=body.token_budget))


@router.post("/entity-resolution")
def benchmark_entity_resolution() -> dict[str, Any]:
    """Curated entity-resolution eval (mention → canonical entity)."""
    _require_enabled()
    return dict(_service().entity_resolution_eval())


@router.post("/edge-extraction")
def benchmark_edge_extraction() -> dict[str, Any]:
    """Curated edge-extraction eval (sentence → S/P/O triple)."""
    _require_enabled()
    return dict(_service().edge_extraction_eval())


__all__ = ["router"]
