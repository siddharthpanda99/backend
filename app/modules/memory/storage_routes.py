"""Memory Storage API Routes."""

import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Body, Query

router = APIRouter(prefix="/storage", tags=["Memory Storage"])

logger = logging.getLogger(__name__)


@router.post("/store")
async def store(payload: Dict[str, Any] = Body(...)):
    try:
        from common_lib.modules.memory.memory_storage.service import get_storage_service

        svc = get_storage_service()
        return await svc.store(**payload)
    except Exception as e:
        logger.error(f"Failed to store memory: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/retrieve/{memory_id}")
async def retrieve(memory_id: str):
    try:
        from common_lib.modules.memory.memory_storage.service import get_storage_service

        svc = get_storage_service()
        return await svc.retrieve(memory_id=memory_id)
    except Exception as e:
        logger.error(f"Failed to retrieve memory: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{memory_id}")
async def delete(memory_id: str, hard: bool = Query(False)):
    try:
        from common_lib.modules.memory.memory_storage.service import get_storage_service

        svc = get_storage_service()
        return await svc.delete(memory_id=memory_id, hard=hard)
    except Exception as e:
        logger.error(f"Failed to delete memory: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/list")
async def list_memories(payload: Dict[str, Any] = Body(...)):
    try:
        from common_lib.modules.memory.memory_storage.service import get_storage_service

        svc = get_storage_service()
        return await svc.list_memories(**payload)
    except Exception as e:
        logger.error(f"Failed to list memories: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cache/stats")
async def get_cache_stats():
    try:
        from common_lib.modules.memory.memory_storage.service import get_storage_service

        svc = get_storage_service()
        return await svc.get_cache_stats()
    except Exception as e:
        logger.error(f"Failed to get cache stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cache/clear")
async def clear_cache():
    try:
        from common_lib.modules.memory.memory_storage.service import get_storage_service

        svc = get_storage_service()
        return await svc.clear_cache()
    except Exception as e:
        logger.error(f"Failed to clear cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tiers")
async def get_tiers():
    try:
        from common_lib.modules.memory.memory_storage.service import get_storage_service

        svc = get_storage_service()
        return await svc.get_tiers()
    except Exception as e:
        logger.error(f"Failed to get tiers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/migrate")
async def migrate_tier(payload: Dict[str, Any] = Body(...)):
    try:
        from common_lib.modules.memory.memory_storage.service import get_storage_service

        svc = get_storage_service()
        return await svc.migrate_tier(**payload)
    except Exception as e:
        logger.error(f"Failed to migrate tier: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/decay/config")
async def get_decay_config():
    try:
        from common_lib.modules.memory.config import get_config

        cfg = get_config()
        return cfg.decay_rates
    except Exception as e:
        logger.error(f"Failed to get decay config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/decay/config")
async def update_decay_config(payload: Dict[str, float] = Body(...)):
    try:
        from common_lib.modules.memory.config import get_config_manager

        mgr = get_config_manager()
        mgr.update({"decay_rates": payload})
        return {"status": "success", "decay_rates": mgr.load().decay_rates}
    except Exception as e:
        logger.error(f"Failed to update decay config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/decay/interval")
async def get_decay_interval():
    try:
        from common_lib.modules.memory.config import get_config

        cfg = get_config()
        return {"interval_seconds": cfg.decay_interval_seconds}
    except Exception as e:
        logger.error(f"Failed to get decay interval: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/decay/interval")
