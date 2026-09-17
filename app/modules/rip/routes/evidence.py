"""RIP Nexus evidence routes — thin transport for §55/§20 (chunk C053).

Thin-router discipline: no business logic here; delegation to
``common_lib.modules.rip.rip_synthesis.bundles`` and
``common_lib.modules.rip.rip_graph.evidence_graph`` (lazy imports in handlers).
Endpoints:
* ``POST /rip/evidence/bundle``         — §55 bundle assembly (C050/C050b)
* ``POST /rip/evidence/graph``          — §20 query-scoped evidence graph (C049)
* ``GET  /rip/evidence/graph/{query_id}`` — graph summary by query id (C049)
* ``POST /rip/evidence/promote``        — §20 promotion hook (C049)
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/rip/evidence", tags=["RIP — Nexus Evidence"])


class BundleRequest(BaseModel):
    query: str = Field(..., min_length=1)
    scope: str = Field(default="ALL_ALLOWED")
    requirements: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    claims: list[dict[str, Any]] = Field(default_factory=list)
    facts: list[dict[str, Any]] = Field(default_factory=list)
    entities: list[Any] = Field(default_factory=list)
    events: list[Any] = Field(default_factory=list)
    documents: list[Any] = Field(default_factory=list)
    memory: list[dict[str, Any]] = Field(default_factory=list)
    world_model: list[dict[str, Any]] = Field(default_factory=list)
    contradictions: list[dict[str, Any]] = Field(default_factory=list)
    gaps: list[dict[str, Any]] = Field(default_factory=list)
    coverage: dict[str, Any] = Field(default_factory=dict)
    confidence: str | None = None
    temporal_scope: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)
    retrieval_trace: dict[str, Any] = Field(default_factory=dict)
    permissions: dict[str, Any] = Field(default_factory=dict)


class BundleResponse(BaseModel):
    bundle: dict[str, Any]
    excluded_evidence: list[dict[str, Any]]


class GraphRequest(BaseModel):
    query_id: str = Field(..., min_length=1)
    scope: str = Field(default="ALL_ALLOWED")
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    claims: list[dict[str, Any]] = Field(default_factory=list)
    matches: list[dict[str, Any]] = Field(default_factory=list)
    contradictions: list[dict[str, Any]] = Field(default_factory=list)


class GraphResponse(BaseModel):
    graph: dict[str, Any]


class PromoteRequest(BaseModel):
    graph: dict[str, Any]
    node_ids: list[str]


class PromoteResponse(BaseModel):
    promotion: dict[str, Any]


@router.post("/bundle", response_model=BundleResponse)
async def assemble_bundle_route(payload: BundleRequest) -> BundleResponse:
    """§55 EvidenceBundle assembly (scope-gated, deterministic)."""
    try:
        from common_lib.modules.rip.rip_synthesis.bundles import assemble_bundle

        out = assemble_bundle(
            query=payload.query,
            scope=payload.scope,
            requirements=payload.requirements,
            evidence=payload.evidence,
            claims=payload.claims,
            facts=payload.facts,
            entities=payload.entities,
            events=payload.events,
            documents=payload.documents,
            memory=payload.memory,
            world_model=payload.world_model,
            contradictions=payload.contradictions,
            gaps=payload.gaps,
            coverage=payload.coverage,
            confidence=payload.confidence,
            temporal_scope=payload.temporal_scope,
            provenance=payload.provenance,
            retrieval_trace=payload.retrieval_trace,
            permissions=payload.permissions,
        )
        return BundleResponse(bundle=out["bundle"], excluded_evidence=out["excluded_evidence"])
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 — transport error mapping only
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/graph", response_model=GraphResponse)
async def build_graph_route(payload: GraphRequest) -> GraphResponse:
    """§20 query-scoped evidence graph (ephemeral, deterministic)."""
    try:
        from common_lib.modules.rip.rip_graph.evidence_graph import (
            build_evidence_graph,
        )

        graph = build_evidence_graph(
            query_id=payload.query_id,
            evidence=payload.evidence,
            claims=payload.claims,
            matches=payload.matches,
            contradictions=payload.contradictions,
            scope=payload.scope,
        )
        return GraphResponse(graph=graph)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/graph/{query_id}")
async def graph_summary_route(query_id: str) -> dict[str, Any]:
    """§20/§74 graph summary for a previously built (client-held) graph id."""
    try:
        from common_lib.modules.rip.rip_graph.evidence_graph import graph_summary

        # The graph itself is ephemeral (client-held); the summary endpoint
        # validates the query_id shape and documents the contract rather than
        # pretending server-side persistence exists (§97 explicit).
        if not query_id or len(query_id) < 1:
            raise ValueError("query_id required")
        return {
            "query_id": query_id,
            "note": "evidence graphs are ephemeral and client-held (§20); POST /rip/evidence/graph to build one",
            "summary_schema": graph_summary(
                {"nodes": [], "edges": [], "promoted": []}
            ),
        }
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/promote", response_model=PromoteResponse)
async def promote_artifacts_route(payload: PromoteRequest) -> PromoteResponse:
    """§20 promotion hook — mark artifacts for durable-KG handoff."""
    try:
        from common_lib.modules.rip.rip_graph.evidence_graph import promote_artifacts

        promotion = promote_artifacts(payload.graph, payload.node_ids)
        return PromoteResponse(promotion=promotion)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
