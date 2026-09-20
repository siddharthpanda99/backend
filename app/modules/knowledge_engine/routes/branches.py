"""
Knowledge Engine — Branch Routes.

Thin transport for branch operations.
Delegates to common_lib.modules.knowledge_engine.services.branch_service.BranchService
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from common_lib.modules.knowledge_engine.models.branch import (
    KnowledgeBranch,
    BranchStatus,
    MergeStrategy,
    ConflictResolution,
    BranchMerge,
    BranchComparison,
    BranchPolicy,
)
from common_lib.modules.knowledge_engine.services.branch_service import (
    get_branch_service,
)

router = APIRouter(prefix="/branches", tags=["Knowledge Engine — Branches"])


# ── Request/Response Models ────────────────────────────────────


class BranchCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=256)
    display_name: str | None = Field(None, max_length=256)
    description: str | None = Field(None, max_length=2048)
    base_commit_id: str | None = None
    base_branch_id: UUID | None = None
    purpose: str | None = None
    tags: list[str] = Field(default_factory=list)
    category: str | None = None
    owner_id: str | None = None
    owner_name: str | None = None
    collaborators: list[str] = Field(default_factory=list)
    is_public: bool = False
    auto_cleanup: bool = True
    retention_days: int = 90


class BranchUpdateRequest(BaseModel):
    display_name: str | None = Field(None, max_length=256)
    description: str | None = Field(None, max_length=2048)
    head_commit_id: str | None = None
    status: BranchStatus | None = None
    purpose: str | None = None
    tags: list[str] | None = None
    collaborators: list[str] | None = None
    is_public: bool | None = None
    metadata: dict[str, Any] | None = None


class BranchResponse(BaseModel):
    branch: KnowledgeBranch


class BranchListResponse(BaseModel):
    branches: list[KnowledgeBranch]
    total: int


class BranchMergeRequest(BaseModel):
    source_branch_id: UUID
    target_branch_id: UUID
    strategy: MergeStrategy = MergeStrategy.THREE_WAY
    message: str = ""
    description: str | None = None


class BranchMergeResponse(BaseModel):
    merge: BranchMerge


class BranchComparisonResponse(BaseModel):
    comparison: BranchComparison


class BranchPolicyResponse(BaseModel):
    policy: BranchPolicy


class BranchPolicyUpdateRequest(BaseModel):
    name_pattern: str | None = None
    require_issue_reference: bool | None = None
    allow_anyone_create: bool | None = None
    protected_branches: list[str] | None = None
    require_review_for_protected: bool | None = None
    required_reviewers: int | None = None
    allowed_strategies: list[MergeStrategy] | None = None
    default_strategy: MergeStrategy | None = None
    auto_delete_merged: bool | None = None
    max_branch_age_days: int | None = None
    max_branches_per_user: int | None = None


# ── Dependency Injection ────────────────────────────────────────


def get_service() -> Any:
    """Get branch service instance."""
    return get_branch_service()


# ── Routes ─────────────────────────────────────────────────────


@router.post("", response_model=BranchResponse, status_code=201)
async def create_branch(
    request: BranchCreateRequest,
    service=Depends(get_service),
):
    """Create a new knowledge branch."""
    try:
        branch = await service.create_branch(
            name=request.name,
            display_name=request.display_name,
            description=request.description,
            base_commit_id=request.base_commit_id,
            base_branch_id=request.base_branch_id,
            purpose=request.purpose,
            tags=request.tags,
            category=request.category,
            owner_id=request.owner_id,
            owner_name=request.owner_name,
            collaborators=request.collaborators,
            is_public=request.is_public,
            auto_cleanup=request.auto_cleanup,
            retention_days=request.retention_days,
        )
        return BranchResponse(branch=branch)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to create branch: {exc}"
        ) from exc


@router.get("/{branch_id}", response_model=BranchResponse)
async def get_branch(
    branch_id: UUID,
    service=Depends(get_service),
):
    """Get a branch by ID."""
    try:
        branch = await service.get_branch(branch_id)
        if not branch:
            raise HTTPException(status_code=404, detail=f"Branch {branch_id} not found")
        return BranchResponse(branch=branch)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to get branch: {exc}"
        ) from exc


@router.get("/by-name/{name}", response_model=BranchResponse)
async def get_branch_by_name(
    name: str,
    service=Depends(get_service),
):
    """Get a branch by name."""
    try:
        branch = await service.get_branch_by_name(name)
        if not branch:
            raise HTTPException(status_code=404, detail=f"Branch '{name}' not found")
        return BranchResponse(branch=branch)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to get branch: {exc}"
        ) from exc


@router.get("", response_model=BranchListResponse)
async def list_branches(
    status: BranchStatus | None = Query(None, description="Filter by status"),
    owner_id: str | None = Query(None, description="Filter by owner"),
    purpose: str | None = Query(None, description="Filter by purpose"),
    is_public: bool | None = Query(None, description="Filter by public"),
    limit: int = Query(100, ge=1, le=1000, description="Max results"),
    offset: int = Query(0, ge=0, description="Offset"),
    service=Depends(get_service),
):
    """List branches with filtering."""
    try:
        result = await service.list_branches(
            status=status,
            owner_id=owner_id,
            purpose=purpose,
            is_public=is_public,
            limit=limit,
            offset=offset,
        )
        return BranchListResponse(**result)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to list branches: {exc}"
        ) from exc


@router.put("/{branch_id}", response_model=BranchResponse)
async def update_branch(
    branch_id: UUID,
    request: BranchUpdateRequest,
    service=Depends(get_service),
):
    """Update a branch."""
    try:
        branch = await service.update_branch(
            branch_id=branch_id,
            display_name=request.display_name,
            description=request.description,
            head_commit_id=request.head_commit_id,
            status=request.status,
            purpose=request.purpose,
            tags=request.tags,
            collaborators=request.collaborators,
            is_public=request.is_public,
            metadata=request.metadata,
        )
        if not branch:
            raise HTTPException(status_code=404, detail=f"Branch {branch_id} not found")
        return BranchResponse(branch=branch)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to update branch: {exc}"
        ) from exc


@router.delete("/{branch_id}")
async def delete_branch(
    branch_id: UUID,
    service=Depends(get_service),
):
    """Delete a branch."""
    try:
        success = await service.delete_branch(branch_id)
        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"Branch {branch_id} not found or cannot be deleted",
            )
        return {"success": True}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to delete branch: {exc}"
        ) from exc


# ── Merge Routes ───────────────────────────────────────────────


@router.post("/merge", response_model=BranchMergeResponse)
async def merge_branches(
    request: BranchMergeRequest,
    service=Depends(get_service),
    executed_by: str = Query(default="api", description="Executor identifier"),
):
    """Merge source branch into target branch."""
    try:
        merge = await service.merge_branches(
            source_branch_id=request.source_branch_id,
            target_branch_id=request.target_branch_id,
            strategy=request.strategy,
            message=request.message,
            description=request.description,
            executed_by=executed_by,
        )
        return BranchMergeResponse(merge=merge)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to merge branches: {exc}"
        ) from exc


@router.get(
    "/compare/{source_branch_id}/{target_branch_id}",
    response_model=BranchComparisonResponse,
)
async def compare_branches(
    source_branch_id: UUID,
    target_branch_id: UUID,
    service=Depends(get_service),
):
    """Compare two branches."""
    try:
        comparison = await service.compare_branches(source_branch_id, target_branch_id)
        return BranchComparisonResponse(comparison=comparison)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to compare branches: {exc}"
        ) from exc


# ── Policy Routes ──────────────────────────────────────────────


@router.get("/policy", response_model=BranchPolicyResponse)
async def get_branch_policy(
    service=Depends(get_service),
):
    """Get branch policy."""
    try:
        policy = service.get_policy()
        return BranchPolicyResponse(policy=policy)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to get policy: {exc}"
        ) from exc


@router.put("/policy", response_model=BranchPolicyResponse)
async def update_branch_policy(
    request: BranchPolicyUpdateRequest,
    service=Depends(get_service),
):
    """Update branch policy."""
    try:
        policy = service.update_policy(
            name_pattern=request.name_pattern,
            require_issue_reference=request.require_issue_reference,
            allow_anyone_create=request.allow_anyone_create,
            protected_branches=request.protected_branches,
            require_review_for_protected=request.require_review_for_protected,
            required_reviewers=request.required_reviewers,
            allowed_strategies=request.allowed_strategies,
            default_strategy=request.default_strategy,
            auto_delete_merged=request.auto_delete_merged,
            max_branch_age_days=request.max_branch_age_days,
            max_branches_per_user=request.max_branches_per_user,
        )
        return BranchPolicyResponse(policy=policy)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to update policy: {exc}"
        ) from exc
