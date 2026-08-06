"""Ferment module API routes — Multi-agent lifecycle, project phases, grading.

Thin routing layer that delegates to common_lib.modules.ferment.service.ProjectEngine.

Goal Mode (flag-gated): when ``GOAL_MODE`` is enabled, POST /ferment/goal turns a
natural-language goal into a ferment project via the ScopingLoop, and
GET /ferment/projects/{project_id}/status returns the goal-status progress payload.
When the flag is off, those endpoints respond 403 with a descriptive message.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter()


class GoalRequest(BaseModel):
    goal: str = Field(
        ...,
        description="Top-level goal description (e.g. 'Build a REST API for a todo app')",
    )
    name: Optional[str] = Field(None, description="Optional project name override")
    config: Optional[Dict[str, Any]] = Field(
        None, description="Scoping overrides: continuation, auto_approve, context_hint"
    )


class ProjectCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    config: Optional[Dict[str, Any]] = None


class ExecutionRequest(BaseModel):
    project_id: str
    phase: Optional[str] = None
    inputs: Optional[Dict[str, Any]] = None


def _goal_mode_enabled() -> bool:
    from app.core.settings import get_settings

    return get_settings().GOAL_MODE


def _require_goal_mode() -> None:
    if not _goal_mode_enabled():
        raise HTTPException(
            status_code=403,
            detail=(
                "Goal Mode is disabled. Set GOAL_MODE=true (config.ini [Backend] "
                "goal_mode) to enable /ferment/goal."
            ),
        )


def _get_service():
    from common_lib.modules.ferment.service import ProjectEngine

    return ProjectEngine()


@router.get("/projects")
async def list_projects() -> Dict[str, Any]:
    """List all ferment projects."""
    try:
        svc = _get_service()
        result = svc.list_projects()
        return {"projects": result, "count": len(result)}
    except Exception as e:
        logger.exception("Failed to list ferment projects")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/projects")
async def create_project(request: ProjectCreateRequest) -> Dict[str, Any]:
    """Create a new ferment project from a name + description."""
    try:
        svc = _get_service()
        goal = request.description or f"Build {request.name}"
        result = svc.create_project_from_goal(
            goal=goal, name=request.name, config=request.config
        )
        return {"project": result, "message": "Project created successfully"}
    except Exception as e:
        logger.exception("Failed to create ferment project")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/goal")
async def create_project_from_goal(request: GoalRequest) -> Dict[str, Any]:
    """Goal Mode — turn a natural-language goal into a ferment project.

    Runs the ScopingLoop (orient → plan → approve, headless auto-approve by
    default) and persists the resulting phased step plan. Gated on GOAL_MODE.
    """
    _require_goal_mode()
    try:
        svc = _get_service()
        result = svc.create_project_from_goal(
            goal=request.goal, name=request.name, config=request.config
        )
        return {"project": result, "message": "Goal project created successfully"}
    except Exception as e:
        logger.exception("Failed to create project from goal")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}")
async def get_project(project_id: str) -> Dict[str, Any]:
    """Get a project by ID or name."""
    try:
        svc = _get_service()
        result = svc.get_project(project_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Project not found")
        return {"project": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get ferment project")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/status")
async def project_status(project_id: str) -> Dict[str, Any]:
    """Goal Mode — goal-status progress payload for a project.

    Returns overall status, completion boolean, progress string, step counts,
    and per-phase/per-step progress with grades. Gated on GOAL_MODE.
    """
    _require_goal_mode()
    try:
        svc = _get_service()
        result = svc.goal_status(project_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Project not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to compute goal status")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute")
async def execute_phase(request: ExecutionRequest) -> Dict[str, Any]:
    """Execute a project (role-driven ferment graph, FermentExecutor fallback)."""
    try:
        svc = _get_service()
        result = svc.execute_project(
            request.project_id, phase=request.phase, inputs=request.inputs
        )
        return {"result": result}
    except Exception as e:
        logger.exception("Failed to execute ferment project")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/grade")
async def grade_project(project_id: str) -> Dict[str, Any]:
    """Grade a project's completed steps and phases (A–F with rubric scores)."""
    try:
        svc = _get_service()
        result = svc.grade_project(project_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Project not found")
        return {"result": result}
    except Exception as e:
        logger.exception("Failed to grade ferment project")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/projects/{project_id}")
async def delete_project(project_id: str) -> Dict[str, Any]:
    """Delete a project."""
    try:
        svc = _get_service()
        deleted = svc.delete_project(project_id)
        return {"success": deleted, "message": "Project deleted successfully"}
    except Exception as e:
        logger.exception("Failed to delete ferment project")
        raise HTTPException(status_code=500, detail=str(e))
