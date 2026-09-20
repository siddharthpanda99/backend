"""Knowledge Engine — Retrieval Routes (Phase 8, Chunk 8.4).

Thin transport for ``knowledge.retrieve(...)`` (SSOT §32/§43).
Delegates to ``common_lib.modules.knowledge_engine.retrieval`` nodes;
no business logic here. API contract only — no UI in this phase.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from common_lib.modules.knowledge_engine.retrieval import nodes as retrieval_nodes

router = APIRouter(prefix="/retrieval", tags=["Knowledge Engine — Retrieval"])


class RetrieveRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4096)
    chunks: list[dict[str, Any]] = Field(default_factory=list)
    top_k: int = Field(default=20, ge=1, le=200)
    branch: str = Field(default="main")
    tenant_id: str | None = None
    knowledge_commit: str = Field(default="")


class RetrieveResponse(BaseModel):
    chunks: list[dict[str, Any]]
    meta: dict[str, Any] = Field(default_factory=dict)


class AssembleRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4096)
    chunks: list[dict[str, Any]] = Field(default_factory=list)
    max_tokens: int = Field(default=8000, ge=100, le=128000)
    knowledge_commit: str = Field(default="")


class AssembleResponse(BaseModel):
    context: dict[str, Any]


class StalenessRequest(BaseModel):
    knowledge_commit: str
    current_commit: str
    stamped_at: str | None = None


class StalenessResponse(BaseModel):
    stale: str
    reason: str


@router.post("/retrieve", response_model=RetrieveResponse)
async def retrieve(request: RetrieveRequest) -> RetrieveResponse:
    """Run multi-channel retrieval (SSOT §32 ``knowledge.retrieve``)."""
    try:
        result = retrieval_nodes.retrieve(
            {
                "query": request.query,
                "chunks": request.chunks,
                "top_k": request.top_k,
                "branch": request.branch,
                "tenant_id": request.tenant_id,
            }
        )
        return RetrieveResponse(**result)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Retrieval failed: {exc}") from exc


@router.post("/assemble", response_model=AssembleResponse)
async def assemble_context(request: AssembleRequest) -> AssembleResponse:
    """Pack ranked chunks into a token-budgeted context (§32)."""
    try:
        result = retrieval_nodes.assemble_context(
            {
                "query": request.query,
                "chunks": request.chunks,
                "max_tokens": request.max_tokens,
                "knowledge_commit": request.knowledge_commit,
            }
        )
        return AssembleResponse(**result)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Context assembly failed: {exc}"
        ) from exc


@router.post("/staleness", response_model=StalenessResponse)
async def check_staleness(request: StalenessRequest) -> StalenessResponse:
    """Check whether a stamped knowledge context is stale (§34)."""
    try:
        result = retrieval_nodes.check_context_staleness(
            {
                "knowledge_commit": request.knowledge_commit,
                "current_commit": request.current_commit,
                "stamped_at": request.stamped_at,
            }
        )
        return StalenessResponse(**result)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Staleness check failed: {exc}"
        ) from exc
