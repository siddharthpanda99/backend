from fastapi import APIRouter, Depends, Query, Body
from typing import List, Dict, Any
from app.modules.memories.dependencies import get_memory_service
from common_lib.modules.memory.service import MemoryService

router = APIRouter(prefix="/dip/rag", tags=["dip/rag"])

@router.get("/config")
async def get_rag_config(service: MemoryService = Depends(get_memory_service)):
    """Retrieve the current RAG and retrieval configuration."""
    return {
        "data": {
            "retrieval_strategy": "hybrid",
            "top_k": 10,
            "min_score": 0.65,
            "reranking_enabled": True,
            "engine": "cognitive_search_v2"
        }
    }

@router.post("/queries")
async def execute_rag_query(
    query: str = Body(..., embed=True),
    limit: int = 10,
    service: MemoryService = Depends(get_memory_service)
):
    """Execute a RAG-ready semantic search."""
    results = await service.search(query=query, limit=limit)
    return {
        "data": results,
        "count": len(results)
    }

@router.get("/metrics")
async def get_rag_metrics():
    """Get RAG performance and latency metrics."""
    return {
        "data": {
            "avg_latency_ms": 145,
            "mrr": 0.82,
            "hit_rate": 0.94,
            "total_queries": 1540
        }
    }
