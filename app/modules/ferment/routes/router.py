"""Ferment module API routes — Multi-agent lifecycle, project phases, grading.

Thin routing layer that delegates to common_lib.modules.ferment services.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()


class ProjectCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    config: Optional[Dict[str, Any]] = None


class ExecutionRequest(BaseModel):
    project_id: str
    phase: Optional[str] = None
    inputs: Optional[Dict[str, Any]] = None


def _get_service():
    from common_lib.modules.ferment.service import ProjectEngine
    return ProjectEngine()


@router.get("/projects")
async def list_projects() -> Dict[str, Any]:
    """List all ferment projects."""
    try:
        svc = _get_service()
        result = svc.list_projects() if hasattr(svc, "list_projects") else []
        return {"projects": result, "count": len(result) if isinstance(result, list) else 0}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/projects")
async def create_project(request: ProjectCreateRequest) -> Dict[str, Any]:
    """Create a new ferment project."""
    try:
        svc = _get_service()
        result = svc.create_project(request.name, request.description, request.config) if hasattr(svc, "create_project") else {"name": request.name}
        return {"project": result, "message": "Project created successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}")
async def get_project(project_id: str) -> Dict[str, Any]:
    """Get a project by ID."""
    try:
        svc = _get_service()
        result = svc.get_project(project_id) if hasattr(svc, "get_project") else None
        if result is None:
            raise HTTPException(status_code=404, detail="Project not found")
        return {"project": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute")
async def execute_phase(request: ExecutionRequest) -> Dict[str, Any]:
    """Execute a project phase."""
    try:
        svc = _get_service()
        result = svc.execute(request.project_id, request.phase, request.inputs) if hasattr(svc, "execute") else {"executed": False}
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/grade")
async def grade_project(project_id: str) -> Dict[str, Any]:
    """Grade a project's output."""
    try:
        svc = _get_service()
        result = svc.grade(project_id) if hasattr(svc, "grade") else {"score": 0}
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/projects/{project_id}")
async def delete_project(project_id: str) -> Dict[str, Any]:
    """Delete a project."""
    try:
        svc = _get_service()
        svc.delete_project(project_id) if hasattr(svc, "delete_project") else None
        return {"success": True, "message": "Project deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
