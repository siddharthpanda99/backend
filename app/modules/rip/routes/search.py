"""RIP Search routes — Unified, BM25, dense, sparse, hybrid search + reranking.

Implements endpoints 11.8–11.13 from the implementation tracker.
All retrieval routes now use the RIP Connector layer to call real model providers.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from pydantic import BaseModel, Field

from common_lib.modules.rip.rip_retrieval.schemas import (
    SearchRequest,
    SearchResponse,
    BM25SearchRequest,
    DenseSearchRequest,
    SparseSearchRequest,
    HybridSearchRequest,
    RetrievalResult,
)
from common_lib.modules.rip.rip_connectors import (
    create_embed_fn,
    create_llm_fn,
    create_cross_encoder_fn,
    create_colbert_fn,
)

router = APIRouter(prefix="/rip/search", tags=["RIP — Search"])


# --- Nexus Wave 3 (C028 ext, SSOT §16): optional `channels` query param -------
# Additive-only hook for the pre-existing search endpoints below. Absent (None)
# → existing behavior byte-identical (no flag check, same retrieval path).
# Present → validated against the 10 C022 channels (400 on unknown) with a 503
# when NEXUS_RETRIEVAL_CHANNELS_ENABLED is off (C021 flag-off pattern). The
# validated selection is a forward-compat routing hint; retrieval itself is
# unchanged. Real channel execution lives in /channels, /structural,
# /exhaustive, /mode.


def _validate_channels_param(channels: Optional[str]) -> Optional[list[str]]:
    """Validate an optional comma-separated §16 channel list (C028).

    Returns the validated selection, or None when absent. Raises 400 on
    unknown names, 503 when the channels flag is off and a selection was
    given. Never gates the legacy path: absent → None, no flag check.
    """
    if channels is None or not channels.strip():
        return None
    from common_lib.modules.rip.feature_flags import is_enabled
    from common_lib.modules.rip.rip_retrieval.channels import CHANNELS

    if not is_enabled("NEXUS_RETRIEVAL_CHANNELS_ENABLED"):
        raise HTTPException(
            status_code=503, detail="NEXUS_RETRIEVAL_CHANNELS_ENABLED is off"
        )
    selected = [c.strip().lower() for c in channels.split(",") if c.strip()]
    unknown = [c for c in selected if c not in CHANNELS]
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"unknown retrieval channels: {unknown}; valid: {list(CHANNELS)}",
        )
    return selected


@router.post("", response_model=SearchResponse)
async def unified_search(
    payload: SearchRequest,
    channels: Optional[str] = Query(
        default=None,
        description=(
            "Optional comma-separated SSOT §16 retrieval-channel subset "
            "(10 C022 channels). Absent = existing behavior."
        ),
    ),
):
    """Unified hybrid search — auto-routes to the best retriever(s).

    By default uses BM25 + dense with RRF fusion.
    Specify `retrievers` to customise the set.
    """
    _validate_channels_param(channels)
    try:
        from common_lib.modules.rip.rip_retrieval.service import hybrid_search
        import time

        start = time.perf_counter()
        results = await hybrid_search(
            query=payload.query,
            top_k=payload.top_k * 2 if payload.reranker else payload.top_k,
            filters=payload.filters,
            tenant_id=payload.tenant_id,
        )
        elapsed = (time.perf_counter() - start) * 1000

        # Apply reranking if specified — uses real cross-encoder/LLM via connectors
        if payload.reranker and results:
            try:
                from common_lib.modules.rip.rip_reranking.service import rerank_results

                # Create connectors matching the selected reranker method
                rerank_kwargs = {}
                if payload.reranker == "cross_encoder":
                    rerank_kwargs["cross_encoder_fn"] = await create_cross_encoder_fn()
                elif payload.reranker == "llm":
                    rerank_kwargs["llm_fn"] = await create_llm_fn()

                reranked = await rerank_results(
                    query=payload.query,
                    results=list(results),
                    method=payload.reranker
                    if payload.reranker != "none"
                    else "cross_encoder",
                    top_k=payload.top_k,
                    **rerank_kwargs,
                )
                results = reranked
            except Exception:
                results = results[: payload.top_k]
        else:
            results = results[: payload.top_k]

        return SearchResponse(
            results=[
                RetrievalResult(
                    chunk_id=getattr(r, "chunk_id", getattr(r, "id", str(i))),
                    document_id=getattr(r, "document_id", ""),
                    document_title=getattr(r, "document_title", ""),
                    content=getattr(r, "content", str(r)),
                    score=getattr(r, "score", 0.0),
                    rank=i,
                    source=getattr(r, "source", "hybrid"),
                    metadata=getattr(r, "metadata", {}),
                    reranked_score=getattr(r, "reranked_score", None),
                )
                for i, r in enumerate(results)
            ],
            total_results=len(results),
            query=payload.query,
            retrievers_used=payload.retrievers,
            fusion_method=payload.fusion_method,
            latency_ms=elapsed,
            total_time_ms=elapsed,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/bm25", response_model=SearchResponse)
async def bm25_search(
    payload: BM25SearchRequest,
    channels: Optional[str] = Query(
        default=None,
        description=(
            "Optional comma-separated SSOT §16 retrieval-channel subset "
            "(10 C022 channels). Absent = existing behavior."
        ),
    ),
):
    """BM25 lexical search — exact term matching with term-frequency saturation."""
    _validate_channels_param(channels)
    try:
        from common_lib.modules.rip.rip_retrieval.service import bm25_search
        import time

        start = time.perf_counter()
        results = await bm25_search(
            query=payload.query,
            top_k=payload.top_k,
            filters=payload.filters,
            tenant_id=payload.tenant_id,
        )
        elapsed = (time.perf_counter() - start) * 1000

        return SearchResponse(
            results=[
                RetrievalResult(
                    chunk_id=getattr(r, "chunk_id", getattr(r, "id", str(i))),
                    document_id=getattr(r, "document_id", ""),
                    document_title=getattr(r, "document_title", ""),
                    content=getattr(r, "content", str(r)),
                    score=getattr(r, "score", 0.0),
                    rank=i,
                    source="bm25",
                    metadata=getattr(r, "metadata", {}),
                )
                for i, r in enumerate(results)
            ],
            total_results=len(results),
            query=payload.query,
            retrievers_used=["bm25"],
            latency_ms=elapsed,
            total_time_ms=elapsed,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/dense", response_model=SearchResponse)
async def dense_search(
    payload: DenseSearchRequest,
    channels: Optional[str] = Query(
        default=None,
        description=(
            "Optional comma-separated SSOT §16 retrieval-channel subset "
            "(10 C022 channels). Absent = existing behavior."
        ),
    ),
):
    """Dense vector search — semantic similarity via embeddings.

    Uses the RIP Connector layer to call real embedding models (OpenAI, BGE-M3,
    or SentenceTransformers) based on the model_name field.
    """
    _validate_channels_param(channels)
    try:
        from common_lib.modules.rip.rip_retrieval.service import dense_search
        import time

        # Create real embed_fn from connector layer using the requested model
        embed_fn = await create_embed_fn(
            model_name=payload.model_name,
            device="cpu",
            batch_size=64,
        )

        start = time.perf_counter()
        results = await dense_search(
            query=payload.query,
            top_k=payload.top_k,
            model_name=payload.model_name,
            distance_metric=payload.distance_metric,
            filters=payload.filters,
            tenant_id=payload.tenant_id,
            embed_fn=embed_fn,
        )
        elapsed = (time.perf_counter() - start) * 1000

        return SearchResponse(
            results=[
                RetrievalResult(
                    chunk_id=getattr(r, "chunk_id", getattr(r, "id", str(i))),
                    document_id=getattr(r, "document_id", ""),
                    document_title=getattr(r, "document_title", ""),
                    content=getattr(r, "content", str(r)),
                    score=getattr(r, "score", 0.0),
                    rank=i,
                    source="dense",
                    metadata=getattr(r, "metadata", {}),
                )
                for i, r in enumerate(results)
            ],
            total_results=len(results),
            query=payload.query,
            retrievers_used=["dense"],
            latency_ms=elapsed,
            total_time_ms=elapsed,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sparse", response_model=SearchResponse)
async def sparse_search(
    payload: SparseSearchRequest,
    channels: Optional[str] = Query(
        default=None,
        description=(
            "Optional comma-separated SSOT §16 retrieval-channel subset "
            "(10 C022 channels). Absent = existing behavior."
        ),
    ),
):
    """Sparse learned search (SPLADE-style) — term expansion via transformer."""
    _validate_channels_param(channels)
    try:
        from common_lib.modules.rip.rip_retrieval.service import sparse_search
        import time

        start = time.perf_counter()
        results = await sparse_search(
            query=payload.query,
            top_k=payload.top_k,
            expansion_factor=payload.expansion_factor,
            filters=payload.filters,
            tenant_id=payload.tenant_id,
        )
        elapsed = (time.perf_counter() - start) * 1000

        return SearchResponse(
            results=[
                RetrievalResult(
                    chunk_id=getattr(r, "chunk_id", getattr(r, "id", str(i))),
                    document_id=getattr(r, "document_id", ""),
                    document_title=getattr(r, "document_title", ""),
                    content=getattr(r, "content", str(r)),
                    score=getattr(r, "score", 0.0),
                    rank=i,
                    source="sparse",
                    metadata=getattr(r, "metadata", {}),
                )
                for i, r in enumerate(results)
            ],
            total_results=len(results),
            query=payload.query,
            retrievers_used=["sparse"],
            latency_ms=elapsed,
            total_time_ms=elapsed,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/colbert", response_model=SearchResponse)
async def colbert_search_endpoint(
    payload: DenseSearchRequest,
    channels: Optional[str] = Query(
        default=None,
        description=(
            "Optional comma-separated SSOT §16 retrieval-channel subset "
            "(10 C022 channels). Absent = existing behavior."
        ),
    ),
):
    """ColBERT late interaction search via RAGatouille.

    Uses the RIP Connector layer to load a real ColBERTv2 model
    and perform multi-vector MaxSim scoring.
    """
    _validate_channels_param(channels)
    try:
        from common_lib.modules.rip.rip_retrieval.colbert import colbert_search
        import time

        # Create real colbert_fn from connector layer
        colbert_fn = await create_colbert_fn(
            model_name=payload.model_name or "colbertv2.0",
            device="cpu",
        )

        start = time.perf_counter()
        results = await colbert_search(
            query=payload.query,
            colbert_fn=colbert_fn,
            top_k=payload.top_k,
            model=payload.model_name or "colbertv2.0",
            use_plaid=True,
        )
        elapsed = (time.perf_counter() - start) * 1000

        items = results.get("results", [])

        return SearchResponse(
            results=[
                RetrievalResult(
                    chunk_id=r.get("chunk_id", r.get("id", str(i))),
                    document_id=r.get("document_id", r.get("passage_id", "")),
                    document_title=r.get("document_title", ""),
                    content=r.get("content", ""),
                    score=r.get("score", 0.0),
                    rank=i,
                    source="colbert",
                    metadata=r.get("metadata", {}),
                )
                for i, r in enumerate(items)
            ],
            total_results=len(items),
            query=payload.query,
            retrievers_used=["colbert"],
            latency_ms=elapsed,
            total_time_ms=elapsed,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/hybrid", response_model=SearchResponse)
async def hybrid_search_endpoint(
    payload: HybridSearchRequest,
    channels: Optional[str] = Query(
        default=None,
        description=(
            "Optional comma-separated SSOT §16 retrieval-channel subset "
            "(10 C022 channels). Absent = existing behavior."
        ),
    ),
):
    """Hybrid search — BM25 + dense + optional sparse with configurable weights and fusion."""
    _validate_channels_param(channels)
    try:
        from common_lib.modules.rip.rip_retrieval.service import hybrid_search
        import time

        start = time.perf_counter()
        results = await hybrid_search(
            query=payload.query,
            top_k=payload.top_k,
            filters=payload.filters,
            tenant_id=payload.tenant_id,
        )
        elapsed = (time.perf_counter() - start) * 1000

        # Apply reranker if specified — uses real cross-encoder/LLM
        if payload.reranker and results:
            try:
                from common_lib.modules.rip.rip_reranking.service import rerank_results

                rerank_kwargs = {}
                if payload.reranker == "cross_encoder":
                    rerank_kwargs["cross_encoder_fn"] = await create_cross_encoder_fn()
                elif payload.reranker == "llm":
                    rerank_kwargs["llm_fn"] = await create_llm_fn()

                reranked = await rerank_results(
                    query=payload.query,
                    results=list(results),
                    method=payload.reranker
                    if payload.reranker != "none"
                    else "cross_encoder",
                    top_k=payload.top_k,
                    **rerank_kwargs,
                )
                results = reranked
            except Exception:
                results = results[: payload.top_k]
        else:
            results = results[: payload.top_k]

        return SearchResponse(
            results=[
                RetrievalResult(
                    chunk_id=getattr(r, "chunk_id", getattr(r, "id", str(i))),
                    document_id=getattr(r, "document_id", ""),
                    document_title=getattr(r, "document_title", ""),
                    content=getattr(r, "content", str(r)),
                    score=getattr(r, "score", 0.0),
                    rank=i,
                    source="hybrid",
                    metadata=getattr(r, "metadata", {}),
                    reranked_score=getattr(r, "reranked_score", None),
                )
                for i, r in enumerate(results)
            ],
            total_results=len(results),
            query=payload.query,
            retrievers_used=["bm25", "dense", "sparse"]
            if payload.sparse_weight > 0
            else ["bm25", "dense"],
            fusion_method=payload.fusion_method,
            latency_ms=elapsed,
            total_time_ms=elapsed,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Nexus Wave 3 (C028, SSOT §16): channel params + plan-driven search -------
# Thin delegation to common_lib channel runner; stateless (inline doc corpus).


class ChannelSearchRequest(BaseModel):
    """Plan-driven channel search over an inline document set (no storage)."""

    query: str = Field(..., min_length=1)
    query_types: Optional[list[str]] = Field(default=None)
    channels: Optional[list[str]] = Field(default=None)
    documents: dict[str, str] = Field(default_factory=dict)
    inventories: list[dict] = Field(default_factory=list)
    top_k: int = Field(default=10, ge=1, le=50)


@router.post("/channels", response_model=dict)
async def channel_search(payload: ChannelSearchRequest):
    """Run SSOT §16 retrieval channels selected from the query plan.

    When `query_types` is omitted, the W1 planner classifies the query first.
    When `channels` is omitted, the plan selects them. Stateless: pass the
    document corpus inline (no storage — R3).
    """
    try:
        from common_lib.modules.rip.feature_flags import is_enabled
        from common_lib.modules.rip.rip_retrieval.channels import (
            run_channels,
            select_channels,
        )

        if not is_enabled("NEXUS_RETRIEVAL_CHANNELS_ENABLED"):
            raise HTTPException(
                status_code=503, detail="NEXUS_RETRIEVAL_CHANNELS_ENABLED is off"
            )
        plan: dict
        if payload.query_types is None:
            from common_lib.modules.rip.rip_router.plan import build_query_plan

            plan = build_query_plan(payload.query)["plan"]
        else:
            plan = {
                "query": payload.query,
                "query_types": payload.query_types,
                "requirements": {},
                "retrieval_modes": ["LOCAL"],
                "memory_policy": "DISABLED",
                "completeness_level": "MODERATE",
                "scope": "CURRENT_DOCUMENT",
            }
        channels = payload.channels or select_channels(plan)["channels"]
        ctx = {
            "documents": payload.documents,
            "inventories": payload.inventories,
            "query_types": plan.get("query_types"),
            "top_k": payload.top_k,
        }
        return {
            "plan_query_types": plan.get("query_types"),
            "channels": channels,
            "results": run_channels(channels, payload.query, ctx),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Nexus Wave 3 (C028 ext, SSOT §17/§18/§19/§66): channel gap endpoints -----
# Thin delegation to the C023/C025/C026 surfaces; stateless inline inputs.
# Each is 503 when NEXUS_RETRIEVAL_CHANNELS_ENABLED is off (C021 pattern).


class StructuralSearchRequest(BaseModel):
    """Structure-aware retrieval over inline C019 structural chunks."""

    query: str = Field(..., min_length=1)
    chunks: list[dict] = Field(default_factory=list)
    query_types: Optional[list[str]] = Field(default=None)
    top_k: int = Field(default=10, ge=1, le=50)


@router.post("/structural", response_model=dict)
async def structural_search_endpoint(payload: StructuralSearchRequest):
    """Structural retrieval + §18 expansion (§17/§18, C023) over inline chunks."""
    try:
        from common_lib.modules.rip.feature_flags import is_enabled
        from common_lib.modules.rip.rip_retrieval.structural import (
            structural_retrieve,
        )

        if not is_enabled("NEXUS_RETRIEVAL_CHANNELS_ENABLED"):
            raise HTTPException(
                status_code=503, detail="NEXUS_RETRIEVAL_CHANNELS_ENABLED is off"
            )
        return structural_retrieve(
            query=payload.query,
            chunks=payload.chunks,
            query_types=payload.query_types,
            top_k=payload.top_k,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ExhaustiveSearchRequest(BaseModel):
    """Exhaustive (NOT top-K) retrieval over inline C016 inventories."""

    query: str = Field(..., min_length=1)
    inventories: list[dict] = Field(default_factory=list)


@router.post("/exhaustive", response_model=dict)
async def exhaustive_search_endpoint(payload: ExhaustiveSearchRequest):
    """Exhaustive mention-universe retrieval (§19, C025) over inline inventories."""
    try:
        from common_lib.modules.rip.feature_flags import is_enabled
        from common_lib.modules.rip.rip_retrieval.exhaustive import (
            exhaustive_retrieve,
        )

        if not is_enabled("NEXUS_RETRIEVAL_CHANNELS_ENABLED"):
            raise HTTPException(
                status_code=503, detail="NEXUS_RETRIEVAL_CHANNELS_ENABLED is off"
            )
        return exhaustive_retrieve(
            query=payload.query,
            inventories=payload.inventories,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ModeSearchRequest(BaseModel):
    """Local/global/hybrid/adaptive mode execution over an inline corpus."""

    query: str = Field(..., min_length=1)
    mode: Optional[str] = Field(
        default=None,
        description="LOCAL | GLOBAL | HYBRID | ADAPTIVE. Omitted → plan-chosen.",
    )
    query_types: Optional[list[str]] = Field(default=None)
    retrieval_modes: Optional[list[str]] = Field(default=None)
    scope: Optional[str] = Field(default=None)
    completeness_level: Optional[str] = Field(default=None)
    documents: dict[str, str] = Field(default_factory=dict)
    inventories: list[dict] = Field(default_factory=list)
    top_k: int = Field(default=10, ge=1, le=50)


@router.post("/mode", response_model=dict)
async def mode_search_endpoint(payload: ModeSearchRequest):
    """Run a §66 retrieval mode (§65/§66, C026) over the inline corpus.

    When `mode` is omitted, the W1 planner classifies the query and the
    deterministic mode chooser picks LOCAL/GLOBAL/HYBRID/ADAPTIVE.
    """
    try:
        from common_lib.modules.rip.feature_flags import is_enabled
        from common_lib.modules.rip.rip_router.modes import choose_mode, run_mode

        if not is_enabled("NEXUS_RETRIEVAL_CHANNELS_ENABLED"):
            raise HTTPException(
                status_code=503, detail="NEXUS_RETRIEVAL_CHANNELS_ENABLED is off"
            )
        mode = (payload.mode or "").strip().upper() or None
        if mode is not None and mode not in (
            "LOCAL",
            "GLOBAL",
            "HYBRID",
            "ADAPTIVE",
        ):
            raise HTTPException(
                status_code=400,
                detail=f"unknown retrieval mode: {payload.mode}; "
                "valid: LOCAL, GLOBAL, HYBRID, ADAPTIVE",
            )
        if mode is None:
            plan: dict
            if payload.query_types is None:
                from common_lib.modules.rip.rip_router.plan import build_query_plan

                plan = build_query_plan(payload.query)["plan"]
            else:
                plan = {
                    "query": payload.query,
                    "query_types": payload.query_types,
                    "requirements": {},
                    "retrieval_modes": payload.retrieval_modes or ["LOCAL"],
                    "memory_policy": "DISABLED",
                    "completeness_level": payload.completeness_level or "MODERATE",
                    "scope": payload.scope or "CURRENT_DOCUMENT",
                }
            mode = choose_mode(plan)["mode"]
        ctx = {
            "documents": payload.documents,
            "inventories": payload.inventories,
            "query_types": payload.query_types,
            "top_k": payload.top_k,
        }
        return run_mode(mode, payload.query, ctx)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
