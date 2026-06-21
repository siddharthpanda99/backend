import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Body, Query

router = APIRouter(prefix="/retrieval", tags=["Memory Retrieval"])

logger = logging.getLogger(__name__)


def _get_svc():
    from common_lib.modules.memory.memory_retrieval.service import (
        get_retrieval_service,
    )

    return get_retrieval_service()


# ==================== Core Search ====================


@router.post("/search")
async def search(payload: Dict[str, Any] = Body(...)):
    try:
        return await _get_svc().search(**payload)
    except Exception as e:
        logger.error(f"Failed to search: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/vector-search")
async def vector_search(payload: Dict[str, Any] = Body(...)):
    try:
        return await _get_svc().vector_search(**payload)
    except Exception as e:
        logger.error(f"Failed to vector search: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/hybrid")
async def hybrid_search(payload: Dict[str, Any] = Body(...)):
    try:
        return await _get_svc().hybrid_search(**payload)
    except Exception as e:
        logger.error(f"Failed to hybrid search: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/negative-search")
async def negative_search(payload: Dict[str, Any] = Body(...)):
    try:
        return await _get_svc().negative_search(**payload)
    except Exception as e:
        logger.error(f"Failed to negative search: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Query Rewriting ====================


@router.post("/rewrite")
async def rewrite_query(payload: Dict[str, Any] = Body(...)):
    try:
        return await _get_svc().rewrite_query(**payload)
    except Exception as e:
        logger.error(f"Failed to rewrite query: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Reranking ====================


@router.post("/rerank")
async def rerank(payload: Dict[str, Any] = Body(...)):
    try:
        return await _get_svc().rerank(**payload)
    except Exception as e:
        logger.error(f"Failed to rerank: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Advanced Search ====================


@router.post("/multi-hop")
async def multi_hop_search(payload: Dict[str, Any] = Body(...)):
    try:
        return await _get_svc().multi_hop_search(**payload)
    except Exception as e:
        logger.error(f"Failed to multi-hop search: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/causal-chain")
async def causal_chain(payload: Dict[str, Any] = Body(...)):
    try:
        return await _get_svc().trace_causal_chain(**payload)
    except Exception as e:
        logger.error(f"Failed to trace causal chain: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/expand-context")
async def expand_context(payload: Dict[str, Any] = Body(...)):
    try:
        return await _get_svc().expand_context(**payload)
    except Exception as e:
        logger.error(f"Failed to expand context: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/multi-agent")
async def multi_agent_search(payload: Dict[str, Any] = Body(...)):
    try:
        return await _get_svc().multi_agent_search(**payload)
    except Exception as e:
        logger.error(f"Failed to multi-agent search: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/multi-agent/stats")
async def multi_agent_stats():
    try:
        return await _get_svc().multi_agent_stats()
    except Exception as e:
        logger.error(f"Failed to get multi-agent stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/multi-agent/register")
async def register_agent(payload: Dict[str, Any] = Body(...)):
    try:
        await _get_svc().register_agent(**payload)
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Failed to register agent: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/multi-agent/unregister")
async def unregister_agent(payload: Dict[str, Any] = Body(...)):
    try:
        return {"result": await _get_svc().unregister_agent(**payload)}
    except Exception as e:
        logger.error(f"Failed to unregister agent: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/multi-agent/registered")
async def get_registered_agents():
    try:
        return await _get_svc().get_registered_agents()
    except Exception as e:
        logger.error(f"Failed to get registered agents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/context-aware")
async def context_aware_search(payload: Dict[str, Any] = Body(...)):
    try:
        return await _get_svc().context_aware_search(**payload)
    except Exception as e:
        logger.error(f"Failed to context-aware search: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/personalized")
async def personalized_search(payload: Dict[str, Any] = Body(...)):
    try:
        return await _get_svc().personalized_search(**payload)
    except Exception as e:
        logger.error(f"Failed to personalized search: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/dynamic")
async def dynamic_search(payload: Dict[str, Any] = Body(...)):
    try:
        return await _get_svc().dynamic_search(**payload)
    except Exception as e:
        logger.error(f"Failed to dynamic search: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/incremental")
async def incremental_search(payload: Dict[str, Any] = Body(...)):
    try:
        return await _get_svc().incremental_search(**payload)
    except Exception as e:
        logger.error(f"Failed to incremental search: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Embedding Service ====================


@router.post("/embed")
async def embed_text(payload: Dict[str, Any] = Body(...)):
    try:
        return await _get_svc().embed_text(**payload)
    except Exception as e:
        logger.error(f"Failed to embed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/embed/batch")
async def embed_batch(payload: Dict[str, Any] = Body(...)):
    try:
        return await _get_svc().embed_batch(**payload)
    except Exception as e:
        logger.error(f"Failed to batch embed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/embed/sync")
async def sync_embeddings():
    try:
        return await _get_svc().sync_embeddings()
    except Exception as e:
        logger.error(f"Failed to sync embeddings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/embed/retry-failed")
async def retry_failed_embeddings():
    try:
        return await _get_svc().retry_failed_embeddings()
    except Exception as e:
        logger.error(f"Failed to retry embeddings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/embed/status")
async def embedding_status():
    try:
        return await _get_svc().get_embedding_status()
    except Exception as e:
        logger.error(f"Failed to get embedding status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/embed/status")
async def clear_embedding_status():
    try:
        return {"cleared": await _get_svc().clear_embedding_status()}
    except Exception as e:
        logger.error(f"Failed to clear embedding status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Data Seeding ====================


@router.post("/seed")
async def seed_data():
    try:
        from app.modules.memories.dependencies import get_memory_service as ensure_ms

        ensure_ms()
        return await _get_svc().seed_data()
    except Exception as e:
        logger.error(f"Failed to seed data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/seed")
async def clear_seed():
    try:
        from app.modules.memories.dependencies import get_memory_service as ensure_ms

        ensure_ms()
        return await _get_svc().clear_seed_data()
    except Exception as e:
        logger.error(f"Failed to clear seed data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Batch Operations ====================


@router.post("/batch-dedup")
async def batch_deduplicate(payload: Dict[str, Any] = Body(...)):
    try:
        return await _get_svc().batch_deduplicate(**payload)
    except Exception as e:
        logger.error(f"Failed to batch deduplicate: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch-consolidate")
async def batch_consolidate(payload: Dict[str, Any] = Body(...)):
    try:
        return await _get_svc().batch_consolidate(**payload)
    except Exception as e:
        logger.error(f"Failed to batch consolidate: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Deduplication ====================


@router.post("/dedup")
async def deduplicate(payload: Dict[str, Any] = Body(...)):
    try:
        return await _get_svc().deduplicate(**payload)
    except Exception as e:
        logger.error(f"Failed to deduplicate: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dedup/history")
async def dedup_history():
    try:
        return await _get_svc().get_dedup_history()
    except Exception as e:
        logger.error(f"Failed to get dedup history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/dedup/history")
async def clear_dedup_history():
    try:
        return {"cleared": await _get_svc().clear_dedup_history()}
    except Exception as e:
        logger.error(f"Failed to clear dedup history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Consolidation ====================


@router.post("/consolidate")
async def consolidate(payload: Dict[str, Any] = Body(...)):
    try:
        return await _get_svc().consolidate(**payload)
    except Exception as e:
        logger.error(f"Failed to consolidate: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/consolidate/history")
async def consolidation_history():
    try:
        return await _get_svc().get_consolidation_history()
    except Exception as e:
        logger.error(f"Failed to get consolidation history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/consolidate/history")
async def clear_consolidation_history():
    try:
        return {"cleared": await _get_svc().clear_consolidation_history()}
    except Exception as e:
        logger.error(f"Failed to clear consolidation history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Versioning ====================


@router.post("/versions")
async def create_version(payload: Dict[str, Any] = Body(...)):
    try:
        return await _get_svc().create_version(**payload)
    except Exception as e:
        logger.error(f"Failed to create version: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/versions/{memory_id}")
async def list_versions(memory_id: str):
    try:
        return await _get_svc().get_versions(memory_id=memory_id)
    except Exception as e:
        logger.error(f"Failed to list versions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/versions/{memory_id}/stats")
async def version_stats(memory_id: str):
    try:
        return await _get_svc().get_version_stats(memory_id=memory_id)
    except Exception as e:
        logger.error(f"Failed to get version stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/versions/{memory_id}/{version}")
async def get_version(memory_id: str, version: int):
    try:
        return await _get_svc().get_version(memory_id=memory_id, version=version)
    except Exception as e:
        logger.error(f"Failed to get version: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/versions/{memory_id}/revert")
async def revert_version(memory_id: str, payload: Dict[str, Any] = Body(...)):
    try:
        return await _get_svc().revert_to_version(
            memory_id=memory_id, version=payload.get("version", 1)
        )
    except Exception as e:
        logger.error(f"Failed to revert version: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/versions/diff")
async def diff_versions(payload: Dict[str, Any] = Body(...)):
    try:
        return await _get_svc().diff_versions(**payload)
    except Exception as e:
        logger.error(f"Failed to diff versions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/versions/{memory_id}/{version}")
async def delete_version(memory_id: str, version: int):
    try:
        return {
            "deleted": await _get_svc().delete_version(
                memory_id=memory_id, version=version
            )
        }
    except Exception as e:
        logger.error(f"Failed to delete version: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/versions/{memory_id}")
async def delete_all_versions(memory_id: str):
    try:
        return {
            "deleted_count": await _get_svc().delete_all_versions(memory_id=memory_id)
        }
    except Exception as e:
        logger.error(f"Failed to delete all versions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Meta Ranking ====================


@router.post("/meta-rank")
async def meta_rank(payload: Dict[str, Any] = Body(...)):
    try:
        return await _get_svc().meta_rank(**payload)
    except Exception as e:
        logger.error(f"Failed to meta rank: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/meta-rank/register-llm")
async def register_llm(payload: Dict[str, Any] = Body(...)):
    try:
        await _get_svc().register_llm(**payload)
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Failed to register llm: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/meta-rank/unregister-llm")
async def unregister_llm(payload: Dict[str, Any] = Body(...)):
    try:
        return {"result": await _get_svc().unregister_llm(**payload)}
    except Exception as e:
        logger.error(f"Failed to unregister llm: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/meta-rank/registered-llms")
async def get_registered_llms():
    try:
        return await _get_svc().get_registered_llms()
    except Exception as e:
        logger.error(f"Failed to get registered llms: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Hybrid Ranking ====================


@router.post("/hybrid-rank")
async def hybrid_rank(payload: Dict[str, Any] = Body(...)):
    try:
        return await _get_svc().hybrid_rank(**payload)
    except Exception as e:
        logger.error(f"Failed to hybrid rank: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Confidence Ranking ====================


@router.post("/confidence-rank")
async def confidence_rank(payload: Dict[str, Any] = Body(...)):
    try:
        return await _get_svc().confidence_rank(**payload)
    except Exception as e:
        logger.error(f"Failed to confidence rank: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rank-with-threshold")
async def rank_with_threshold(payload: Dict[str, Any] = Body(...)):
    try:
        return await _get_svc().rank_with_threshold(**payload)
    except Exception as e:
        logger.error(f"Failed to rank with threshold: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/confidence-rank/history")
async def confidence_ranking_history():
    try:
        return await _get_svc().get_confidence_ranking_history()
    except Exception as e:
        logger.error(f"Failed to get confidence ranking history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/confidence-rank/history")
async def clear_confidence_ranking_history():
    try:
        return {"cleared": await _get_svc().clear_confidence_ranking_history()}
    except Exception as e:
        logger.error(f"Failed to clear confidence ranking history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Auto Pruning ====================


@router.post("/auto-prune")
async def auto_prune(payload: Dict[str, Any] = Body(...)):
    try:
        return await _get_svc().auto_prune(**payload)
    except Exception as e:
        logger.error(f"Failed to auto-prune: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/auto-prune/history")
async def auto_prune_history():
    try:
        return await _get_svc().get_auto_prune_history()
    except Exception as e:
        logger.error(f"Failed to get auto-prune history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/auto-prune/history")
async def clear_auto_prune_history():
    try:
        return {"cleared": await _get_svc().clear_auto_prune_history()}
    except Exception as e:
        logger.error(f"Failed to clear auto-prune history: {e}")
        raise HTTPException(status_code=500, detail=str(e))
