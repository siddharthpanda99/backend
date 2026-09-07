"""Plugin Server routes — hot-loadable extensions (ComfyUI, git, pip, local_dir)."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response, status

from common_lib.modules.extensions.models import (
    ExtensionCreate,
    ExtensionUpdate,
)
from common_lib.modules.extensions import get_extension_registry

logger = logging.getLogger(__name__)
router = APIRouter()


def _reg():
    return get_extension_registry()


@router.get("")
async def list_extensions(
    status_filter: str | None = None,
) -> dict[str, Any]:
    """List registered extensions."""
    from common_lib.modules.extensions.models import ExtensionStatus

    reg = _reg()
    all_exts = reg.list()
    if status_filter is not None:
        try:
            sf = ExtensionStatus(status_filter)
            all_exts = [e for e in all_exts if e.status == sf]
        except ValueError:
            pass  # ignore unknown status
    return {
        "extensions": [
            {
                "id": e.id,
                "name": e.name,
                "version": e.version,
                "extension_type": e.extension_type.value
                if hasattr(e.extension_type, "value")
                else str(e.extension_type),
                "status": e.status.value
                if hasattr(e.status, "value")
                else str(e.status),
                "source_url": e.source_url,
                "author": e.author,
            }
            for e in all_exts
        ]
    }


@router.get("/{extension_id}")
async def get_extension(extension_id: str) -> dict[str, Any]:
    """Get a single extension by ID."""
    ext = _reg().get(extension_id)
    if ext is None:
        raise HTTPException(
            status_code=404, detail=f"Extension '{extension_id}' not found"
        )
    return {
        "id": ext.id,
        "name": ext.name,
        "version": ext.version,
        "extension_type": ext.extension_type.value
        if hasattr(ext.extension_type, "value")
        else str(ext.extension_type),
        "status": ext.status.value if hasattr(ext.status, "value") else str(ext.status),
        "source_url": ext.source_url,
        "source_path": ext.source_path,
        "author": ext.author,
        "tags": ext.tags,
        "nodes": [
            {"name": n.name, "description": n.description, "category": n.category}
            for n in ext.nodes
        ],
    }


@router.post("")
async def register_extension(body: dict) -> dict[str, Any]:
    """Register a new extension."""
    from common_lib.modules.extensions.models import Extension, ExtensionType
    from common_lib.modules.plugin_sdk.manifest import ExtensionManifest

    try:
        manifest = ExtensionManifest(**body)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid manifest: {e}")

    try:
        ext_type = ExtensionType(manifest.extension_type)
    except ValueError:
        ext_type = ExtensionType.PYTHON_PACKAGE

    ext = Extension(
        id=manifest.id,
        name=manifest.name,
        version=manifest.version,
        extension_type=ext_type,
        source_url=manifest.source_url,
        source_path=manifest.source_path,
        source_branch=manifest.source_branch,
        author=manifest.author or "",
        tags=manifest.tags,
        config=manifest.config,
    )
    result = _reg().register(ext)
    return {"success": True, "id": result.id}


@router.post("/{extension_id}/load")
async def load_extension(extension_id: str, response: Response) -> dict[str, Any]:
    """Load an extension into memory."""
    result = _reg().load(extension_id)
    if not result:
        # Result is ExtensionLoadResult; check .success
        if hasattr(result, "success") and not result.success:
            response.status_code = status.HTTP_400_BAD_REQUEST
            return {
                "success": False,
                "error": getattr(result, "message", "load failed"),
            }
    return {"success": True, "extension_id": extension_id}


@router.post("/{extension_id}/unload")
async def unload_extension(extension_id: str) -> dict[str, Any]:
    """Unload an extension from memory."""
    ok = _reg().unload(extension_id)
    return {"success": ok, "extension_id": extension_id}


@router.post("/{extension_id}/reload")
async def reload_extension(extension_id: str) -> dict[str, Any]:
    """Reload an extension (unload + load)."""
    _reg().unload(extension_id)
    ok = _reg().load(extension_id)
    return {"success": bool(ok), "extension_id": extension_id}


@router.post("/{extension_id}/sync")
async def sync_extension(extension_id: str) -> dict[str, Any]:
    """Sync an extension from its source (git pull, etc.)."""
    result = _reg().sync_from_source(extension_id)
    if hasattr(result, "success"):
        if not result.success:
            raise HTTPException(
                status_code=400,
                detail=getattr(result, "message", "sync failed"),
            )
        return {
            "success": True,
            "extension_id": extension_id,
            "new_commit": getattr(result, "new_commit", None),
        }
    return {"success": True, "extension_id": extension_id}


@router.delete("/{extension_id}")
async def unregister_extension(extension_id: str) -> dict[str, Any]:
    """Unregister an extension entirely."""
    ok = _reg().unregister(extension_id)
    return {"success": ok, "extension_id": extension_id}
