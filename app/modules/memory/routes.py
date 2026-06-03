"""Memory API Routes - CRUD operations for cognitive memory system.

Provides REST endpoints for memory operations:
- Store, retrieve, update, delete memories
- Search and vector search
- Session and agent memory management
- Memory statistics and health
- PII redaction and GDPR compliance
- Rate limiting and input sanitization
- Unified observability (tracing, metrics, notifications)
"""

import json
import logging
import time
import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, Body, Request, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from common_lib.modules.observability import get_observability
from common_lib.modules.notification.controller import (
    notify,
    notify_sync,
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
    """Extract trace_id from request headers or generate new one."""
    trace_id = request.headers.get("X-Trace-ID")
    if not trace_id:
        trace_id = request.headers.get("X-Correlation-ID")
    return trace_id


def _create_request_context(request: Request, operation: str):
    """Create trace context for a request."""
    trace_id = _get_trace_id_from_request(request)
    if trace_id:
        ctx = get_context_propagation().get_trace(trace_id)
        if ctx:
            return get_context_propagation().propagate(ctx, "memory_api", operation)
    return create_trace_context(source="memory_api", operation=operation)


# =============================================================================
# Rate Limiting & Input Sanitization
# =============================================================================


def get_client_id(request: Request) -> str:
    """Extract client identifier from request."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def check_rate_limit(request: Request):
    """Rate limiting dependency."""
    from common_lib.modules.memory.api import get_rate_limiter

    client_id = get_client_id(request)
    limiter = get_rate_limiter()
    allowed, retry_after = limiter.check_rate_limit(client_id)

    if not allowed:
        return JSONResponse(
            status_code=429,
            content={
                "detail": "Rate limit exceeded",
                "retry_after": round(retry_after, 1),
            },
            headers={"Retry-After": str(int(retry_after + 1))},
        )
    return None


def sanitize_input(data: dict) -> dict:
    """Sanitize input data."""
    from common_lib.modules.memory.api import get_sanitizer

    sanitizer = get_sanitizer()
    return sanitizer.sanitize_dict(data)


# =============================================================================
# Request/Response Models
# =============================================================================


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


# =============================================================================
# Helper Functions
# =============================================================================


def _get_adapter():
    """Get the memory storage adapter."""
    from common_lib.modules.memory.memory_storage.adapters.pgvector_adapter import (
        PgVectorAdapter,
    )
    from app.core.settings import get_settings

    settings = get_settings()
    return PgVectorAdapter(settings.SQLALCHEMY_DATABASE_URI)


def _get_memory_service():
    """Get the memory service."""
    from common_lib.modules.memory.service import MemoryService
    from common_lib.modules.memory.memory_storage.repositories.memory_repository import (
        MemoryRepository,
    )

    adapter = _get_adapter()
    repo = MemoryRepository(adapter)
    return MemoryService(repository=repo)


# =============================================================================
# Memory Blocks & Marketplace Endpoints
# =============================================================================

# Note: Memory Blocks, Profiles, and Compositions endpoints are now
# defined and managed in app/modules/memory/blocks_routes.py
# and wired via wire_routes.py.


# =============================================================================
# Core Memory Operations
# =============================================================================


@router.post("/store", response_model=StoreMemoryResponse)
async def store_memory(
    request: StoreMemoryRequest,
    req: Request,
    rate_limit: Optional[JSONResponse] = Depends(check_rate_limit),
):
    """Store a new memory record with metadata and policy checks."""
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
            sanitized = sanitize_input(
                {
                    "content": request.content,
                    "memory_type": request.memory_type,
                    "agent_id": request.agent_id or "",
                    "session_id": request.session_id or "",
                }
            )

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

            # Notify other modules
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
            span.set_attribute("error_type", "validation")
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            latency = time.time() - start
            obs.record_store(latency, success=False, trace_id=trace_ctx.trace_id)
            span.status = "error"
            span.error = str(e)
            span.set_attribute("error_type", "internal")
            logger.error(f"Failed to store memory: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))


@router.get("/{memory_id}")
async def retrieve_memory(
    memory_id: str,
    req: Request,
    rate_limit: Optional[JSONResponse] = Depends(check_rate_limit),
):
    """Retrieve a memory by its unique ID."""
    if rate_limit:
        return rate_limit

    trace_ctx = _create_request_context(req, "memory.retrieve")
    obs = get_observability()

    with obs.start_span(
        "memory.retrieve",
        trace_id=trace_ctx.trace_id,
        parent_span_id=trace_ctx.parent_span_id,
        attributes={"memory_id": memory_id},
    ) as span:
        start = time.time()
        try:
            from common_lib.modules.memory.api import get_sanitizer

            sanitizer = get_sanitizer()
            sanitized_id = sanitizer.validate_memory_id(memory_id)

            adapter = _get_adapter()
            result = await adapter.retrieve(sanitized_id)

            latency = time.time() - start
            found = result is not None
            obs.record_retrieve(latency, found=found, trace_id=trace_ctx.trace_id)
            span.set_attribute("latency_ms", round(latency * 1000, 2))
            span.set_attribute("found", found)

            if not result:
                span.status = "error"
                span.error = "not_found"
                raise HTTPException(status_code=404, detail="Memory not found")

            await notify(
                "memory.retrieve",
                {
                    "memory_id": sanitized_id,
                    "found": True,
                    "latency_ms": round(latency * 1000, 2),
                },
                channel=Channels.MEMORY_RETRIEVE,
                correlation_id=trace_ctx.correlation_id,
                trace_id=trace_ctx.trace_id,
            )

            return {"status": "ok", "data": result}
        except HTTPException:
            latency = time.time() - start
            obs.record_retrieve(latency, found=False, trace_id=trace_ctx.trace_id)
            raise
        except ValueError as e:
            latency = time.time() - start
            obs.record_retrieve(latency, found=False, trace_id=trace_ctx.trace_id)
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            latency = time.time() - start
            obs.record_retrieve(latency, found=False, trace_id=trace_ctx.trace_id)
            logger.error(f"Failed to retrieve memory {memory_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))


@router.put("/{memory_id}")
async def update_memory(memory_id: str, request: UpdateMemoryRequest):
    """Update memory content, importance, or metadata."""
    try:
        adapter = _get_adapter()
        data = {}
        if request.content is not None:
            data["content"] = request.content
        if request.metadata is not None:
            data["metadata"] = request.metadata

        success = await adapter.update(
            memory_id,
            data=data if data else None,
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
async def delete_memory(
    memory_id: str,
    hard: bool = Query(False, description="Permanent deletion"),
):
    """Delete a memory (soft or hard delete)."""
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
    """List memories with filtering and pagination."""
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

        latency = time.time() - start
        from common_lib.modules.memory.monitoring import get_metrics_collector

        collector = get_metrics_collector()
        collector.increment("memory.list.total")
        collector.observe("memory.list.latency", latency)

        return {
            "status": "ok",
            "data": memories,
            "count": len(memories),
            "skip": request.skip,
            "limit": request.limit,
        }
    except Exception as e:
        logger.error(f"Failed to list memories: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Search Operations
# =============================================================================


@router.post("/search")
async def search_memories(
    request: SearchRequest,
    req: Request,
    rate_limit: Optional[JSONResponse] = Depends(check_rate_limit),
):
    """Full-text search across memories with optional type filtering."""
    if rate_limit:
        return rate_limit

    trace_ctx = _create_request_context(req, "memory.search")
    obs = get_observability()

    with obs.start_span(
        "memory.search",
        trace_id=trace_ctx.trace_id,
        parent_span_id=trace_ctx.parent_span_id,
        attributes={
            "query_length": len(request.query),
            "memory_type": request.memory_type or "",
            "limit": request.limit,
        },
    ) as span:
        start = time.time()
        try:
            from common_lib.modules.memory.api import get_sanitizer

            sanitizer = get_sanitizer()
            sanitized_query = sanitizer.sanitize_string(request.query, "query")
            sanitized_agent = sanitizer.sanitize_string(
                request.agent_id or "", "agent_id"
            )
            sanitized_session = sanitizer.sanitize_string(
                request.session_id or "", "session_id"
            )

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
            obs.record_search(
                latency, result_count=len(results), trace_id=trace_ctx.trace_id
            )
            span.set_attribute("latency_ms", round(latency * 1000, 2))
            span.set_attribute("result_count", len(results))

            await notify(
                "memory.search",
                {
                    "query": request.query[:100],
                    "result_count": len(results),
                    "latency_ms": round(latency * 1000, 2),
                },
                channel=Channels.MEMORY_SEARCH,
                correlation_id=trace_ctx.correlation_id,
                trace_id=trace_ctx.trace_id,
            )

            return {
                "status": "ok",
                "data": results,
                "count": len(results),
                "query": request.query,
            }
        except ValueError as e:
            latency = time.time() - start
            obs.record_search(latency, result_count=0, trace_id=trace_ctx.trace_id)
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            latency = time.time() - start
            obs.record_search(latency, result_count=0, trace_id=trace_ctx.trace_id)
            logger.error(f"Search failed for '{request.query}': {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))


@router.post("/vector-search")
async def vector_search(
    query_embedding: List[float] = Body(..., description="Query embedding vector"),
    top_k: int = Body(10, description="Number of top results"),
    threshold: float = Body(0.0, description="Minimum similarity threshold"),
):
    """Semantic vector search across memories using embedding similarity."""
    try:
        from common_lib.modules.memory.memory_storage.adapters.pgvector_adapter import (
            PgVectorAdapter,
        )
        from app.core.settings import get_settings

        settings = get_settings()
        adapter = PgVectorAdapter(settings.SQLALCHEMY_DATABASE_URI)
        results = await adapter.similarity_search(
            query_embedding, top_k=top_k, threshold=threshold
        )
        return {
            "status": "ok",
            "data": results,
            "count": len(results),
        }
    except Exception as e:
        logger.error(f"Vector search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Session Operations
# =============================================================================


@router.get("/session/{session_id}")
async def get_session_memories(
    session_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
):
    """Get all memories for a specific session."""
    try:
        adapter = _get_adapter()
        memories = await adapter.get_by_session(session_id, skip=skip, limit=limit)
        return {
            "status": "ok",
            "data": memories,
            "count": len(memories),
            "session_id": session_id,
        }
    except Exception as e:
        logger.error(f"Failed to get session memories: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/session/{session_id}/state")
async def get_session_state(
    session_id: str,
    include_content: bool = Query(True),
    max_memories: int = Query(10, ge=1, le=100),
):
    """Get session state including memory count and recent memories."""
    try:
        adapter = _get_adapter()
        memories = await adapter.get_by_session(session_id)
        result = {
            "session_id": session_id,
            "memory_count": len(memories),
            "memories": memories[:max_memories]
            if include_content
            else [{"id": m.get("id")} for m in memories[:max_memories]],
        }
        return {"status": "ok", "data": result}
    except Exception as e:
        logger.error(f"Failed to get session state: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Agent Operations
# =============================================================================


@router.get("/agent/{agent_id}")
async def get_agent_memories(
    agent_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
):
    """Get all memories for a specific agent."""
    try:
        adapter = _get_adapter()
        memories = await adapter.get_by_agent(agent_id, skip=skip, limit=limit)
        return {
            "status": "ok",
            "data": memories,
            "count": len(memories),
            "agent_id": agent_id,
        }
    except Exception as e:
        logger.error(f"Failed to get agent memories: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Security Operations
# =============================================================================


@router.post("/pii/redact", response_model=PIIResponse)
async def redact_pii(request: PIIRequest):
    """Detect and redact PII from memory content."""
    try:
        from common_lib.modules.security.pii.unified_detector import (
            get_unified_pii_detector,
        )

        detector = get_unified_pii_detector(use_presidio=request.use_presidio)
        result = detector.detect(request.content)
        scrubbed = (
            detector.scrub(request.content, strategy=request.strategy)
            if result.entities
            else request.content
        )
        entities = [
            {"type": e.entity_type, "value": e.text, "start": e.start, "end": e.end}
            for e in result.entities
        ]
        return PIIResponse(
            scrubbed_content=scrubbed,
            pii_entities=entities,
            entity_count=len(entities),
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
    """Execute GDPR right-to-forget request for an agent."""
    if rate_limit:
        return rate_limit

    try:
        from common_lib.modules.memory.api import get_sanitizer

        sanitizer = get_sanitizer()
        sanitized_agent_id = sanitizer.validate_agent_id(request.agent_id)

        adapter = _get_adapter()
        export_path = ""
        if request.export_first:
            export_path = f"/tmp/gdpr_export_{sanitized_agent_id}.json"

        if request.hard_delete:
            count = await adapter.hard_delete_by_agent(sanitized_agent_id)
        else:
            count = await adapter.soft_delete_by_agent(sanitized_agent_id)

        return GDPRResponse(
            deleted_count=count,
            export_path=export_path,
            success=True,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"GDPR right-to-forget failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Batch Operations
# =============================================================================


@router.post("/batch/store")
async def batch_store(records: List[Dict[str, Any]] = Body(...)):
    """Store multiple memories in a single batch operation."""
    try:
        adapter = _get_adapter()
        count = await adapter.batch_store(records)
        return {
            "status": "ok",
            "stored_count": count,
            "total_requested": len(records),
        }
    except Exception as e:
        logger.error(f"Batch store failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Monitoring & Metrics Endpoints
# =============================================================================


@router.get("/metrics")
async def memory_metrics(
    format: str = Query("json", description="Output format: json or prometheus"),
):
    """Get memory system metrics in JSON or Prometheus format."""
    try:
        from common_lib.modules.memory.monitoring import get_metrics_collector

        collector = get_metrics_collector()
        collector.evaluate_alerts()

        if format == "prometheus":
            from fastapi.responses import PlainTextResponse

            return PlainTextResponse(content=collector.export_prometheus())

        metrics = collector.get_all_metrics()
        return {
            "status": "ok",
            "data": metrics,
        }
    except Exception as e:
        logger.error(f"Failed to get metrics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/metrics/alerts/evaluate")
async def evaluate_alerts():
    """Manually trigger alert rule evaluation."""
    try:
        from common_lib.modules.memory.monitoring import get_metrics_collector

        collector = get_metrics_collector()
        alerts = collector.evaluate_alerts()

        return {
            "status": "ok",
            "active_alerts": [
                {
                    "rule_name": a.rule_name,
                    "metric": a.metric,
                    "current_value": a.current_value,
                    "threshold": a.threshold,
                    "severity": a.severity,
                    "triggered_at": a.triggered_at,
                    "message": a.message,
                }
                for a in alerts
            ],
            "alert_count": len(alerts),
        }
    except Exception as e:
        logger.error(f"Alert evaluation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/metrics/alerts/add")
async def add_alert_rule(
    name: str = Body(...),
    metric: str = Body(...),
    condition: str = Body(..., description="gt, lt, eq, gte, lte"),
    threshold: float = Body(...),
    severity: str = Body("warning"),
    duration_seconds: float = Body(60),
):
    """Add a new alert rule."""
    try:
        from common_lib.modules.memory.monitoring import (
            get_metrics_collector,
            AlertRule,
        )

        collector = get_metrics_collector()
        rule = AlertRule(
            name=name,
            metric=metric,
            condition=condition,
            threshold=threshold,
            severity=severity,
            duration_seconds=duration_seconds,
        )
        collector.add_alert_rule(rule)

        return {
            "status": "ok",
            "message": f"Alert rule '{name}' added",
        }
    except Exception as e:
        logger.error(f"Failed to add alert rule: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/metrics/reset")
async def reset_metrics():
    """Reset all metrics counters and gauges."""
    try:
        from common_lib.modules.memory.monitoring import get_metrics_collector

        collector = get_metrics_collector()
        collector.reset()

        return {
            "status": "ok",
            "message": "All metrics reset",
        }
    except Exception as e:
        logger.error(f"Failed to reset metrics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Workflow Execution Endpoints
# =============================================================================


class WorkflowExecuteRequest(BaseModel):
    workflow_id: str
    inputs: Dict[str, Any] = {}


class WorkflowExecuteResponse(BaseModel):
    workflow_id: str
    status: str
    execution_id: str
    outputs: Dict[str, Any]
    duration_ms: float


class WorkflowListResponse(BaseModel):
    workflows: List[Dict[str, Any]]


@router.get("/workflows", response_model=WorkflowListResponse)
async def list_memory_workflows(
    category: str = Query(None, description="Filter by category"),
):
    """List all available memory workflows."""
    try:
        from common_lib.modules.workflows.standard.registry.workflow_registry import (
            get_workflow_registry,
        )

        registry = get_workflow_registry()
        workflows = []
        for wf_id, wf_def in registry._workflows.items():
            if wf_def.get("category") == "memory" or wf_id.startswith("memory_"):
                if category and wf_def.get("category") != category:
                    continue
                workflows.append(
                    {
                        "id": wf_id,
                        "name": wf_def.get("name", ""),
                        "description": wf_def.get("description", "")[:200],
                        "category": wf_def.get("category", ""),
                        "version": wf_def.get("version", ""),
                    }
                )
        return WorkflowListResponse(workflows=workflows)
    except Exception as e:
        logger.error(f"Failed to list workflows: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/workflows/execute", response_model=WorkflowExecuteResponse)
async def execute_memory_workflow(request: WorkflowExecuteRequest):
    """Execute a memory workflow by ID with provided inputs."""
    import time
    import uuid
    import asyncio

    start_time = time.time()

    try:
        from common_lib.modules.workflows.standard.registry.workflow_registry import (
            get_workflow_registry,
        )
        from common_lib.modules.workflows.standard.builder import WorkflowBuilder
        from common_lib.modules.workflows.standard.executor import WorkflowExecutor
        from common_lib.modules.workflows.standard.execution.executor import (
            GraphExecutor,
        )
        from common_lib.modules.workflows.standard.execution.primitives import (
            Graph,
            State,
            Transition,
        )
        from common_lib.modules.workflows.standard.execution.context import (
            ExecutionContext,
        )
        from common_lib.modules.core_infrastructure.registry import RegistryService

        registry = get_workflow_registry()
        workflow_def = registry._workflows.get(request.workflow_id)
        if not workflow_def:
            raise HTTPException(
                status_code=404, detail=f"Workflow not found: {request.workflow_id}"
            )

        # Build graph from workflow definition
        nodes = workflow_def.get("nodes", [])
        edges = workflow_def.get("edges", [])

        states = []
        for node_def in nodes:
            if not node_def.get("enabled", True):
                continue
            state = State(
                id=node_def["id"],
                tool_id=node_def["tool_id"],
                metadata={
                    "config": node_def.get("config", {}),
                    "condition": node_def.get("condition"),
                },
            )
            states.append(state)

        transitions = []
        for edge_def in edges:
            condition = None
            cond_def = edge_def.get("condition")
            if cond_def and cond_def.get("type") == "feature_enabled":
                flag = cond_def.get("params", {}).get("flag")
                condition = lambda ctx, f=flag: True  # Simplified

            transitions.append(
                Transition(
                    from_state_id=edge_def["from_node"],
                    to_state_id=edge_def["to_node"],
                    condition=condition,
                )
            )

        graph = Graph(
            id=request.workflow_id,
            states=states,
            transitions=transitions,
        )

        # Execute
        exec_context = ExecutionContext(
            trace_id=str(uuid.uuid4()),
            workflow_id=request.workflow_id,
            workflow_state=request.inputs.copy(),
        )

        executor = GraphExecutor(registry=RegistryService())
        result = await asyncio.to_thread(
            executor.execute, graph, request.inputs, exec_context
        )

        duration_ms = (time.time() - start_time) * 1000

        return WorkflowExecuteResponse(
            workflow_id=request.workflow_id,
            status="completed",
            execution_id=exec_context.trace_id,
            outputs=result if isinstance(result, dict) else {},
            duration_ms=round(duration_ms, 2),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Workflow execution failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Export/Import Endpoints
# =============================================================================


class ExportRequest(BaseModel):
    format: str = "json"
    include_deleted: bool = False
    agent_id: Optional[str] = None
    session_id: Optional[str] = None
    memory_type: Optional[str] = None
    max_records: int = 10000


class ExportResponse(BaseModel):
    file_path: str
    format: str
    record_count: int
    file_size_bytes: int
    exported_at: str


class ImportResponse(BaseModel):
    imported_count: int
    skipped_count: int
    error_count: int
    errors: List[str]
    duration_ms: float


@router.post("/export", response_model=ExportResponse)
async def export_memories(
    request: ExportRequest,
    req: Request,
    rate_limit: Optional[JSONResponse] = Depends(check_rate_limit),
):
    """Export memories to JSON or CSV file."""
    if rate_limit:
        return rate_limit

    try:
        import tempfile
        from common_lib.modules.memory.memory_storage.export_import import (
            MemoryExportImportService,
            ExportConfig,
        )

        adapter = _get_adapter()
        service = MemoryExportImportService(adapter)

        # Create temp file
        suffix = ".json" if request.format == "json" else ".csv"
        fd, output_path = tempfile.mkstemp(suffix=suffix, prefix="memory_export_")
        os.close(fd)

        config = ExportConfig(
            format=request.format,
            include_deleted=request.include_deleted,
            filter_agent_id=request.agent_id,
            filter_session_id=request.session_id,
            filter_memory_type=request.memory_type,
            max_records=request.max_records,
        )

        result = await service.export(output_path, config)

        return ExportResponse(
            file_path=result.file_path,
            format=result.format,
            record_count=result.record_count,
            file_size_bytes=result.file_size_bytes,
            exported_at=result.exported_at,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Export failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/import", response_model=ImportResponse)
async def import_memories(
    file_path: str = Body(..., embed=True, description="Path to export file"),
    skip_duplicates: bool = Body(True, embed=True),
    update_existing: bool = Body(False, embed=True),
    req: Request = None,
    rate_limit: Optional[JSONResponse] = Depends(check_rate_limit),
):
    """Import memories from JSON or CSV export file."""
    if rate_limit:
        return rate_limit

    try:
        from common_lib.modules.memory.memory_storage.export_import import (
            MemoryExportImportService,
        )

        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail=f"File not found: {file_path}")

        adapter = _get_adapter()
        service = MemoryExportImportService(adapter)

        result = await service.import_data(
            file_path,
            skip_duplicates=skip_duplicates,
            update_existing=update_existing,
        )

        return ImportResponse(
            imported_count=result.imported_count,
            skipped_count=result.skipped_count,
            error_count=result.error_count,
            errors=result.errors,
            duration_ms=result.duration_ms,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Import failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/backup")
async def create_backup(
    backup_dir: str = Body("./backups", embed=True),
    req: Request = None,
    rate_limit: Optional[JSONResponse] = Depends(check_rate_limit),
):
    """Create a full backup of all memories."""
    if rate_limit:
        return rate_limit

    try:
        from common_lib.modules.memory.memory_storage.export_import import (
            MemoryExportImportService,
        )

        adapter = _get_adapter()
        service = MemoryExportImportService(adapter)

        result = await service.create_backup(backup_dir)

        return {
            "status": "ok",
            "file_path": result.file_path,
            "record_count": result.record_count,
            "file_size_bytes": result.file_size_bytes,
        }
    except Exception as e:
        logger.error(f"Backup failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/restore")
async def restore_backup(
    backup_path: str = Body(..., embed=True, description="Path to backup file"),
    req: Request = None,
    rate_limit: Optional[JSONResponse] = Depends(check_rate_limit),
):
    """Restore memories from a backup file."""
    if rate_limit:
        return rate_limit

    try:
        from common_lib.modules.memory.memory_storage.export_import import (
            MemoryExportImportService,
        )

        if not os.path.exists(backup_path):
            raise HTTPException(
                status_code=404, detail=f"Backup not found: {backup_path}"
            )

        adapter = _get_adapter()
        service = MemoryExportImportService(adapter)

        result = await service.restore_from_backup(backup_path)

        return {
            "status": "ok",
            "imported_count": result.imported_count,
            "skipped_count": result.skipped_count,
            "error_count": result.error_count,
            "duration_ms": result.duration_ms,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Restore failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Configuration Endpoints
# =============================================================================


class ConfigUpdateRequest(BaseModel):
    database: Optional[Dict[str, Any]] = None
    embedding: Optional[Dict[str, Any]] = None
    rate_limit: Optional[Dict[str, Any]] = None
    security: Optional[Dict[str, Any]] = None
    feature_flags: Optional[Dict[str, Any]] = None


@router.get("/config")
async def get_memory_config():
    """Get current memory system configuration."""
    try:
        from common_lib.modules.memory.config import get_config

        config = get_config()
        return {
            "status": "ok",
            "config": {
                "database": {
                    "url": config.database.url,
                    "pool_size": config.database.pool_size,
                    "max_overflow": config.database.max_overflow,
                },
                "embedding": {
                    "model_name": config.embedding.model_name,
                    "device": config.embedding.device,
                    "batch_size": config.embedding.batch_size,
                },
                "rate_limit": {
                    "enabled": config.rate_limit.enabled,
                    "requests_per_minute": config.rate_limit.requests_per_minute,
                    "requests_per_hour": config.rate_limit.requests_per_hour,
                },
                "security": {
                    "pii_scan_enabled": config.security.pii_scan_enabled,
                    "max_content_length": config.security.max_content_length,
                    "gdpr_retention_days": config.security.gdpr_retention_days,
                },
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


@router.put("/config")
async def update_memory_config(
    request: ConfigUpdateRequest,
    req: Request,
    rate_limit: Optional[JSONResponse] = Depends(check_rate_limit),
):
    """Update memory system configuration."""
    if rate_limit:
        return rate_limit

    try:
        from common_lib.modules.memory.config import get_config_manager

        updates = {}
        if request.database:
            updates["database"] = request.database
        if request.embedding:
            updates["embedding"] = request.embedding
        if request.rate_limit:
            updates["rate_limit"] = request.rate_limit
        if request.security:
            updates["security"] = request.security
        if request.feature_flags:
            updates["feature_flags"] = request.feature_flags

        manager = get_config_manager()
        config = manager.update(updates)

        return {
            "status": "ok",
            "message": "Configuration updated",
            "version": config.version,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update config: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/config/reset")
async def reset_memory_config(
    req: Request,
    rate_limit: Optional[JSONResponse] = Depends(check_rate_limit),
):
    """Reset configuration to defaults."""
    if rate_limit:
        return rate_limit

    try:
        from common_lib.modules.memory.config import get_config_manager

        manager = get_config_manager()
        config = manager.reset_to_defaults()

        return {
            "status": "ok",
            "message": "Configuration reset to defaults",
            "version": config.version,
        }
    except Exception as e:
        logger.error(f"Failed to reset config: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# Wire sub-routers (core, context, storage, observability, blueprints, etc.)
# This import has the side-effect of attaching all sub-routers to this file's
# `router` object via router.include_router() calls.
import app.modules.memory.wire_routes  # noqa: F401, E402
