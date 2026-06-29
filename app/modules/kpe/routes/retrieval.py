"""KPE Retrieval Routes — Thin FastAPI wrappers delegating to common_lib.

Uses LLM-driven retrieval (query rewriting + contextual enrichment + reranking)
with static BM25/dense/hybrid fallback.
Set use_llm=false to use static retrieval directly.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from common_lib.modules.kpe.retrieval.llm import LLMQueryRewriter, LLMContextualEnricher, LLMReranker
from common_lib.modules.kpe.retrieval.bm25 import BM25Retriever
from common_lib.modules.kpe.retrieval.hybrid import HybridRetriever
from common_lib.modules.kpe.retrieval.dense import DenseRetriever

logger = logging.getLogger(__name__)

router = APIRouter()

_query_rewriter = LLMQueryRewriter()
_contextual_enricher = LLMContextualEnricher()
_reranker = LLMReranker()
_bm25 = BM25Retriever()
_dense = DenseRetriever()
_hybrid = HybridRetriever(bm25=_bm25, dense=_dense)


class QueryRewriteRequest(BaseModel):
    """Request to rewrite/expand a search query using LLM."""

    query: str = Field(description="Search query to rewrite")
    context: str = Field(default="", description="Optional context about the user or search")


class QueryRewriteResponse(BaseModel):
    """Response from query rewriting."""

    original_query: str = Field(description="Original query")
    rewritten_query: str = Field(description="Optimized search query")
    search_type: str = Field(default="hybrid", description="Suggested search type")
    intent: str = Field(default="factual", description="Detected intent")
    key_entities: List[str] = Field(default_factory=list, description="Key search entities")
    filters: Dict[str, Any] = Field(default_factory=dict, description="Suggested filters")
    query_expansion: List[str] = Field(default_factory=list, description="Alternative phrasings")
    decomposition: List[str] = Field(default_factory=list, description="Sub-queries for multi-faceted queries")
    engine: str = Field(default="llm", description="Engine used: llm|fallback")


class EnrichChunksRequest(BaseModel):
    """Request to enrich chunks with document context."""

    chunks: List[Dict[str, Any]] = Field(description="List of chunks to enrich")
    doc_context: Dict[str, str] = Field(description="Document-level context keyed by document_id")
    use_llm: bool = Field(default=True, description="Use LLM for contextual enrichment")


class RerankRequest(BaseModel):
    """Request to rerank search results."""

    query: str = Field(description="Original search query")
    results: List[Dict[str, Any]] = Field(description="Search results to rerank")
    use_llm: bool = Field(default=True, description="Use LLM for reranking")


class SearchRequest(BaseModel):
    """Search request parameters with optional LLM enhancement."""

    query: str = Field(description="Search query")
    retriever_type: str = Field(default="bm25", description="Retriever: bm25|dense|hybrid")
    top_k: int = Field(default=10, ge=1, le=100, description="Max results")
    tenant_id: Optional[str] = Field(default=None, description="Tenant filter")
    use_llm_rewrite: bool = Field(default=True, description="Use LLM query rewriting before search")
    use_llm_rerank: bool = Field(default=True, description="Use LLM reranking after search")


@router.post("/search")
async def search(payload: SearchRequest):
    """Search across documents with optional LLM query rewriting and reranking.

    1. (Optional) LLM query rewriting for query expansion and intent detection
    2. Execute search with the (rewritten) query
    3. (Optional) LLM reranking for deep relevance scoring
    """
    try:
        # Step 1: LLM query rewriting
        query = payload.query
        query_info = {}
        if payload.use_llm_rewrite:
            result = _query_rewriter.rewrite(payload.query)
            query = result.get("rewritten_query", payload.query)
            query_info = result

        # Step 2: Execute search
        if payload.retriever_type == "hybrid":
            search_results = _hybrid.search(query, top_k=payload.top_k * 2)
        elif payload.retriever_type == "dense":
            search_results = _dense.search(query, top_k=payload.top_k * 2)
        else:
            search_results = _bm25.search(query, top_k=payload.top_k * 2)

        # Step 3: LLM reranking
        if payload.use_llm_rerank and search_results:
            search_results = _reranker.rerank(query, search_results)

        return {
            "query": payload.query,
            "rewritten_query": query,
            "results": search_results[:payload.top_k],
            "total_results": len(search_results),
            "query_info": query_info,
            "engine": "llm_pipeline" if payload.use_llm_rewrite or payload.use_llm_rerank else "static",
        }
    except Exception as e:
        logger.error("Search failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rewrite", response_model=QueryRewriteResponse)
async def rewrite_query(payload: QueryRewriteRequest):
    """Rewrite/expand a search query for optimal retrieval."""
    try:
        result = _query_rewriter.rewrite(
            query=payload.query,
            context=payload.context,
        )
        return QueryRewriteResponse(
            original_query=result.get("original_query", payload.query),
            rewritten_query=result.get("rewritten_query", payload.query),
            search_type=result.get("search_type", "hybrid"),
            intent=result.get("intent", "factual"),
            key_entities=result.get("key_entities", []),
            filters=result.get("filters", {}),
            query_expansion=result.get("query_expansion", []),
            decomposition=result.get("decomposition", []),
            engine="llm" if result.get("original_query") != payload.query or any(result.get("key_entities")) else "fallback",
        )
    except Exception as e:
        logger.error("Query rewriting failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/enrich")
async def enrich_chunks(payload: EnrichChunksRequest):
    """Enrich chunks with document context."""
    try:
        enriched = _contextual_enricher.enrich(
            chunks=payload.chunks,
            doc_context=payload.doc_context,
        )
        return {
            "enriched_chunks": enriched,
            "count": len(enriched),
            "engine": "llm" if payload.use_llm else "static",
        }
    except Exception as e:
        logger.error("Enrichment failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rerank")
async def rerank_results(payload: RerankRequest):
    """Rerank search results for relevance."""
    try:
        reranked = _reranker.rerank(
            query=payload.query,
            results=payload.results,
        )
        return {
            "results": reranked,
            "count": len(reranked),
            "engine": "llm" if payload.use_llm else "static",
        }
    except Exception as e:
        logger.error("Reranking failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
