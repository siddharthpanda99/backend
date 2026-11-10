"""Harness Registry Routes.

Thin transport layer for harness and version management.
"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from common_lib.modules.harness_optimization.service import (
    get_harness_optimization_service,
)
from common_lib.modules.harness_optimization.flags import is_hos_enabled
from common_lib.modules.harness_optimization.exceptions import FeatureDisabledError

from app.modules.harness_optimization.routes.schemas import (
    HarnessCreate,
    HarnessUpdate,
    HarnessRead,
    HarnessVersionCreate,
    HarnessVersionRead,
    HarnessVersionApprove,
)

router = APIRouter(prefix="/harnesses", tags=["Harnesses"])


def _get_service():
    """Get HOS service instance."""
    if not is_hos_enabled():
        raise FeatureDisabledError(
            "Harness Optimization Service is disabled",
            flag_name="HARNESS_OPTIMIZATION_ENABLED",
        )
    return get_harness_optimization_service()


# ═══════════════════════════════════════════════════════════════════
# Harnesses
# ═══════════════════════════════════════════════════════════════════


@router.post(
    "/",
    response_model=HarnessRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new harness family",
)
def create_harness(payload: HarnessCreate, service=Depends(_get_service)):
    """Create a new harness family for optimization."""
    harness = service.create_harness(
        tenant_id=payload.tenant_id,
        name=payload.name,
        description=payload.description,
        domain=payload.domain,
        owner_id=payload.owner_id,
        visibility=payload.visibility,
    )
    return HarnessRead.model_validate(harness)


@router.get(
    "/",
    response_model=List[HarnessRead],
    summary="List accessible harnesses",
)
def list_harnesses(
    tenant_id: Optional[str] = Query(None, description="Filter by tenant"),
    domain: Optional[str] = Query(None, description="Filter by domain"),
    owner_id: Optional[str] = Query(None, description="Filter by owner"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    service=Depends(_get_service),
):
    """List harnesses with optional filters."""
    harnesses, total = service.list_harnesses(
        tenant_id=tenant_id,
        domain=domain,
        owner_id=owner_id,
        page=page,
        page_size=page_size,
    )
    return [HarnessRead.model_validate(h) for h in harnesses]


@router.get(
    "/{harness_id}",
    response_model=HarnessRead,
    summary="Get harness by ID",
)
def get_harness(harness_id: UUID, service=Depends(_get_service)):
    """Get harness metadata and approved version."""
    harness = service.get_harness(harness_id)
    return HarnessRead.model_validate(harness)


@router.patch(
    "/{harness_id}",
    response_model=HarnessRead,
    summary="Update harness metadata",
)
def update_harness(
    harness_id: UUID,
    payload: HarnessUpdate,
    service=Depends(_get_service),
):
    """Update harness metadata (name, description, domain, visibility)."""
    # Note: service doesn't have update_harness yet, would need to add
    from common_lib.modules.harness_optimization.exceptions import HOSError

    raise HOSError("Not implemented yet")


# ═══════════════════════════════════════════════════════════════════
# Harness Versions
# ═══════════════════════════════════════════════════════════════════


@router.post(
    "/{harness_id}/versions",
    response_model=HarnessVersionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new harness version (draft)",
)
def create_harness_version(
    harness_id: UUID,
    payload: HarnessVersionCreate,
    service=Depends(_get_service),
):
    """Create a new immutable harness version."""
    if payload.harness_id != harness_id:
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail="harness_id mismatch")
    version = service.create_harness_version(
        harness_id=harness_id,
        version=payload.version,
        component_manifest_json=payload.component_manifest_json,
        created_by=payload.created_by,
        parent_version_id=payload.parent_version_id,
        policy_bundle_id=payload.policy_bundle_id,
        policy_bundle_version=payload.policy_bundle_version,
        model_profile_id=payload.model_profile_id,
        pinned_model_ids=payload.pinned_model_ids,
        tool_catalog_snapshot_id=payload.tool_catalog_snapshot_id,
        skill_snapshot_ids=payload.skill_snapshot_ids,
        memory_policy_version=payload.memory_policy_version,
    )
    return HarnessVersionRead.model_validate(version)


@router.get(
    "/{harness_id}/versions/{version_id}",
    response_model=HarnessVersionRead,
    summary="Get harness version by ID",
)
def get_harness_version(
    harness_id: UUID, version_id: UUID, service=Depends(_get_service)
):
    """Get harness version details."""
    version = service.get_harness_version(version_id)
    if version.harness_id != harness_id:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=404, detail="Version not found for this harness"
        )
    return HarnessVersionRead.model_validate(version)


@router.post(
    "/{harness_id}/versions/{version_id}/validate",
    response_model=dict,
    summary="Validate harness version schema and policy compatibility",
)
def validate_harness_version(
    harness_id: UUID, version_id: UUID, service=Depends(_get_service)
):
    """Validate harness version schema and policy compatibility."""
    # TODO: implement validation logic
    return {"valid": True, "errors": []}


@router.post(
    "/{harness_id}/versions/{version_id}/promote",
    response_model=HarnessVersionRead,
    summary="Approve a harness version",
)
def promote_harness_version(
    harness_id: UUID,
    version_id: UUID,
    payload: HarnessVersionApprove,
    service=Depends(_get_service),
):
    """Approve a harness version and set as current approved."""
    version = service.approve_harness_version(version_id, payload.approver_id)
    if version.harness_id != harness_id:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=404, detail="Version not found for this harness"
        )
    return HarnessVersionRead.model_validate(version)


# ════════════════════════════════════════════════════════════════════
# Rollback
# ═══════════════════════════════════════════════════════════════════


@router.post(
    "/{harness_id}/rollback",
    response_model=dict,
    summary="Rollback harness to a previous version",
)
def rollback_harness(
    harness_id: UUID,
    target_version_id: UUID,
    requester_id: str,
    service=Depends(_get_service),
):
    """Rollback harness to a previous version."""
    version = service.rollback_harness(harness_id, target_version_id, requester_id)
    return {
        "harness_id": str(harness_id),
        "target_version_id": str(target_version_id),
        "version": version.version,
    }


__all__ = ["router"]
