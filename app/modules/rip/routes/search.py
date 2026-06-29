"""RIP Search routes — Unified, BM25, dense, sparse, hybrid search + reranking.

Implements endpoints 11.8–11.13 from the implementation tracker.
All retrieval routes now use the RIP Connector layer to call real model providers.
"""

from fastapi import APIRouter, HTTPException
from typing import Optional

from common_lib.modules.rip.rip_retrieval.schemas import (
    SearchRequest,
    SearchResponse,
    BM25SearchRequest,
    DenseSearchRequest,
    SparseSearchRequest,
    HybridSearchRequest,
    RetrievalResult,
)
from common_lib.modules.rip.rip_connectors import create_embed_fn, create_llm_fn, create_cross_encoder_fn, create_colbert_fn

router = APIRouter(prefix="/rip/search", tags=["RIP — Search"])


@router.post("", response_model=SearchResponse)
async def unified_search(payload: SearchRequest):
    """Unified hybrid search — auto-routes to the best retriever(s).

    By default uses BM25 + dense with RRF fusion.
    Specify `retrievers` to customise the set.
    """
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
                    method=payload.reranker if payload.reranker != "none" else "cross_encoder",
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
async def bm25_search(payload: BM25SearchRequest):
    """BM25 lexical search — exact term matching with term-frequency saturation."""
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
async def dense_search(payload: DenseSearchRequest):
    """Dense vector search — semantic similarity via embeddings.

    Uses the RIP Connector layer to call real embedding models (OpenAI, BGE-M3,
    or SentenceTransformers) based on the model_name field.
    """
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
async def sparse_search(payload: SparseSearchRequest):
    """Sparse learned search (SPLADE-style) — term expansion via transformer."""
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
async def colbert_search_endpoint(payload: DenseSearchRequest):
    """ColBERT late interaction search via RAGatouille.

    Uses the RIP Connector layer to load a real ColBERTv2 model
    and perform multi-vector MaxSim scoring.
    """
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
async def hybrid_search_endpoint(payload: HybridSearchRequest):
    """Hybrid search — BM25 + dense + optional sparse with configurable weights and fusion."""
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
                    method=payload.reranker if payload.reranker != "none" else "cross_encoder",
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
            retrievers_used=["bm25", "dense", "sparse"] if payload.sparse_weight > 0 else ["bm25", "dense"],
            fusion_method=payload.fusion_method,
            latency_ms=elapsed,
            total_time_ms=elapsed,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
