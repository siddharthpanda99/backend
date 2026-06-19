"""Memory API Routes — Thin API layer for cognitive memory system.

Delegates to common_lib modules.memory and modules.security services.
"""

import json
import logging
import time
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Body, Request, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from common_lib.modules.observability import get_observability
from common_lib.modules.notification.controller import (
    notify,
    Channels,
    Priority,
)
from common_lib.modules.integration.context_propagation import (
    get_context_propagation,
    create_trace_context,
)

router = APIRouter(tags=["memory"])
logger = logging.getLogger(__name__)


def _get_trace_id_from_request(request: Request) -> Optional[str]:
    trace_id = request.headers.get("X-Trace-ID")
    if not trace_id:
        trace_id = request.headers.get("X-Correlation-ID")
    return trace_id


def _create_request_context(request: Request, operation: str):
    trace_id = _get_trace_id_from_request(request)
    if trace_id:
        ctx = get_context_propagation().get_trace(trace_id)
        if ctx:
            return get_context_propagation().propagate(ctx, "memory_api", operation)
    return create_trace_context(source="memory_api", operation=operation)


# ────────────────────────────────────────────────────────────────
# Helpers — thin wrappers over existing common_lib services
# ────────────────────────────────────────────────────────────────


def get_client_id(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def check_rate_limit(request: Request):
    from common_lib.modules.memory.api import get_rate_limiter

    client_id = get_client_id(request)
    limiter = get_rate_limiter()
    allowed, retry_after = limiter.check_rate_limit(client_id)
    if not allowed:
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded", "retry_after": round(retry_after, 1)},
            headers={"Retry-After": str(int(retry_after + 1))},
        )
    return None


def sanitize_input(data: dict) -> dict:
    from common_lib.modules.memory.api import get_sanitizer

    sanitizer = get_sanitizer()
    return sanitizer.sanitize_dict(data)


def _get_adapter():
    from common_lib.modules.memory.memory_storage.adapters.pgvector_adapter import (
        PgVectorAdapter,
    )
    from app.core.settings import get_settings

    settings = get_settings()
    return PgVectorAdapter(settings.SQLALCHEMY_DATABASE_URI)


# ────────────────────────────────────────────────────────────────
# Request/Response Models
# ────────────────────────────────────────────────────────────────


class StoreMemoryRequest(BaseModel):
    content: str
    memory_type: str = "semantic"
    agent_id: Optional[str] = None
    session_id: Optional[str] = None
    importance: float = 0.5
    confidence: float = 1.0
    enable_pii_scan: bool = True
    store_in_hot: bool = True


class StoreMemoryResponse(BaseModel):
    memory_id: str
    status: str
    content_length: int


class UpdateMemoryRequest(BaseModel):
    content: Optional[str] = None
    importance: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


class SearchRequest(BaseModel):
    query: str
    memory_type: Optional[str] = None
    agent_id: Optional[str] = None
    session_id: Optional[str] = None
    limit: int = 10
    skip: int = 0


class ListMemoriesRequest(BaseModel):
    skip: int = 0
    limit: int = 50
    memory_type: Optional[str] = None
    session_id: Optional[str] = None
    agent_id: Optional[str] = None
    include_deleted: bool = False


class PIIRequest(BaseModel):
    content: str
    strategy: str = "redact"
    use_presidio: bool = True


class PIIResponse(BaseModel):
    scrubbed_content: str
    pii_entities: List[Dict[str, Any]]
    entity_count: int


class GDPRRequest(BaseModel):
    agent_id: str
    hard_delete: bool = False
    export_first: bool = True
    reason: str = ""


class GDPRResponse(BaseModel):
    deleted_count: int
    export_path: str
    success: bool


def _get_memory_service():
    from common_lib.modules.memory.service import MemoryService
    from common_lib.modules.memory.memory_storage.repositories.memory_repository import (
        MemoryRepository,
    )

    adapter = _get_adapter()
    repo = MemoryRepository(adapter)
    return MemoryService(repository=repo)


# ────────────────────────────────────────────────────────────────
# Core Memory Operations
# ────────────────────────────────────────────────────────────────


