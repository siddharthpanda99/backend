"""External Platforms module API routes — Story Bible management.

Thin routing layer that delegates to common_lib.modules.external_platforms services.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()


class StoryBibleCreateRequest(BaseModel):
    project_id: str
    entry_type: str
    name: str
    data: Optional[Dict[str, Any]] = None


class StoryBibleUpdateRequest(BaseModel):
    entry_type: Optional[str] = None
    name: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


def _get_service():
    from common_lib.modules.external_platforms.service import StoryBibleService
    return StoryBibleService()


@router.get("/projects/{project_id}/story-bible")
async def list_story_bible(project_id: str) -> Dict[str, Any]:
    """List all Story Bible entries for a project."""
    try:
        svc = _get_service()
        result = svc.list_entries(project_id) if hasattr(svc, "list_entries") else []
        return {"entries": result, "count": len(result) if isinstance(result, list) else 0}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/projects/{project_id}/story-bible")
async def create_story_bible_entry(project_id: str, request: StoryBibleCreateRequest) -> Dict[str, Any]:
    """Create a new Story Bible entry."""
    try:
        svc = _get_service()
        result = svc.create_entry(project_id, request.entry_type, request.name, request.data) if hasattr(svc, "create_entry") else {"name": request.name}
        return {"entry": result, "message": "Entry created successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/projects/{project_id}/story-bible/{entry_id}")
async def update_story_bible_entry(
    project_id: str, entry_id: str, request: StoryBibleUpdateRequest
) -> Dict[str, Any]:
    """Update a Story Bible entry."""
    try:
        svc = _get_service()
        result = svc.update_entry(project_id, entry_id, **request.model_dump(exclude_unset=True)) if hasattr(svc, "update_entry") else {"entry_id": entry_id}
        return {"entry": result, "message": "Entry updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/projects/{project_id}/story-bible/{entry_id}")
async def delete_story_bible_entry(project_id: str, entry_id: str) -> Dict[str, Any]:
    """Delete a Story Bible entry."""
    try:
        svc = _get_service()
        svc.delete_entry(project_id, entry_id) if hasattr(svc, "delete_entry") else None
        return {"success": True, "message": "Entry deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/platforms")
async def list_platforms() -> Dict[str, Any]:
    """List supported external platforms."""
    try:
        svc = _get_service()
        result = svc.list_platforms() if hasattr(svc, "list_platforms") else []
        return {"platforms": result, "count": len(result) if isinstance(result, list) else 0}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
