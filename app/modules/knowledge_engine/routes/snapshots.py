"""
Knowledge Engine — Snapshot Routes.

Thin transport for snapshot operations.
Delegates to common_lib.modules.knowledge_engine.services.snapshot_service.SnapshotService
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from common_lib.modules.knowledge_engine.models.snapshot import (
    KnowledgeSnapshot,
    SnapshotMetadata,
    SnapshotType,
    SnapshotStatus,
    SnapshotFormat,
    SnapshotSchedule,
    SnapshotRestore,
    SnapshotDiff,
)
from common_lib.modules.knowledge_engine.services.snapshot_service import (
    get_snapshot_service,
)

router = APIRouter(prefix="/snapshots", tags=["Knowledge Engine — Snapshots"])


# ── Request/Response Models ────────────────────────────────────


class SnapshotCreateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    snapshot_type: SnapshotType = SnapshotType.FULL
    scope: str = "full"
    entity_ids: list[UUID] = Field(default_factory=list)
    claim_ids: list[str] = Field(default_factory=list)
    relationship_ids: list[UUID] = Field(default_factory=list)
    branch_id: UUID | None = None
    tag: str | None = None
    filters: dict[str, Any] = Field(default_factory=dict)
    format: SnapshotFormat = SnapshotFormat.JSON
    compress: bool = False
    retention_days: int = 90
    is_permanent: bool = False
    tags: list[str] = Field(default_factory=list)
    labels: dict[str, str] = Field(default_factory=dict)


class SnapshotResponse(BaseModel):
    snapshot: KnowledgeSnapshot


class SnapshotListResponse(BaseModel):
    snapshots: list[KnowledgeSnapshot]
    total: int


class SnapshotRestoreRequest(BaseModel):
    target_branch_id: UUID | None = None
    create_new_branch: bool = False
    new_branch_name: str | None = None
    entity_ids: list[UUID] = Field(default_factory=list)
    claim_ids: list[str] = Field(default_factory=list)
    relationship_ids: list[UUID] = Field(default_factory=list)
    restore_all: bool = True
    conflict_strategy: str = "skip"


class SnapshotRestoreResponse(BaseModel):
    restore: SnapshotRestore


class SnapshotDiffResponse(BaseModel):
    diff: SnapshotDiff


class SnapshotScheduleCreateRequest(BaseModel):
    name: str
    cron_expression: str
    description: str | None = None
    timezone: str = "UTC"
    snapshot_type: SnapshotType = SnapshotType.INCREMENTAL
    scope: str = "full"
    filters: dict[str, Any] = Field(default_factory=dict)
    format: SnapshotFormat = SnapshotFormat.JSON
    compress: bool = True
    retention_days: int = 30
    max_snapshots: int = 100
    owner_id: str | None = None


class SnapshotScheduleResponse(BaseModel):
    schedule: SnapshotSchedule


# ── Dependency Injection ────────────────────────────────────────


def get_service() -> Any:
    """Get snapshot service instance."""
    return get_snapshot_service()


# ── Routes ─────────────────────────────────────────────────────


@router.post("", response_model=SnapshotResponse, status_code=201)
async def create_snapshot(
    request: SnapshotCreateRequest,
    service=Depends(get_service),
    created_by: str = Query(default="api", description="Creator identifier"),
):
    """Create a new knowledge snapshot."""
    try:
        snapshot = await service.create_snapshot(
            name=request.name,
            description=request.description,
            snapshot_type=request.snapshot_type,
            scope=request.scope,
            entity_ids=request.entity_ids,
            claim_ids=request.claim_ids,
            relationship_ids=request.relationship_ids,
            branch_id=request.branch_id,
            tag=request.tag,
            filters=request.filters,
            format=request.format,
            compress=request.compress,
            retention_days=request.retention_days,
            is_permanent=request.is_permanent,
            tags=request.tags,
            labels=request.labels,
            created_by=created_by,
        )
        return SnapshotResponse(snapshot=snapshot)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to create snapshot: {exc}"
        ) from exc


@router.get("/{snapshot_id}", response_model=SnapshotResponse)
async def get_snapshot(
    snapshot_id: UUID,
    service=Depends(get_service),
):
    """Get a snapshot by ID."""
    try:
        snapshot = await service.get_snapshot(snapshot_id)
        if not snapshot:
            raise HTTPException(
                status_code=404, detail=f"Snapshot {snapshot_id} not found"
            )
        return SnapshotResponse(snapshot=snapshot)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to get snapshot: {exc}"
        ) from exc


@router.get("", response_model=SnapshotListResponse)
async def list_snapshots(
    status: SnapshotStatus | None = Query(None, description="Filter by status"),
    snapshot_type: SnapshotType | None = Query(None, description="Filter by type"),
    branch_id: UUID | None = Query(None, description="Filter by branch"),
    tag: str | None = Query(None, description="Filter by tag"),
    created_by: str | None = Query(None, description="Filter by creator"),
    limit: int = Query(100, ge=1, le=1000, description="Max results"),
    offset: int = Query(0, ge=0, description="Offset"),
    service=Depends(get_service),
):
    """List snapshots with filtering."""
    try:
        result = await service.list_snapshots(
            status=status,
            snapshot_type=snapshot_type,
            branch_id=branch_id,
            tag=tag,
            created_by=created_by,
            limit=limit,
            offset=offset,
        )
        return SnapshotListResponse(**result)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to list snapshots: {exc}"
        ) from exc


@router.delete("/{snapshot_id}")
async def delete_snapshot(
    snapshot_id: UUID,
    service=Depends(get_service),
):
    """Delete a snapshot."""
    try:
        success = await service.delete_snapshot(snapshot_id)
        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"Snapshot {snapshot_id} not found or is permanent",
            )
        return {"success": True}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to delete snapshot: {exc}"
        ) from exc


# ── Restore Routes ─────────────────────────────────────────────


@router.post("/{snapshot_id}/restore", response_model=SnapshotRestoreResponse)
async def restore_snapshot(
    snapshot_id: UUID,
    request: SnapshotRestoreRequest,
    service=Depends(get_service),
    executed_by: str = Query(default="api", description="Executor identifier"),
):
    """Restore from a snapshot."""
    try:
        restore = await service.restore_snapshot(
            snapshot_id=snapshot_id,
            target_branch_id=request.target_branch_id,
            create_new_branch=request.create_new_branch,
            new_branch_name=request.new_branch_name,
            entity_ids=request.entity_ids,
            claim_ids=request.claim_ids,
            relationship_ids=request.relationship_ids,
            restore_all=request.restore_all,
            conflict_strategy=request.conflict_strategy,
            executed_by=executed_by,
        )
        return SnapshotRestoreResponse(restore=restore)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to restore snapshot: {exc}"
        ) from exc


@router.get(
    "/diff/{base_snapshot_id}/{target_snapshot_id}", response_model=SnapshotDiffResponse
)
async def diff_snapshots(
    base_snapshot_id: UUID,
    target_snapshot_id: UUID,
    service=Depends(get_service),
):
    """Diff two snapshots."""
    try:
        diff = await service.diff_snapshots(base_snapshot_id, target_snapshot_id)
        return SnapshotDiffResponse(diff=diff)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to diff snapshots: {exc}"
        ) from exc


# ── Schedule Routes ────────────────────────────────────────────


@router.post("/schedules", response_model=SnapshotScheduleResponse, status_code=201)
async def create_schedule(
    request: SnapshotScheduleCreateRequest,
    service=Depends(get_service),
):
    """Create a snapshot schedule."""
    try:
        schedule = await service.create_schedule(
            name=request.name,
            cron_expression=request.cron_expression,
            description=request.description,
            timezone=request.timezone,
            snapshot_type=request.snapshot_type,
            scope=request.scope,
            filters=request.filters,
            format=request.format,
            compress=request.compress,
            retention_days=request.retention_days,
            max_snapshots=request.max_snapshots,
            owner_id=request.owner_id,
        )
        return SnapshotScheduleResponse(schedule=schedule)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to create schedule: {exc}"
        ) from exc


@router.get("/schedules", response_model=list[SnapshotScheduleResponse])
async def list_schedules(
    enabled: bool | None = Query(None, description="Filter by enabled"),
    service=Depends(get_service),
):
    """List snapshot schedules."""
    try:
        schedules = await service.list_schedules(enabled=enabled)
        return [SnapshotScheduleResponse(schedule=s) for s in schedules]
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to list schedules: {exc}"
        ) from exc


@router.delete("/schedules/{schedule_id}")
async def delete_schedule(
    schedule_id: UUID,
    service=Depends(get_service),
):
    """Delete a snapshot schedule."""
    try:
        success = await service.delete_schedule(schedule_id)
        if not success:
            raise HTTPException(
                status_code=404, detail=f"Schedule {schedule_id} not found"
            )
        return {"success": True}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to delete schedule: {exc}"
        ) from exc