@router.post("/store", response_model=StoreMemoryResponse)
async def store_memory(
    request: StoreMemoryRequest,
    req: Request,
    rate_limit: Optional[JSONResponse] = Depends(check_rate_limit),
):
    if rate_limit:
        return rate_limit

    trace_ctx = _create_request_context(req, "memory.store")
    obs = get_observability()

    with obs.start_span(
        "memory.store",
        trace_id=trace_ctx.trace_id,
        parent_span_id=trace_ctx.parent_span_id,
        attributes={
            "memory_type": request.memory_type,
            "agent_id": request.agent_id or "",
            "session_id": request.session_id or "",
        },
    ) as span:
        start = time.time()
        try:
            sanitized = sanitize_input({
                "content": request.content,
                "memory_type": request.memory_type,
                "agent_id": request.agent_id or "",
                "session_id": request.session_id or "",
            })

            svc = _get_memory_service()
            mem_id = svc.store_memory(
                sanitized["content"],
                sanitized["memory_type"],
                sanitized["agent_id"] or None,
                sanitized["session_id"] or None,
                request.importance,
                request.confidence,
                enable_pii_scan=request.enable_pii_scan,
                store_in_hot=request.store_in_hot,
            )

            latency = time.time() - start
            obs.record_store(latency, success=True, trace_id=trace_ctx.trace_id)
            span.set_attribute("latency_ms", round(latency * 1000, 2))
            span.set_attribute("memory_id", str(mem_id))

            await notify(
                "memory.store",
                {
                    "memory_id": str(mem_id),
                    "memory_type": request.memory_type,
                    "agent_id": request.agent_id,
                    "session_id": request.session_id,
                    "content_length": len(request.content),
                    "latency_ms": round(latency * 1000, 2),
                },
                channel=Channels.MEMORY_STORE,
                priority=Priority.NORMAL,
                correlation_id=trace_ctx.correlation_id,
                trace_id=trace_ctx.trace_id,
            )
            return StoreMemoryResponse(
                memory_id=str(mem_id),
                status="stored",
                content_length=len(request.content),
            )
        except ValueError as e:
            latency = time.time() - start
            obs.record_store(latency, success=False, trace_id=trace_ctx.trace_id)
            span.status = "error"
            span.error = str(e)
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            latency = time.time() - start
            obs.record_store(latency, success=False, trace_id=trace_ctx.trace_id)
            span.status = "error"
            span.error = str(e)
            logger.error(f"Failed to store memory: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))


@router.get("/{memory_id}")
async def retrieve_memory(
    memory_id: str,
    req: Request,
    rate_limit: Optional[JSONResponse] = Depends(check_rate_limit),
):
    if rate_limit:
        return rate_limit

    trace_ctx = _create_request_context(req, "memory.retrieve")
    obs = get_observability()

    with obs.start_span("memory.retrieve", trace_id=trace_ctx.trace_id, parent_span_id=trace_ctx.parent_span_id, attributes={"memory_id": memory_id}) as span:
        start = time.time()
        try:
            from common_lib.modules.memory.api import get_sanitizer

            sanitized_id = get_sanitizer().validate_memory_id(memory_id)
            adapter = _get_adapter()
            result = await adapter.retrieve(sanitized_id)

            latency = time.time() - start
            found = result is not None
            obs.record_retrieve(latency, found=found, trace_id=trace_ctx.trace_id)
            span.set_attribute("latency_ms", round(latency * 1000, 2))
            span.set_attribute("found", found)

            if not result:
                raise HTTPException(status_code=404, detail="Memory not found")

            await notify(
                "memory.retrieve",
                {"memory_id": sanitized_id, "found": True, "latency_ms": round(latency * 1000, 2)},
                channel=Channels.MEMORY_RETRIEVE,
                correlation_id=trace_ctx.correlation_id,
                trace_id=trace_ctx.trace_id,
            )
            return {"status": "ok", "data": result}
        except HTTPException:
            raise
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Failed to retrieve memory {memory_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))


