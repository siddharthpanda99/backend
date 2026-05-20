"""Memory API Routes - CRUD operations for cognitive memory system.

Provides REST endpoints for memory operations:
- Store, retrieve, update, delete memories
- Search and vector search
- Session and agent memory management
- Memory statistics and health
- PII redaction and GDPR compliance
"""

import json
import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel

router = APIRouter(prefix="/memory", tags=["memory"])

logger = logging.getLogger(__name__)


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
    from common_lib.modules.memory.memory_storage.adapters.relational_adapter import (
        RelationalStorageAdapter,
    )
    import os

    return RelationalStorageAdapter(os.environ.get("DATABASE_URL", "sqlite:///test.db"))


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
# Core Memory Operations
# =============================================================================


@router.post("/store", response_model=StoreMemoryResponse)
async def store_memory(request: StoreMemoryRequest):
    """Store a new memory record with metadata and policy checks."""
    try:
        svc = _get_memory_service()
        mem_id = svc.store_memory(
            request.content,
            request.memory_type,
            request.agent_id,
            request.session_id,
            request.importance,
            request.confidence,
            enable_pii_scan=request.enable_pii_scan,
            store_in_hot=request.store_in_hot,
        )
        return StoreMemoryResponse(
            memory_id=str(mem_id),
            status="stored",
            content_length=len(request.content),
        )
    except Exception as e:
        logger.error(f"Failed to store memory: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{memory_id}")
async def retrieve_memory(memory_id: str):
    """Retrieve a memory by its unique ID."""
    try:
        adapter = _get_adapter()
        result = await adapter.retrieve(memory_id)
        if not result:
            raise HTTPException(status_code=404, detail="Memory not found")
        return {"status": "ok", "data": result}
    except HTTPException:
        raise
    except Exception as e:
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


@router.get("/stats")
async def memory_stats(
    include_deleted: bool = Query(False, description="Include soft-deleted memories"),
):
    """Get memory storage statistics and metrics."""
    try:
        adapter = _get_adapter()
        stats = await adapter.get_stats(include_deleted=include_deleted)
        return {"status": "ok", "data": stats}
    except Exception as e:
        logger.error(f"Failed to get memory stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Search Operations
# =============================================================================


@router.post("/search")
async def search_memories(request: SearchRequest):
    """Full-text search across memories with optional type filtering."""
    try:
        adapter = _get_adapter()
        results = await adapter.search(
            request.query,
            memory_type=request.memory_type,
            agent_id=request.agent_id,
            session_id=request.session_id,
            skip=request.skip,
            limit=request.limit,
        )
        return {
            "status": "ok",
            "data": results,
            "count": len(results),
            "query": request.query,
        }
    except Exception as e:
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
        import os

        adapter = PgVectorAdapter(os.environ.get("DATABASE_URL", "sqlite:///test.db"))
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
async def gdpr_right_to_forget(request: GDPRRequest):
    """Execute GDPR right-to-forget request for an agent."""
    try:
        adapter = _get_adapter()
        export_path = ""
        if request.export_first:
            export_path = f"/tmp/gdpr_export_{request.agent_id}.json"

        if request.hard_delete:
            count = await adapter.hard_delete_by_agent(request.agent_id)
        else:
            count = await adapter.soft_delete_by_agent(request.agent_id)

        return GDPRResponse(
            deleted_count=count,
            export_path=export_path,
            success=True,
        )
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
# Health Check
# =============================================================================


@router.get("/health")
async def memory_health():
    """Check memory system health."""
    try:
        adapter = _get_adapter()
        healthy = await adapter.health_check()
        stats = await adapter.get_stats()
        return {
            "status": "ok" if healthy else "degraded",
            "healthy": healthy,
            "stats": stats,
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        return {
            "status": "error",
            "healthy": False,
            "error": str(e),
        }


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
