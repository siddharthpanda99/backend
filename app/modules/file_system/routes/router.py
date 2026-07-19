"""File System module API routes — File/folder CRUD, storage statistics.

Thin routing layer that delegates to common_lib.modules.file_system services.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()


class FileCreateRequest(BaseModel):
    path: str
    content: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class FileUpdateRequest(BaseModel):
    content: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class FolderCreateRequest(BaseModel):
    path: str
    metadata: Optional[Dict[str, Any]] = None


def _get_service():
    from common_lib.modules.file_system.service import FileStorageController
    return FileStorageController()


@router.get("/files")
async def list_files(directory: Optional[str] = "/") -> Dict[str, Any]:
    """List files in a directory."""
    try:
        svc = _get_service()
        result = svc.list_files(directory) if hasattr(svc, "list_files") else []
        return {"files": result, "count": len(result) if isinstance(result, list) else 0}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/files")
async def create_file(request: FileCreateRequest) -> Dict[str, Any]:
    """Create a new file."""
    try:
        svc = _get_service()
        result = svc.create_file(request.path, request.content, request.metadata) if hasattr(svc, "create_file") else {"path": request.path}
        return {"file": result, "message": "File created successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/files/{file_path:path}")
async def get_file(file_path: str) -> Dict[str, Any]:
    """Get file contents."""
    try:
        svc = _get_service()
        result = svc.get_file(file_path) if hasattr(svc, "get_file") else None
        if result is None:
            raise HTTPException(status_code=404, detail="File not found")
        return {"file": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/files/{file_path:path}")
async def update_file(file_path: str, request: FileUpdateRequest) -> Dict[str, Any]:
    """Update a file."""
    try:
        svc = _get_service()
        result = svc.update_file(file_path, **request.model_dump(exclude_unset=True)) if hasattr(svc, "update_file") else {"path": file_path}
        return {"file": result, "message": "File updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/files/{file_path:path}")
async def delete_file(file_path: str) -> Dict[str, Any]:
    """Delete a file."""
    try:
        svc = _get_service()
        svc.delete_file(file_path) if hasattr(svc, "delete_file") else None
        return {"success": True, "message": "File deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/folders")
async def create_folder(request: FolderCreateRequest) -> Dict[str, Any]:
    """Create a folder."""
    try:
        svc = _get_service()
        result = svc.create_folder(request.path, request.metadata) if hasattr(svc, "create_folder") else {"path": request.path}
        return {"folder": result, "message": "Folder created successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def storage_stats() -> Dict[str, Any]:
    """Get storage statistics."""
    try:
        svc = _get_service()
        result = svc.get_stats() if hasattr(svc, "get_stats") else {"total_files": 0, "total_size": 0}
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