async def update_decay_interval(payload: Dict[str, int] = Body(...)):
    try:
        interval = payload.get("interval_seconds", 3600)
        if interval < 10:
            raise HTTPException(
                status_code=400, detail="Interval must be >= 10 seconds"
            )
        from common_lib.modules.memory.config import get_config_manager

        mgr = get_config_manager()
        mgr.update({"decay_interval_seconds": interval})
        return {
            "status": "success",
            "interval_seconds": mgr.load().decay_interval_seconds,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update decay interval: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/compaction/interval")
async def get_compaction_interval():
    try:
        from common_lib.modules.memory.config import get_config

        cfg = get_config()
        return {"interval_seconds": cfg.compaction_interval_seconds}
    except Exception as e:
        logger.error(f"Failed to get compaction interval: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/compaction/interval")
async def update_compaction_interval(payload: Dict[str, int] = Body(...)):
    try:
        interval = payload.get("interval_seconds", 3600)
        if interval < 10:
            raise HTTPException(
                status_code=400, detail="Interval must be >= 10 seconds"
            )
        from common_lib.modules.memory.config import get_config_manager

        mgr = get_config_manager()
        mgr.update({"compaction_interval_seconds": interval})
        return {
            "status": "success",
            "interval_seconds": mgr.load().compaction_interval_seconds,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update compaction interval: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/decay/trigger")
async def trigger_decay():
    try:
        from app.modules.memories.dependencies import get_memory_service

        svc = get_memory_service()
        return await svc.run_decay_cycle()
    except Exception as e:
        logger.error(f"Failed to trigger decay: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/decay/queue")
async def get_decay_queue():
    try:
        from app.modules.memories.dependencies import get_memory_service

        svc = get_memory_service()
        return await svc.get_decay_queue()
    except Exception as e:
        logger.error(f"Failed to get decay queue: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/decay/review/{memory_id}")
async def review_decay(memory_id: str, payload: Dict[str, Any] = Body(...)):
    try:
        action = payload.get("action")
        comment = payload.get("comment")
        if not action or action not in ["retain", "disable", "comment"]:
            raise HTTPException(
                status_code=400,
                detail="Invalid action. Must be 'retain', 'disable', or 'comment'",
            )
        from app.modules.memories.dependencies import get_memory_service

        svc = get_memory_service()
        success = await svc.review_decay_item(
            memory_id=memory_id, action=action, comment=comment
        )
        if not success:
            raise HTTPException(
                status_code=404, detail="Memory not found or review failed"
            )
        return {"status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to review decay item: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compaction/trigger")
async def trigger_compaction(
    method: str = Query(
        "hybrid",
        description="Compaction method: abstractive, extractive, hybrid, caveman, graphify",
    ),
    max_tokens: int = Query(150, ge=1),
):
    try:
        from app.modules.memories.dependencies import get_memory_service

        svc = get_memory_service()
        return await svc.run_compaction_cycle(method=method, max_tokens=max_tokens)
    except Exception as e:
        logger.error(f"Failed to trigger compaction: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/compaction/queue")
async def get_compaction_queue():
    try:
        from app.modules.memories.dependencies import get_memory_service

        svc = get_memory_service()
        return await svc.get_compaction_queue()
    except Exception as e:
        logger.error(f"Failed to get compaction queue: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compaction/review/{proposal_id}")
async def review_compaction(proposal_id: str, payload: Dict[str, Any] = Body(...)):
    try:
        action = payload.get("action")
        proposed_content = payload.get("proposed_content")
        comment = payload.get("comment")

        if not action or action not in ["approve", "reject", "update", "comment"]:
            raise HTTPException(
                status_code=400,
                detail="Invalid action. Must be 'approve', 'reject', 'update', or 'comment'",
            )

        from app.modules.memories.dependencies import get_memory_service

        svc = get_memory_service()
        success = await svc.review_compaction_item(
            proposal_id=proposal_id,
            action=action,
            proposed_content=proposed_content,
            comment=comment,
        )
        if not success:
            raise HTTPException(
                status_code=404, detail="Proposal not found or review failed"
            )
        return {"status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to review compaction item: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/compaction/stats")
async def get_compaction_stats():
    try:
        from app.modules.memories.dependencies import get_memory_service

        svc = get_memory_service()
        return await svc.get_compaction_stats()
    except Exception as e:
        logger.error(f"Failed to get compaction stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compaction/autocompact")
async def run_autocompaction(threshold: int = Query(15, ge=1)):
    try:
        from app.modules.memories.dependencies import get_memory_service

        svc = get_memory_service()
        return await svc.check_and_run_autocompaction(threshold=threshold)
    except Exception as e:
        logger.error(f"Failed to run autocompaction: {e}")
        raise HTTPException(status_code=500, detail=str(e))
