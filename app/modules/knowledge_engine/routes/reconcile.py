"""
Knowledge Engine — Reconciliation Routes.

Thin transport for entity/claim reconciliation and deduplication.
Delegates to common_lib.modules.knowledge_engine.services.reconciliation_service.ReconciliationService
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from common_lib.modules.knowledge_engine.services.reconciliation_service import (
    ReconciliationStatus,
    ReconciliationType,
    ReconciliationCandidate,
    ReconciliationTask,
    get_reconciliation_service,
)

router = APIRouter(prefix="/reconcile", tags=["Knowledge Engine — Reconciliation"])


# ── Request/Response Models ────────────────────────────────────


class ReconciliationTaskCreateRequest(BaseModel):
    reconciliation_type: ReconciliationType
    object_type: str
    filter_criteria: dict[str, Any] = Field(default_factory=dict)
    source_ids: list[str] = Field(default_factory=list)
    similarity_threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    auto_merge_threshold: float = Field(default=0.95, ge=0.0, le=1.0)
    max_candidates: int = Field(default=1000, ge=1, le=10000)


class ReconciliationTaskResponse(BaseModel):
    task: ReconciliationTask


class ReconciliationTaskListResponse(BaseModel):
    tasks: list[ReconciliationTask]
    total: int


class ReconciliationCandidateResolveRequest(BaseModel):
    resolution: str = Field(
        ..., description="merge | keep_both | delete_1 | delete_2 | manual"
    )
    resolved_by: str | None = None
    resolution_notes: str | None = None


class ReconciliationCandidateResponse(BaseModel):
    candidate: ReconciliationCandidate


class ReconciliationCandidatesResponse(BaseModel):
    candidates: list[ReconciliationCandidate]


class DeduplicateEntitiesRequest(BaseModel):
    entity_ids: list[str] = Field(default_factory=list)
    similarity_threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    auto_merge: bool = False


class DeduplicateClaimsRequest(BaseModel):
    claim_ids: list[str] = Field(default_factory=list)
    similarity_threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    auto_merge: bool = False


class ResolveContradictionsRequest(BaseModel):
    claim_ids: list[str] = Field(default_factory=list)
    similarity_threshold: float = Field(default=0.75, ge=0.0, le=1.0)


# ── Dependency Injection ────────────────────────────────────────


def get_service() -> Any:
    """Get reconciliation service instance."""
    return get_reconciliation_service()


# ── Routes ─────────────────────────────────────────────────────


@router.post("/tasks", response_model=ReconciliationTaskResponse, status_code=201)
async def create_reconciliation_task(
    request: ReconciliationTaskCreateRequest,
    service=Depends(get_service),
    created_by: str = Query(default="api", description="Creator identifier"),
):
    """Create a reconciliation task."""
    try:
        task = await service.create_task(
            reconciliation_type=request.reconciliation_type,
            object_type=request.object_type,
            filter_criteria=request.filter_criteria,
            source_ids=request.source_ids,
            similarity_threshold=request.similarity_threshold,
            auto_merge_threshold=request.auto_merge_threshold,
            max_candidates=request.max_candidates,
            created_by=created_by,
        )
        return ReconciliationTaskResponse(task=task)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to create reconciliation task: {exc}"
        ) from exc


@router.get("/tasks/{task_id}", response_model=ReconciliationTaskResponse)
async def get_reconciliation_task(
    task_id: UUID,
    service=Depends(get_service),
):
    """Get a reconciliation task by ID."""
    try:
        task = await service.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
        return ReconciliationTaskResponse(task=task)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to get task: {exc}"
        ) from exc


@router.get("/tasks", response_model=ReconciliationTaskListResponse)
async def list_reconciliation_tasks(
    status: ReconciliationStatus | None = Query(None, description="Filter by status"),
    reconciliation_type: ReconciliationType | None = Query(
        None, description="Filter by type"
    ),
    limit: int = Query(100, ge=1, le=1000, description="Max results"),
    offset: int = Query(0, ge=0, description="Offset"),
    service=Depends(get_service),
):
    """List reconciliation tasks."""
    try:
        result = await service.list_tasks(
            status=status,
            reconciliation_type=reconciliation_type,
            limit=limit,
            offset=offset,
        )
        return ReconciliationTaskListResponse(**result)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to list tasks: {exc}"
        ) from exc


@router.post("/tasks/{task_id}/execute", response_model=ReconciliationTaskResponse)
async def execute_reconciliation_task(
    task_id: UUID,
    service=Depends(get_service),
):
    """Execute a reconciliation task."""
    try:
        task = await service.execute_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
        return ReconciliationTaskResponse(task=task)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to execute task: {exc}"
        ) from exc


@router.get(
    "/tasks/{task_id}/candidates", response_model=ReconciliationCandidatesResponse
)
async def get_reconciliation_candidates(
    task_id: UUID,
    resolution: str | None = Query(None, description="Filter by resolution"),
    service=Depends(get_service),
):
    """Get candidates for a task."""
    try:
        candidates = await service.get_candidates(task_id, resolution=resolution)
        return ReconciliationCandidatesResponse(candidates=candidates)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to get candidates: {exc}"
        ) from exc


@router.put(
    "/candidates/{candidate_id}/resolve", response_model=ReconciliationCandidateResponse
)
async def resolve_reconciliation_candidate(
    candidate_id: UUID,
    request: ReconciliationCandidateResolveRequest,
    service=Depends(get_service),
):
    """Resolve a reconciliation candidate."""
    try:
        candidate = await service.resolve_candidate(
            candidate_id=candidate_id,
            resolution=request.resolution,
            resolved_by=request.resolved_by,
            resolution_notes=request.resolution_notes,
        )
        if not candidate:
            raise HTTPException(
                status_code=404, detail=f"Candidate {candidate_id} not found"
            )
        return ReconciliationCandidateResponse(candidate=candidate)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to resolve candidate: {exc}"
        ) from exc


# ── Specialized Reconciliation Endpoints ───────────────────────


@router.post("/deduplicate/entities", response_model=ReconciliationTaskResponse)
async def deduplicate_entities(
    request: DeduplicateEntitiesRequest,
    service=Depends(get_service),
):
    """Find and resolve duplicate entities."""
    try:
        task = await service.deduplicate_entities(
            entity_ids=request.entity_ids if request.entity_ids else None,
            similarity_threshold=request.similarity_threshold,
            auto_merge=request.auto_merge,
        )
        return ReconciliationTaskResponse(task=task)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to deduplicate entities: {exc}"
        ) from exc


@router.post("/deduplicate/claims", response_model=ReconciliationTaskResponse)
async def deduplicate_claims(
    request: DeduplicateClaimsRequest,
    service=Depends(get_service),
):
    """Find and resolve duplicate claims."""
    try:
        task = await service.deduplicate_claims(
            claim_ids=request.claim_ids if request.claim_ids else None,
            similarity_threshold=request.similarity_threshold,
            auto_merge=request.auto_merge,
        )
        return ReconciliationTaskResponse(task=task)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to deduplicate claims: {exc}"
        ) from exc


@router.post("/resolve/contradictions", response_model=ReconciliationTaskResponse)
async def resolve_contradictions(
    request: ResolveContradictionsRequest,
    service=Depends(get_service),
):
    """Find and resolve claim contradictions."""
    try:
        task = await service.resolve_contradictions(
            claim_ids=request.claim_ids if request.claim_ids else None,
            similarity_threshold=request.similarity_threshold,
        )
        return ReconciliationTaskResponse(task=task)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to resolve contradictions: {exc}"
        ) from exc