@router.put("/{memory_id}")
async def update_memory(memory_id: str, request: UpdateMemoryRequest):
    try:
        adapter = _get_adapter()
        success = await adapter.update(
            memory_id,
            data={"content": request.content} if request.content is not None else None,
            importance=request.importance,
            metadata=request.metadata,
        )
        if not success:
            raise HTTPException(status_code=404, detail="Memory not found")
        return {"status": "ok", "updated": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update memory {memory_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{memory_id}")
async def delete_memory(memory_id: str, hard: bool = Query(False)):
    try:
        adapter = _get_adapter()
        success = await adapter.delete(memory_id, hard=hard)
        if not success:
            raise HTTPException(status_code=404, detail="Memory not found")
        return {"status": "ok", "deleted": True, "hard": hard}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete memory {memory_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/list")
async def list_memories(request: ListMemoriesRequest):
    start = time.time()
    try:
        adapter = _get_adapter()
        memories = await adapter.list(
            skip=request.skip,
            limit=request.limit,
            memory_type=request.memory_type,
            session_id=request.session_id,
            agent_id=request.agent_id,
            include_deleted=request.include_deleted,
        )
        from common_lib.modules.memory.monitoring import get_metrics_collector

        collector = get_metrics_collector()
        collector.increment("memory.list.total")
        collector.observe("memory.list.latency", time.time() - start)
        return {"status": "ok", "data": memories, "count": len(memories), "skip": request.skip, "limit": request.limit}
    except Exception as e:
        logger.error(f"Failed to list memories: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ────────────────────────────────────────────────
# Search Operations
# ────────────────────────────────────────────────


@router.post("/search")
async def search_memories(
    request: SearchRequest,
    req: Request,
    rate_limit: Optional[JSONResponse] = Depends(check_rate_limit),
):
    if rate_limit:
        return rate_limit

    trace_ctx = _create_request_context(req, "memory.search")
    obs = get_observability()

    with obs.start_span("memory.search", trace_id=trace_ctx.trace_id, parent_span_id=trace_ctx.parent_span_id, attributes={
        "query_length": len(request.query), "memory_type": request.memory_type or "", "limit": request.limit,
    }) as span:
        start = time.time()
        try:
            from common_lib.modules.memory.api import get_sanitizer

            sanitizer = get_sanitizer()
            sanitized_query = sanitizer.sanitize_string(request.query, "query")
            sanitized_agent = sanitizer.sanitize_string(request.agent_id or "", "agent_id")
            sanitized_session = sanitizer.sanitize_string(request.session_id or "", "session_id")

            adapter = _get_adapter()
            results = await adapter.search(
                sanitized_query,
                memory_type=request.memory_type,
                agent_id=sanitized_agent or None,
                session_id=sanitized_session or None,
                skip=request.skip,
                limit=request.limit,
            )
            latency = time.time() - start
            obs.record_search(latency, result_count=len(results), trace_id=trace_ctx.trace_id)
            span.set_attribute("latency_ms", round(latency * 1000, 2))
            span.set_attribute("result_count", len(results))

            return {"status": "ok", "data": results, "count": len(results), "query": request.query}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Search failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))


@router.post("/vector-search")
async def vector_search(
    query_embedding: List[float] = Body(..., description="Query embedding vector"),
    top_k: int = Body(10),
    threshold: float = Body(0.0),
):
    try:
        from common_lib.modules.memory.memory_storage.adapters.pgvector_adapter import PgVectorAdapter
        from app.core.settings import get_settings

        adapter = PgVectorAdapter(get_settings().SQLALCHEMY_DATABASE_URI)
        results = await adapter.similarity_search(query_embedding, top_k=top_k, threshold=threshold)
        return {"status": "ok", "data": results, "count": len(results)}
    except Exception as e:
        logger.error(f"Vector search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ────────────────────────────────────────────────
# Session & Agent Operations
# ────────────────────────────────────────────────


@router.get("/session/{session_id}")
async def get_session_memories(session_id: str, skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=500)):
    try:
        adapter = _get_adapter()
        memories = await adapter.get_by_session(session_id, skip=skip, limit=limit)
        return {"status": "ok", "data": memories, "count": len(memories), "session_id": session_id}
    except Exception as e:
        logger.error(f"Failed to get session memories: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/session/{session_id}/state")
async def get_session_state(session_id: str, include_content: bool = Query(True), max_memories: int = Query(10, ge=1, le=100)):
    try:
        adapter = _get_adapter()
        memories = await adapter.get_by_session(session_id)
        return {
            "status": "ok",
            "data": {
                "session_id": session_id,
                "memory_count": len(memories),
                "memories": memories[:max_memories] if include_content else [{"id": m.get("id")} for m in memories[:max_memories]],
            },
        }
    except Exception as e:
        logger.error(f"Failed to get session state: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agent/{agent_id}")
async def get_agent_memories(agent_id: str, skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=500)):
    try:
        adapter = _get_adapter()
        memories = await adapter.get_by_agent(agent_id, skip=skip, limit=limit)
        return {"status": "ok", "data": memories, "count": len(memories), "agent_id": agent_id}
    except Exception as e:
        logger.error(f"Failed to get agent memories: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ────────────────────────────────────────────────
# Security Operations (PII, GDPR)
# ────────────────────────────────────────────────


@router.post("/pii/redact", response_model=PIIResponse)
async def redact_pii(request: PIIRequest):
    try:
        from common_lib.modules.security.pii.unified_detector import get_unified_pii_detector

        detector = get_unified_pii_detector(use_presidio=request.use_presidio)
        result = detector.detect(request.content)
        scrubbed = detector.scrub(request.content, strategy=request.strategy) if result.entities else request.content
        return PIIResponse(
            scrubbed_content=scrubbed,
            pii_entities=[{"type": e.entity_type, "value": e.text, "start": e.start, "end": e.end} for e in result.entities],
            entity_count=len(result.entities),
        )
    except Exception as e:
        logger.error(f"PII redaction failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/gdpr/right-to-forget", response_model=GDPRResponse)
async def gdpr_right_to_forget(
    request: GDPRRequest,
    req: Request,
    rate_limit: Optional[JSONResponse] = Depends(check_rate_limit),
):
    if rate_limit:
        return rate_limit
    try:
        from common_lib.modules.memory.api import get_sanitizer

        sanitized_agent_id = get_sanitizer().validate_agent_id(request.agent_id)
        adapter = _get_adapter()

        if request.hard_delete:
            count = await adapter.hard_delete_by_agent(sanitized_agent_id)
        else:
            count = await adapter.soft_delete_by_agent(sanitized_agent_id)

        return GDPRResponse(
            deleted_count=count,
            export_path=f"/tmp/gdpr_export_{sanitized_agent_id}.json" if request.export_first else "",
            success=True,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"GDPR right-to-forget failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ────────────────────────────────────────────────
# Metrics / Monitoring
# ────────────────────────────────────────────────


@router.get("/metrics")
async def memory_metrics(format: str = Query("json")):
    try:
        from common_lib.modules.memory.monitoring import get_metrics_collector

        collector = get_metrics_collector()
        collector.evaluate_alerts()
        if format == "prometheus":
            from fastapi.responses import PlainTextResponse
            return PlainTextResponse(content=collector.export_prometheus())
        return {"status": "ok", "data": collector.get_all_metrics()}
    except Exception as e:
        logger.error(f"Failed to get metrics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ────────────────────────────────────────────────
# Capabilities
# ────────────────────────────────────────────────


@router.get("/capabilities")
async def list_memory_capabilities():
    """List all available memory capabilities across all blocks."""
    try:
        from common_lib.modules.memory.blocks_service import get_instance_service

        svc = get_instance_service()
        result = svc.list_all_capabilities()
        return {"status": "ok", **result}
    except Exception as e:
        logger.error(f"Failed to list capabilities: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ────────────────────────────────────────────────
# Config
# ────────────────────────────────────────────────


class ConfigUpdateRequest(BaseModel):
    database: Optional[Dict[str, Any]] = None
    embedding: Optional[Dict[str, Any]] = None
    rate_limit: Optional[Dict[str, Any]] = None
    security: Optional[Dict[str, Any]] = None
    feature_flags: Optional[Dict[str, Any]] = None


@router.get("/config")
async def get_memory_config():
    try:
        from common_lib.modules.memory.config import get_config

        config = get_config()
        return {
            "status": "ok",
            "config": {
                "database": {"url": config.database.url, "pool_size": config.database.pool_size, "max_overflow": config.database.max_overflow},
                "embedding": {"model_name": config.embedding.model_name, "device": config.embedding.device, "batch_size": config.embedding.batch_size},
                "rate_limit": {"enabled": config.rate_limit.enabled, "requests_per_minute": config.rate_limit.requests_per_minute, "requests_per_hour": config.rate_limit.requests_per_hour},
                "security": {"pii_scan_enabled": config.security.pii_scan_enabled, "max_content_length": config.security.max_content_length, "gdpr_retention_days": config.security.gdpr_retention_days},
                "feature_flags": {
                    "vector_search": config.feature_flags.vector_search,
                    "semantic_clustering": config.feature_flags.semantic_clustering,
                    "causal_analysis": config.feature_flags.causal_analysis,
                    "federation_sync": config.feature_flags.federation_sync,
                    "compression": config.feature_flags.compression,
                    "observability": config.feature_flags.observability,
                    "versioning": config.feature_flags.versioning,
                    "multimodal": config.feature_flags.multimodal,
                },
                "version": config.version,
            },
        }
    except Exception as e:
        logger.error(f"Failed to get config: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

