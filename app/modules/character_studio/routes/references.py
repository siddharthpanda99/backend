"""Reference asset routes."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException

from common_lib.modules.common.feature_flags import is_enabled
from app.modules.character_studio.routes.models import (
    AssetRead,
    ListResponse,
    ReferenceCreateBody,
    ApproveBody,
    RejectBody,
    EvaluateResponseContract,
    AuditEventRead,
)
from common_lib.modules.image_processing.character_studio.schemas import EvaluationRead

router = APIRouter()

API = "/api/v1/character-studio"


def _guard() -> None:
    from common_lib.modules.common.feature_flags import is_enabled

    if not is_enabled("character_studio"):
        raise HTTPException(status_code=403, detail="character_studio module disabled")


def _call(fn_name: str, *args: Any, **kwargs: Any) -> Any:
    from common_lib.modules.image_processing.character_studio.operations import (
        list_references,
        add_reference,
        approve_reference,
        archive_reference,
        evaluate_asset,
        list_evaluations,
        approve_asset,
        reject_asset,
    )
    from common_lib.modules.image_processing.character_studio import audit as _audit

    if fn_name == "list_audit_events":
        return _audit.list_audit_events(*args, **kwargs)

    return getattr(
        __import__(
            "common_lib.modules.image_processing.character_studio.operations",
            fromlist=[""],
        ),
        fn_name,
    )(*args, **kwargs)


@router.get(
    "/characters/{character_id}/references",
    response_model=ListResponse[AssetRead],
)
async def list_references(
    character_id: str,
    category: Optional[str] = None,
    approved_only: bool = False,
) -> ListResponse[AssetRead]:
    """List reference assets for a character."""
    items, total = _call(
        "list_references", character_id, category=category, approved_only=approved_only
    )
    return ListResponse[AssetRead](items=list(items), total=total)


@router.post(
    "/characters/{character_id}/references", response_model=AssetRead, status_code=201
)
async def add_reference(character_id: str, body: ReferenceCreateBody) -> AssetRead:
    """Register a reference asset (typically one produced by generation)."""
    return _call(
        "add_reference",
        character_id,
        asset_id_str=body.asset_id_str,
        category=body.category,
        subcategory=body.subcategory,
        width=body.width,
        height=body.height,
        file_size=body.file_size,
        format=body.format,
        quality_score=body.quality_score,
        file_path=body.file_path,
    )


@router.post("/references/{asset_id}/approve", response_model=AssetRead)
async def approve_reference(asset_id: UUID, body: ApproveBody) -> AssetRead:
    """Approve a reference asset."""
    return _call("approve_reference", asset_id, approved_by=body.approved_by)


@router.post("/references/{asset_id}/archive", response_model=AssetRead)
async def archive_reference(asset_id: UUID, body: RejectBody) -> AssetRead:
    """Archive a reference asset."""
    return _call("archive_reference", asset_id, reason=body.reason)


@router.post("/assets/{asset_id}/evaluate", response_model=EvaluateResponseContract)
async def evaluate_asset_endpoint(
    asset_id: UUID,
    reference_asset_id: Optional[UUID] = None,
) -> EvaluateResponseContract:
    """Evaluate an asset's identity consistency against its reference.

    If reference_asset_id is not provided, the system will use:
    1. The DNA identity_lock_source if configured
    2. The deterministic reference selector (approved front face)
    """
    return _call("evaluate_asset", asset_id, reference_asset_id=reference_asset_id)


@router.get(
    "/assets/{asset_id}/evaluations", response_model=ListResponse[EvaluationRead]
)
async def list_evaluations(asset_id: UUID) -> ListResponse[EvaluationRead]:
    """List evaluations for an asset."""
    items = _call("list_evaluations", asset_id)
    return ListResponse[EvaluationRead](items=list(items), total=len(items))


@router.post("/assets/{asset_id}/approve", response_model=AssetRead)
async def approve_asset(asset_id: UUID, body: ApproveBody) -> AssetRead:
    """Approve an asset after evaluation."""
    return _call("approve_asset", asset_id, approved_by=body.approved_by)


@router.post("/assets/{asset_id}/reject", response_model=AssetRead)
async def reject_asset(asset_id: UUID, body: RejectBody) -> AssetRead:
    """Reject an asset after evaluation."""
    return _call("reject_asset", asset_id, reason=body.reason)


@router.get(
    "/characters/{character_id}/audit-events",
    response_model=ListResponse[AuditEventRead],
)
async def list_audit_events_endpoint(
    character_id: str,
    action: Optional[str] = None,
    actor: Optional[str] = None,
    limit: int = 100,
) -> ListResponse[AuditEventRead]:
    """List approval audit events for a character."""
    _guard()
    items = _call(
        "list_audit_events",
        character_id=character_id,
        action=action,
        actor=actor,
        limit=limit,
    )
    return ListResponse[AuditEventRead](
        items=[AuditEventRead.model_validate(item) for item in items],
        total=len(items),
    )
