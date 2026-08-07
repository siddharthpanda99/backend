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


# ── Session-scoped Goal-Mode settings (Goal-Mode v2 toggle) ────────────────
# Lightweight in-process store keyed by session id. The frontend chat-settings
# toggle maps to these values; ProjectEngine.execute_project reads the
# per-session `goal_mode` flag through the `inputs`/params threading.
_SESSION_GOAL_MODE: Dict[str, Dict[str, Any]] = {}


def _session_settings(session_id: str) -> Dict[str, Any]:
    if session_id not in _SESSION_GOAL_MODE:
        _SESSION_GOAL_MODE[session_id] = {
            "goal_mode": _goal_mode_enabled(),
            "token_budget": None,
        }
    return _SESSION_GOAL_MODE[session_id]


class FermentSettingsRequest(BaseModel):
    session_id: str = Field(..., description="Agent session id for the toggle")
    goal_mode: Optional[bool] = Field(
        None, description="Goal-Mode toggle for this session (default OFF)"
    )
    token_budget: Optional[int] = Field(
        None, description="Optional per-goal token budget (guard inactive without it)"
    )


@router.get("/settings")
async def get_ferment_settings(session_id: str) -> Dict[str, Any]:
    """Return the session-scoped Goal-Mode settings (toggle + budget + threshold).

    Gated on GOAL_MODE so the toggle surface stays hidden when Goal Mode is off.
    """
    _require_goal_mode()
    settings = _session_settings(session_id)
    return {
        "session_id": session_id,
        "goal_mode": settings["goal_mode"],
        "token_budget": settings["token_budget"],
        "compact_trigger_fraction": getattr(
            _settings_or_none(), "COMPACT_TRIGGER_FRACTION", 0.6
        ),
    }


@router.post("/settings")
async def update_ferment_settings(request: FermentSettingsRequest) -> Dict[str, Any]:
    """Update the session-scoped Goal-Mode toggle and/or token budget."""
    _require_goal_mode()
    settings = _session_settings(request.session_id)
    if request.goal_mode is not None:
        settings["goal_mode"] = request.goal_mode
    if request.token_budget is not None:
        settings["token_budget"] = max(int(request.token_budget), 0)
    return {
        "session_id": request.session_id,
        "goal_mode": settings["goal_mode"],
        "token_budget": settings["token_budget"],
    }


def _settings_or_none():
    """Settings accessor that never raises on import issues."""
    try:
        from app.core.settings import get_settings

        return get_settings()
    except Exception:
        return None


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


# ── Goal-Mode v2: token budget + compaction endpoints ───────────────────────
# Path contract (GOAL_MODE_PLAN.md §9.4 / frontend goalMode/api.ts):
#   GET  /tokens/{project_id}                            → budget status
#   POST /tokens/{project_id}                            → ledger accumulation (internal)
#   POST /tokens/extension/{extension_id}/approve|reject → HITL decision
#   POST /tokens/{project_id}/compact                    → conversation compaction
# Extension ids are project-scoped (ext_001) and the frontend sends ONLY the
# extension id, so approve/reject resolve the owning project by scanning the
# persisted .ferment/ ledgers (see _resolve_project_by_extension).


class TokenBudgetRequest(BaseModel):
    project_id: str
    budget: Optional[int] = Field(
        None, description="Set/clear the per-goal token budget"
    )


class TokenUsageRequest(BaseModel):
    tokens: int = Field(..., description="Tokens consumed to accumulate (advisory)")


def _session_goal_mode_override(session_id: Optional[str]) -> Optional[bool]:
    """Map a session-scoped toggle (if any) to an explicit goal_mode override."""
    if session_id and session_id in _SESSION_GOAL_MODE:
        return _SESSION_GOAL_MODE[session_id]["goal_mode"]
    return None


