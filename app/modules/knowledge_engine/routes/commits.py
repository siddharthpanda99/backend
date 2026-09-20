"""
Knowledge Engine — Commit Routes.

Thin transport for commit operations.
Delegates to common_lib.modules.knowledge_engine.services.commit_service.CommitService
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from common_lib.modules.knowledge_engine.models.commit import (
    KnowledgeCommit,
    CommitMetadata,
    CommitChange,
    ChangeType,
    CommitBatch,
    CommitDiff,
)
from common_lib.modules.knowledge_engine.services.commit_service import (
    get_commit_service,
)

router = APIRouter(prefix="/commits", tags=["Knowledge Engine — Commits"])


# ── Request/Response Models ────────────────────────────────────


class CommitCreateRequest(BaseModel):
    metadata: CommitMetadata
    changes: list[CommitChange] = Field(default_factory=list)


class CommitResponse(BaseModel):
    commit: KnowledgeCommit


class CommitListResponse(BaseModel):
    commits: list[KnowledgeCommit]
    total: int


class CommitBatchCreateRequest(BaseModel):
    commits: list[KnowledgeCommit]


class CommitBatchResponse(BaseModel):
    batch: CommitBatch


class DiffResponse(BaseModel):
    diff: CommitDiff


# ── Dependency Injection ────────────────────────────────────────


def get_service() -> Any:
    """Get commit service instance."""
    return get_commit_service()


# ── Routes ─────────────────────────────────────────────────────


@router.post("", response_model=CommitResponse, status_code=201)
async def create_commit(
    request: CommitCreateRequest,
    service=Depends(get_service),
):
    """Create a new knowledge commit."""
    try:
        commit = await service.create_commit(
            metadata=request.metadata,
            changes=request.changes,
        )
        return CommitResponse(commit=commit)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to create commit: {exc}"
        ) from exc


@router.get("/{commit_id}", response_model=CommitResponse)
async def get_commit(
    commit_id: str | UUID,
    service=Depends(get_service),
):
    """Get a commit by ID."""
    try:
        commit = await service.get_commit(str(commit_id))
        if not commit:
            raise HTTPException(status_code=404, detail=f"Commit {commit_id} not found")
        return CommitResponse(commit=commit)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to get commit: {exc}"
        ) from exc


@router.get("", response_model=CommitListResponse)
async def list_commits(
    branch_id: UUID | None = Query(None, description="Filter by branch"),
    author_id: str | None = Query(None, description="Filter by author"),
    status: str | None = Query(None, description="Filter by status"),
    limit: int = Query(100, ge=1, le=1000, description="Max results"),
    offset: int = Query(0, ge=0, description="Offset"),
    service=Depends(get_service),
):
    """List commits with filtering."""
    try:
        result = await service.list_commits(
            branch_id=branch_id,
            author_id=author_id,
            status=status,
            limit=limit,
            offset=offset,
        )
        return CommitListResponse(**result)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to list commits: {exc}"
        ) from exc


@router.post("/{commit_id}/rollback", response_model=CommitResponse)
async def rollback_commit(
    commit_id: str | UUID,
    service=Depends(get_service),
    rolled_back_by: str = Query(default="api", description="Rollback initiator"),
    rollback_reason: str | None = Query(None, description="Rollback reason"),
):
    """Rollback a commit."""
    try:
        commit = await service.rollback_commit(
            commit_id=str(commit_id),
            rolled_back_by=rolled_back_by,
            rollback_reason=rollback_reason,
        )
        if not commit:
            raise HTTPException(status_code=404, detail=f"Commit {commit_id} not found")
        return CommitResponse(commit=commit)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to rollback commit: {exc}"
        ) from exc


@router.get("/diff/{target_commit_id}", response_model=DiffResponse)
async def diff_commits(
    target_commit_id: str | UUID,
    base_commit_id: str | UUID | None = Query(None, description="Base commit for diff"),
    service=Depends(get_service),
):
    """Generate diff between two commits."""
    try:
        diff = await service.diff_commits(
            target_commit_id=str(target_commit_id),
            base_commit_id=str(base_commit_id) if base_commit_id else None,
        )
        return DiffResponse(diff=diff)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to diff commits: {exc}"
        ) from exc


# ── Batch Routes ───────────────────────────────────────────────


@router.post("/batch", response_model=CommitBatchResponse, status_code=201)
async def create_batch(
    request: CommitBatchCreateRequest,
    service=Depends(get_service),
):
    """Create a batch of commits."""
    try:
        batch = await service.create_batch(request.commits)
        return CommitBatchResponse(batch=batch)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to create batch: {exc}"
        ) from exc


@router.post("/batch/{batch_id}/commit", response_model=CommitBatchResponse)
async def commit_batch(
    batch_id: UUID,
    service=Depends(get_service),
):
    """Commit a batch of pending commits."""
    try:
        batch = await service.commit_batch(batch_id)
        if not batch:
            raise HTTPException(status_code=404, detail=f"Batch {batch_id} not found")
        return CommitBatchResponse(batch=batch)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to commit batch: {exc}"
        ) from exc
