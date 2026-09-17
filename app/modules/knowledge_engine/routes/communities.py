"""Community & global-understanding routes — GU-020 (SSOT §40, Wave GU-5).

Thin transport for the Nexus Global Understanding engine (Cluster 3 waves
GU-0..4). No business logic — lazy delegation into
``common_lib.modules.knowledge_engine.communities.*`` and
``common_lib.modules.rip.*``:

* ``POST /communities/search/global`` — global map-reduce query (GU-011)
* ``POST /communities/search/local``  — local subgraph search (GU-012)
* ``GET  /communities/hierarchy``     — build hierarchy for posted graph (GU-003, body POST-free variant GETs stored report set)
* ``GET  /communities/reports/{id}``  — one community report (GU-007 store)

All endpoints are gated by ``NEXUS_GLOBAL_UNDERSTANDING_ENABLED`` (503 when
off — default). Never raises to the client; structured errors only.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from common_lib.modules.knowledge_engine.communities.flags import (
    NEXUS_GLOBAL_UNDERSTANDING_ENABLED,
)

router = APIRouter(prefix="/communities", tags=["Knowledge Engine — Communities"])


def _require_engine() -> None:
    """Fail-fast gate: cluster flag off ⇒ 503 (flag is default-OFF)."""
    from common_lib.modules.knowledge_engine.communities.flags import (
        is_community_flag_enabled,
    )

    if not is_community_flag_enabled(NEXUS_GLOBAL_UNDERSTANDING_ENABLED):
        raise HTTPException(
            status_code=503,
            detail=(
                "Global understanding engine is disabled "
                "(NEXUS_GLOBAL_UNDERSTANDING_ENABLED)"
            ),
        )


def _result(outcome: dict[str, Any], key: str | None = None) -> dict[str, Any]:
    """Normalize a never-raises service dict into a response (error ⇒ 502).

    Orchestrator outputs nest under ``key`` (e.g. ``result``); the error
    check unwraps that level too.
    """
    payload = outcome.get(key) if (key and isinstance(outcome, dict)) else outcome
    target = payload if isinstance(payload, dict) else outcome
    if isinstance(target, dict) and target.get("error"):
        raise HTTPException(status_code=502, detail=target["error"])
    return outcome


class GlobalSearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_fraction: float = Field(default=0.5, gt=0.0, le=1.0)
    relevance_threshold: float = Field(default=40.0, ge=0.0, le=100.0)
    batch_token_budget: int = Field(default=3000, ge=256)
    tenant_id: str | None = None


class LocalSearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    max_hops: int = Field(default=2, ge=1, le=2)
    graph_nodes: list[dict[str, Any]] = Field(default_factory=list)
    graph_edges: list[dict[str, Any]] = Field(default_factory=list)
    chunks: list[dict[str, Any]] = Field(default_factory=list)


class HierarchyRequest(BaseModel):
    graph_nodes: list[dict[str, Any]] = Field(..., min_length=1)
    graph_edges: list[dict[str, Any]] = Field(default_factory=list)
    levels: int = Field(default=3, ge=1, le=5)
    algorithm: str = "leiden"


@router.post("/search/global")
def search_global(body: GlobalSearchRequest) -> dict[str, Any]:
    """GraphRAG-style global map-reduce query over community reports."""
    _require_engine()
    try:
        from common_lib.modules.knowledge_engine.communities.global_orchestrator import (
            execute_global_query,
        )
        from common_lib.modules.knowledge_engine.communities.report_store import (
            get_report_store,
        )

        reports = [r.to_dict() for r in get_report_store().list_all()]
        return _result(
            execute_global_query(
                body.query,
                reports,
                top_fraction=body.top_fraction,
                relevance_threshold=body.relevance_threshold,
                batch_token_budget=body.batch_token_budget,
                tenant_id=body.tenant_id,
            ),
            key="result",
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 — structured errors only
        raise HTTPException(status_code=502, detail=f"global search failed: {exc}") from exc


@router.post("/search/local")
def search_local(body: LocalSearchRequest) -> dict[str, Any]:
    """LightRAG-style local subgraph search (1-2 hop neighborhoods)."""
    _require_engine()
    try:
        from common_lib.modules.rip.rip_graph.graph import KnowledgeGraphService
        from common_lib.modules.rip.rip_retrieval.local_search import (
            execute_local_search,
        )

        graph = KnowledgeGraphService()
        graph.build(body.graph_nodes, body.graph_edges)
        return _result(execute_local_search(body.query, graph, body.chunks, body.max_hops))
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 — structured errors only
        raise HTTPException(status_code=502, detail=f"local search failed: {exc}") from exc


@router.post("/hierarchy")
def build_hierarchy(body: HierarchyRequest) -> dict[str, Any]:
    """Build the multi-level community hierarchy for a posted graph."""
    _require_engine()
    try:
        from common_lib.modules.knowledge_engine.communities.hierarchy_adapter import (
            build_community_hierarchy,
        )

        import asyncio

        return _result(
            asyncio.run(
                build_community_hierarchy(
                    body.graph_nodes, body.graph_edges,
                    levels=body.levels, algorithm=body.algorithm,
                )
            )
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 — structured errors only
        raise HTTPException(status_code=502, detail=f"hierarchy build failed: {exc}") from exc


@router.get("/reports/{report_id}")
def get_report(report_id: str) -> dict[str, Any]:
    """Fetch one community report by id (404 when absent)."""
    _require_engine()
    try:
        from common_lib.modules.knowledge_engine.communities.report_store import (
            get_report_store,
        )

        report = get_report_store().get(report_id)
        if report is None:
            raise HTTPException(status_code=404, detail=f"report {report_id} not found")
        return report.to_dict()
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 — structured errors only
        raise HTTPException(status_code=502, detail=f"report lookup failed: {exc}") from exc