def _resolve_project_by_extension(extension_id: str) -> Optional[str]:
    """Resolve the owning project id for a (project-scoped) extension id.

    Extension entries live on the persisted FermentProject JSON
    (``project.extensions``, e.g. ``ext_001``) and carry no project reference —
    the frontend sends only the extension id. Scan every project under
    ``.ferment/`` and return the id of the first project whose ``extensions``
    contains a matching entry id, else ``None``.
    """
    from common_lib.modules.ferment.persistence import (
        list_projects as _list_project_names,
        load_project as _load_project,
    )

    for name in _list_project_names():
        project = _load_project(name)
        if project is None:
            continue
        for entry in project.extensions or []:
            if entry.get("id") == extension_id:
                return project.id
    return None


@router.get("/tokens/{project_id}")
async def check_token_budget(
    project_id: str, session_id: Optional[str] = None
) -> Dict[str, Any]:
    """Goal-Mode v2 — return the token ledger status for a project."""
    _require_goal_mode()
    try:
        svc = _get_service()
        result = svc.check_token_budget(
            project_id, goal_mode=_session_goal_mode_override(session_id)
        )
        if result is None:
            raise HTTPException(status_code=404, detail="Project not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to check token budget")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tokens/{project_id}")
async def record_token_usage(
    project_id: str,
    request: TokenUsageRequest,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Goal-Mode v2 — accumulate token usage into the project ledger (internal)."""
    _require_goal_mode()
    try:
        svc = _get_service()
        result = svc.record_token_usage(
            project_id,
            request.tokens,
            goal_mode=_session_goal_mode_override(session_id),
        )
        if result is None:
            raise HTTPException(status_code=404, detail="Project not found")
        return result
    except Exception as e:
        logger.exception("Failed to record token usage")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tokens/extension/{extension_id}/approve")
async def approve_token_extension(
    extension_id: str,
    session_id: Optional[str] = None,
    approved_by: str = "human",
    extra_tokens: Optional[int] = None,
) -> Dict[str, Any]:
    """Goal-Mode v2 — approve a pending token-budget extension by id.

    The frontend sends only the extension id; the owning project is resolved
    by scanning the persisted ledgers (``_resolve_project_by_extension``).
    """
    _require_goal_mode()
    project_id = _resolve_project_by_extension(extension_id)
    if project_id is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Token extension '{extension_id}' was not found in any "
                "persisted ferment project"
            ),
        )
    try:
        svc = _get_service()
        result = svc.approve_token_extension(
            project_id,
            approved_by=approved_by,
            extra_tokens=extra_tokens,
            goal_mode=_session_goal_mode_override(session_id),
        )
        if result is None:
            raise HTTPException(status_code=404, detail="Project not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to approve token extension")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tokens/extension/{extension_id}/reject")
async def reject_token_extension(
    extension_id: str,
    session_id: Optional[str] = None,
    rejected_by: str = "human",
) -> Dict[str, Any]:
    """Goal-Mode v2 — reject (stop) a pending token-budget extension by id.

    The frontend sends only the extension id; the owning project is resolved
    by scanning the persisted ledgers (``_resolve_project_by_extension``).
    """
    _require_goal_mode()
    project_id = _resolve_project_by_extension(extension_id)
    if project_id is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Token extension '{extension_id}' was not found in any "
                "persisted ferment project"
            ),
        )
    try:
        svc = _get_service()
        result = svc.reject_token_extension(
            project_id,
            rejected_by=rejected_by,
            goal_mode=_session_goal_mode_override(session_id),
        )
        if result is None:
            raise HTTPException(status_code=404, detail="Project not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to reject token extension")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tokens/{project_id}/compact")
async def compact_project_session(
    project_id: str,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Goal-Mode v2 — auto-compact the agent session context (best-effort).

    ``session_id`` comes from the query param (the frontend sends no body);
    falls back to a project-scoped session id when omitted.
    """
    _require_goal_mode()
    try:
        svc = _get_service()
        result = svc.compact_project_session(
            project_id,
            session_id or f"ferment-{project_id}",
            goal_mode=_session_goal_mode_override(session_id),
        )
        if result is None:
            raise HTTPException(status_code=404, detail="Project not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to compact project session")
        raise HTTPException(status_code=500, detail=str(e))
