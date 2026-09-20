"""Knowledge Engine — Search Routes (Phase 8, Chunk 8.4).

Thin transport for lexical search, reranking, evidence expansion, and
retrieval conflict detection (SSOT §32 stages). Delegates to
``common_lib.modules.knowledge_engine.retrieval`` nodes; no business
logic here. API contract only — no UI in this phase.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from common_lib.modules.knowledge_engine.retrieval import nodes as retrieval_nodes

router = APIRouter(prefix="/search", tags=["Knowledge Engine — Search"])


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4096)
    chunks: list[dict[str, Any]] = Field(default_factory=list)
    top_k: int = Field(default=10, ge=1, le=200)


class SearchResponse(BaseModel):
    chunks: list[dict[str, Any]]


class RerankRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4096)
    chunks: list[dict[str, Any]] = Field(default_factory=list)
    top_k: int = Field(default=10, ge=1, le=200)


class RerankResponse(BaseModel):
    chunks: list[dict[str, Any]]


class EvidenceRequest(BaseModel):
    chunks: list[dict[str, Any]] = Field(default_factory=list)
    evidence_index: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)


class EvidenceResponse(BaseModel):
    chunks: list[dict[str, Any]]


class ConflictScanRequest(BaseModel):
    chunks: list[dict[str, Any]] = Field(default_factory=list)


class ConflictScanResponse(BaseModel):
    chunks: list[dict[str, Any]]
    report: dict[str, Any] = Field(default_factory=dict)


@router.post("", response_model=SearchResponse)
async def search(request: SearchRequest) -> SearchResponse:
    """Lexical-first keyword search (SSOT §32 lexical channel)."""
    try:
        result = retrieval_nodes.search(
            {
                "query": request.query,
                "chunks": request.chunks,
                "top_k": request.top_k,
            }
        )
        return SearchResponse(**result)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Search failed: {exc}") from exc


@router.post("/rerank", response_model=RerankResponse)
async def rerank(request: RerankRequest) -> RerankResponse:
    """Rerank candidates (SSOT §32 rerank stage)."""
    try:
        result = retrieval_nodes.rerank_candidates(
            {
                "query": request.query,
                "chunks": request.chunks,
                "top_k": request.top_k,
            }
        )
        return RerankResponse(**result)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Rerank failed: {exc}") from exc


@router.post("/evidence", response_model=EvidenceResponse)
async def expand_evidence(request: EvidenceRequest) -> EvidenceResponse:
    """Expand supporting evidence for candidates (§10/§32)."""
    try:
        result = retrieval_nodes.expand_evidence(
            {
                "chunks": request.chunks,
                "evidence_index": request.evidence_index,
            }
        )
        return EvidenceResponse(**result)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Evidence expansion failed: {exc}"
        ) from exc


@router.post("/conflicts", response_model=ConflictScanResponse)
async def scan_conflicts(request: ConflictScanRequest) -> ConflictScanResponse:
    """Detect disagreement among candidates (§14)."""
    try:
        result = retrieval_nodes.detect_retrieval_conflicts({"chunks": request.chunks})
        return ConflictScanResponse(**result)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Conflict scan failed: {exc}"
        ) from exc
