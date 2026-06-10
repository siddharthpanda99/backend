"""
DIP RAG Routes — Delegated to KnowledgeEngine.

These routes now delegate to the KnowledgeEngineService (from the
knowledge_engine module) instead of returning hardcoded mocks or
forwarding to MemoryService. This provides real retrieval pipeline
results, configuration, and health metrics.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Body

from app.modules.knowledge.dependencies import get_knowledge_engine_service
from common_lib.modules.knowledge_engine.service import KnowledgeEngineService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dip/rag", tags=["dip/rag"])


@router.get("/config")
async def get_rag_config(
    service: KnowledgeEngineService = Depends(get_knowledge_engine_service),
):
    """Retrieve the current RAG and retrieval configuration from KnowledgeEngine."""
    config = service.get_config()
    return {
        "data": {
            "retrieval_strategy": "hybrid",
            "top_k": config.get("retrieval", {}).get("default_top_k", 100),
            "min_score": config.get("retrieval", {}).get("min_score_threshold", 0.60),
            "reranking_enabled": config.get("reranking", {}).get("enabled", True),
            "engine": "knowledge_engine",
        }
    }


@router.post("/queries")
async def execute_rag_query(
    query: str = Body(..., embed=True),
    limit: int = 10,
    service: KnowledgeEngineService = Depends(get_knowledge_engine_service),
):
    """Execute the KnowledgeEngine retrieval pipeline.

    Returns a ContextPackage with ranked knowledge chunks, validation
    results, and formatted context ready for LLM consumption.
    """
    result = await service.retrieve(query=query, top_k=limit)
    if result is None:
        return {"data": [], "count": 0, "status": "empty", "message": "Engine not available"}

    chunks = result.get("knowledge_chunks", [])
    return {
        "data": chunks,
        "count": len(chunks),
        "query": query,
        "tokens_used": result.get("tokens_used", 0),
        "validation": result.get("validation_report"),
        "formatted_context": result.get("formatted_context"),
        "status": "success",
    }


@router.get("/metrics")
async def get_rag_metrics(
    service: KnowledgeEngineService = Depends(get_knowledge_engine_service),
):
    """Get RAG performance and health metrics from KnowledgeEngine."""
    try:
        health = await service.health()
        return {
            "data": {
                "module": health.get("module", "knowledge_engine"),
                "version": health.get("version", "1.0.0"),
                "initialized": health.get("initialized", False),
                "models_count": health.get("models_count", 0),
                "embedding_models": health.get("embedding_models", []),
                "chunking_strategies": health.get("chunking_strategies", []),
            }
        }
    except Exception as e:
        logger.error(f"Failed to fetch KnowledgeEngine health: {e}")
        return {
            "data": {
                "module": "knowledge_engine",
                "version": "1.0.0",
                "initialized": False,
                "error": str(e),
            }
        }
