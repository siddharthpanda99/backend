"""
DIP RAG Routes — Delegated to KnowledgeEngine.

These routes now delegate to the KnowledgeEngineService (from the
knowledge_engine module) instead of returning hardcoded mocks or
forwarding to MemoryService. This provides real retrieval pipeline
results, configuration, and health metrics.

Long-running queries are jobs-backed by default; pass ``sync=true`` for inline.
"""

from __future__ import annotations

import logging
import json
import asyncio
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Body

from app.modules.knowledge.dependencies import get_knowledge_engine_service
from common_lib.modules.knowledge_engine.service import KnowledgeEngineService

from app.modules.dip.runtime.actor import capture_job_actor, owned_job_service
from common_lib.modules.jobs.artifacts import job_dir
from common_lib.modules.jobs.models import JobRecord
from common_lib.modules.jobs.service import get_job_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/dip/rag", tags=["dip/rag"], dependencies=[Depends(capture_job_actor)])


# ---------------------------------------------------------------------------
# Jobs-backed execution helpers
# ---------------------------------------------------------------------------


def _ensure_dip_jobs():
    return owned_job_service()


def _dip_job_payload(record: Any) -> Dict[str, Any]:
    refs: List[str] = []
    try:
        refs = [str(r) for r in (record.get_result_refs() or [])]
    except Exception:
        refs = []
    return {
        "job_id": str(record.id),
        "status": str(record.status),
        "kind": str(record.kind),
        "progress": float(record.progress or 0.0),
        "result_refs": refs,
        "error": record.error,
    }


def _dip_job_status(job_id: str) -> Dict[str, Any]:
    from fastapi import HTTPException as _HTTPException

    svc = _ensure_dip_jobs()
    record = svc.get(job_id)
    if record is None:
        raise _HTTPException(status_code=404, detail=f"Job {job_id} not found")
    payload: Dict[str, Any] = _dip_job_payload(record)
    meta: Dict[str, Any] = {}
    try:
        refs = [str(r) for r in (record.get_result_refs() or [])]
    except Exception:
        refs = []
    for ref in refs:
        if not ref.endswith("result.json"):
            continue
        try:
            with open(ref, "r", encoding="utf-8") as fh:
                loaded = json.load(fh)
            if isinstance(loaded, dict):
                meta = loaded
                break
        except (OSError, ValueError):
            continue
    payload["meta"] = meta
    return payload


# ---------------------------------------------------------------------------
# Jobs endpoints
# ---------------------------------------------------------------------------


@router.get("/jobs")
async def list_dip_rag_jobs(
    status: Optional[str] = None,
    kind: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    records = _ensure_dip_jobs().list(
        status=status,
        kind=kind,
        kind_prefix="dip.",
        limit=min(max(limit, 1), 200),
        offset=max(offset, 0),
    )
    items = [_dip_job_payload(record) for record in records]
    return {"data": items, "total": len(items)}


@router.get("/jobs/{job_id}")
async def get_dip_rag_job(job_id: str) -> Dict[str, Any]:
    return _dip_job_status(job_id)


@router.post("/jobs/{job_id}/cancel")
async def cancel_dip_rag_job(job_id: str) -> Dict[str, Any]:
    record = _ensure_dip_jobs().cancel(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return {"status": "ok", **_dip_job_payload(record)}


@router.get("/jobs/{job_id}/events")
async def dip_rag_job_events(job_id: str):
    from fastapi.responses import StreamingResponse

    async def event_generator():
        import time as _time

        deadline: float = _time.time() + 3600.0
        last_progress: float = -1.0
        yield f"event: started\ndata: {json.dumps({'job_id': job_id, 'status': 'queued'})}\n\n"
        while True:
            record: JobRecord | None = get_job_service().get(job_id)
            if record is None:
                yield f"event: failed\ndata: {json.dumps({'job_id': job_id, 'error': 'job not found'})}\n\n"
                return
            if record.progress != last_progress:
                last_progress = record.progress
                yield f"event: progress\ndata: {json.dumps({'job_id': job_id, 'status': record.status, 'progress': record.progress})}\n\n"
            if record.status in ("completed", "failed", "cancelled"):
                if record.status == "completed":
                    meta: Dict[str, Any] = {}
                    for ref in _dip_job_payload(record)["result_refs"]:
                        if not ref.endswith("result.json"):
                            continue
                        try:
                            with open(ref, "r", encoding="utf-8") as fh:
                                loaded = json.load(fh)
                            if isinstance(loaded, dict):
                                meta = loaded
                                break
                        except (OSError, ValueError):
                            continue
                    yield f"event: completed\ndata: {json.dumps({'job_id': job_id, 'status': 'completed', 'meta': meta})}\n\n"
                else:
                    yield f"event: {record.status}\ndata: {json.dumps({'job_id': job_id, 'status': record.status, 'error': record.error or record.status})}\n\n"
                return
            if _time.time() > deadline:
                yield f"event: timeout\ndata: {json.dumps({'job_id': job_id, 'error': 'progress stream timed out'})}\n\n"
                return
            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


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
    sync: bool = False,
    service: KnowledgeEngineService = Depends(get_knowledge_engine_service),
):
    """Execute the KnowledgeEngine retrieval pipeline.

    Jobs-backed by default; pass ``sync=true`` for inline.

    Returns a ContextPackage with ranked knowledge chunks, validation
    results, and formatted context ready for LLM consumption.
    """
    if sync:
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

    from app.modules.dip.runtime.job_executors import RAG_QUERY_KIND

    record = _ensure_dip_jobs().submit(
        RAG_QUERY_KIND,
        params={"query": query, "limit": limit},
    )
    return {"status": "queued", **_dip_job_payload(record)}


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
