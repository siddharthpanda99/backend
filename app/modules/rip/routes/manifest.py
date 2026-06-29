"""RIP Manifest routes — Save, load, list, delete RIP configuration packets.

Enables the RIP Builder UI to persist configuration manifests
that can be exported and applied to any module.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from common_lib.modules.rip.rip_manifest import (
    ManifestMeta,
    ManifestSaveRequest,
    ManifestListResponse,
    ManifestDetailResponse,
    ManifestDeleteResponse,
    validate_id,
    save_manifest,
    list_manifests,
    get_manifest,
    delete_manifest,
)

router = APIRouter(prefix="/rip/manifest", tags=["RIP — Manifest"])


@router.post("/save", response_model=ManifestMeta)
async def save_manifest_endpoint(payload: ManifestSaveRequest):
    """Save a RIP manifest to persistent storage."""
    try:
        return save_manifest(payload.manifest, payload.overwrite)
    except FileExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/list", response_model=ManifestListResponse)
async def list_manifests_endpoint(status: Optional[str] = None):
    """List all saved RIP manifests with metadata."""
    return list_manifests(status)


@router.get("/get/{manifest_id}", response_model=ManifestDetailResponse)
async def get_manifest_endpoint(manifest_id: str):
    """Load a full RIP manifest by ID."""
    result = get_manifest(manifest_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Manifest {manifest_id} not found")
    return ManifestDetailResponse(id=manifest_id, manifest=result)


@router.delete("/delete/{manifest_id}", response_model=ManifestDeleteResponse)
async def delete_manifest_endpoint(manifest_id: str):
    """Delete a saved RIP manifest."""
    success = delete_manifest(manifest_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Manifest {manifest_id} not found")
    return ManifestDeleteResponse(
        success=True, message=f"Manifest {manifest_id} deleted"
    )
