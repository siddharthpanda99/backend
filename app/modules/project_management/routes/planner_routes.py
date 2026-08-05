"""
PM Planner — Pomodoro, Focus Sessions, Daily Plans & Productivity Analytics Routes.

Endpoints:
- Pomodoro: POST /start, POST /{id}/complete, POST /{id}/pause, POST /{id}/resume,
  POST /{id}/interrupt, GET /running, GET /
- Focus Sessions: POST /focus, GET /focus
- Daily Plans: POST /plans, GET /plans/today, GET /plans
- Analytics: GET /stats, GET /stats/weekly
- Config: GET /config, PUT /config
"""
from __future__ import annotations

import logging
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from app.modules.auth.dependencies import require_permission


def _get_session():
    from common_lib.modules.integration.adapters.database_adapter import get_db_port
    engine = get_db_port().get_engine()
    return Session(engine)


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/planner", tags=["project_management", "planner"])


# ===========================================================================
# Pomodoro Config
# ===========================================================================


@router.get("/config")
def get_pomodoro_config(
    user_id: str = Query("system"),
    _perm: None = require_permission("planner.read", "*", "planner"),
    session: Session = Depends(_get_session),
):
    """Get the user's pomodoro timer configuration."""
    from common_lib.modules.project_management.planner.service import PlannerService
    svc = PlannerService(session=session)
    config = svc.get_or_create_config(user_id)
    return {
        "work_duration": config.work_duration,
        "short_break_duration": config.short_break_duration,
        "long_break_duration": config.long_break_duration,
        "pomodoros_before_long": config.pomodoros_before_long,
        "auto_start_breaks": config.auto_start_breaks,
        "auto_start_work": config.auto_start_work,
        "daily_pomodoro_goal": config.daily_pomodoro_goal,
        "sound_enabled": config.sound_enabled,
        "notifications_enabled": config.notifications_enabled,
    }


@router.put("/config")
def update_pomodoro_config(
    updates: dict,
    user_id: str = Query("system"),
    _perm: None = require_permission("planner.update", "*", "planner"),
    session: Session = Depends(_get_session),
):
    """Update the user's pomodoro timer configuration."""
    from common_lib.modules.project_management.planner.service import PlannerService
    svc = PlannerService(session=session)
    config = svc.update_config(user_id, updates)
    return {
        "work_duration": config.work_duration,
        "daily_pomodoro_goal": config.daily_pomodoro_goal,
    }


# ===========================================================================
# Pomodoro Timer
# ===========================================================================


@router.post("/start")
def start_pomodoro(
    session_type: str = Query("work"),
    user_id: str = Query("system"),
    project_id: Optional[str] = Query(None),
    issue_id: Optional[str] = Query(None),
    _perm: None = require_permission("planner.create", "*", "planner"),
    session: Session = Depends(_get_session),
):
    """Start a pomodoro work or break interval."""
    from common_lib.modules.project_management.planner.service import PlannerService
    svc = PlannerService(session=session)
    pom = svc.start_pomodoro(
        user_id=user_id, session_type=session_type,
        project_id=project_id, issue_id=issue_id,
    )
    return {
        "id": pom.id, "session_type": pom.session_type,
        "planned_duration_seconds": pom.planned_duration_seconds,
        "state": pom.state,
        "started_at": pom.started_at.isoformat() if pom.started_at else None,
    }


@router.post("/{session_id}/complete")
def complete_pomodoro(
    session_id: str,
    notes: Optional[str] = Query(None),
    focus_quality: Optional[str] = Query(None),
    _perm: None = require_permission("planner.update", "*", "planner"),
    session: Session = Depends(_get_session),
):
    """Complete a running or paused pomodoro."""
    from common_lib.modules.project_management.planner.service import PlannerService
    svc = PlannerService(session=session)
    pom = svc.complete_pomodoro(session_id, notes=notes, focus_quality=focus_quality)
    if not pom:
        raise HTTPException(status_code=404, detail=f"Pomodoro {session_id} not found or not active")
    return {"id": pom.id, "state": pom.state, "actual_duration_seconds": pom.actual_duration_seconds}


@router.post("/{session_id}/pause")
def pause_pomodoro(
    session_id: str,
    _perm: None = require_permission("planner.update", "*", "planner"),
    session: Session = Depends(_get_session),
):
    """Pause a running pomodoro."""
    from common_lib.modules.project_management.planner.service import PlannerService
    svc = PlannerService(session=session)
    pom = svc.pause_pomodoro(session_id)
    if not pom:
        raise HTTPException(status_code=404, detail="Pomodoro not found or not running")
    return {"id": pom.id, "state": pom.state}


@router.post("/{session_id}/resume")
def resume_pomodoro(
    session_id: str,
    _perm: None = require_permission("planner.update", "*", "planner"),
    session: Session = Depends(_get_session),
):
    """Resume a paused pomodoro."""
    from common_lib.modules.project_management.planner.service import PlannerService
    svc = PlannerService(session=session)
    pom = svc.resume_pomodoro(session_id)
    if not pom:
        raise HTTPException(status_code=404, detail="Pomodoro not found or not paused")
    return {"id": pom.id, "state": pom.state}


@router.post("/{session_id}/interrupt")
def interrupt_pomodoro(
    session_id: str,
    reason: Optional[str] = Query("unspecified"),
    _perm: None = require_permission("planner.update", "*", "planner"),
    session: Session = Depends(_get_session),
):
    """Record an interruption and mark the pomodoro as interrupted."""
    from common_lib.modules.project_management.planner.service import PlannerService
    svc = PlannerService(session=session)
    pom = svc.interrupt_pomodoro(session_id, reason=reason)
    if not pom:
        raise HTTPException(status_code=404, detail="Pomodoro not found or not running")
    return {"id": pom.id, "state": pom.state, "interruption_count": pom.interruption_count}


@router.get("/running")
def get_running_pomodoro(
    user_id: str = Query("system"),
    _perm: None = require_permission("planner.read", "*", "planner"),
    session: Session = Depends(_get_session),
):
    """Get the user's currently running pomodoro."""
    from common_lib.modules.project_management.planner.service import PlannerService
    svc = PlannerService(session=session)
    pom = svc.get_running_pomodoro(user_id)
    if not pom:
        return {"running": False, "id": None}
    return {
        "running": True, "id": pom.id,
        "session_type": pom.session_type,
        "planned_duration_seconds": pom.planned_duration_seconds,
        "started_at": pom.started_at.isoformat() if pom.started_at else None,
        "issue_id": pom.issue_id,
        "project_id": pom.project_id,
    }


@router.get("")
def list_pomodoros(
    user_id: str = Query("system"),
    session_type: Optional[str] = Query(None),
    project_id: Optional[str] = Query(None),
    issue_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    _perm: None = require_permission("planner.read", "*", "planner"),
    session: Session = Depends(_get_session),
):
    """List pomodoro sessions with filters."""
    from common_lib.modules.project_management.planner.service import PlannerService
    svc = PlannerService(session=session)
    poms = svc.list_pomodoros(
        user_id=user_id, session_type=session_type,
        project_id=project_id, issue_id=issue_id, limit=limit,
    )
    return {"sessions": [p.model_dump() for p in poms], "total": len(poms)}


# ===========================================================================
# Focus Sessions
# ===========================================================================


@router.post("/focus")
def create_focus_session(
    user_id: str = Query("system"),
    project_id: Optional[str] = Query(None),
    name: Optional[str] = Query(None),
    work_duration: Optional[int] = Query(None),
    short_break: Optional[int] = Query(None),
    long_break: Optional[int] = Query(None),
    pomodoros_before_long: Optional[int] = Query(None),
    _perm: None = require_permission("planner.create", "*", "planner"),
    session: Session = Depends(_get_session),
):
    """Create a focus session — a block of consecutive pomodoros."""
    from common_lib.modules.project_management.planner.service import PlannerService
    svc = PlannerService(session=session)
    fs = svc.create_focus_session(
        user_id=user_id, project_id=project_id, name=name,
        work_duration=work_duration, short_break=short_break,
        long_break=long_break, pomodoros_before_long=pomodoros_before_long,
    )
    return {"id": fs.id, "name": fs.name, "state": fs.state}


@router.post("/focus/{focus_session_id}/start")
def start_focus_session(
    focus_session_id: str,
    _perm: None = require_permission("planner.update", "*", "planner"),
    session: Session = Depends(_get_session),
):
    """Activate a focus session."""
    from common_lib.modules.project_management.planner.service import PlannerService
    svc = PlannerService(session=session)
    fs = svc.start_focus_session(focus_session_id)
    if not fs:
        raise HTTPException(status_code=404, detail="Focus session not found or not in planned/paused state")
    return {"id": fs.id, "name": fs.name, "state": fs.state, "started_at": fs.started_at.isoformat() if fs.started_at else None}


@router.post("/focus/{focus_session_id}/complete")
def complete_focus_session(
    focus_session_id: str,
    _perm: None = require_permission("planner.update", "*", "planner"),
    session: Session = Depends(_get_session),
):
    """Mark a focus session as complete."""
    from common_lib.modules.project_management.planner.service import PlannerService
    svc = PlannerService(session=session)
    fs = svc.complete_focus_session(focus_session_id)
    if not fs:
        raise HTTPException(status_code=404, detail="Focus session not found or not active/paused")
    return {"id": fs.id, "name": fs.name, "state": fs.state, "completed_pomodoros": fs.completed_pomodoros}


@router.get("/focus")
def list_focus_sessions(
    user_id: str = Query("system"),
    project_id: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    _perm: None = require_permission("planner.read", "*", "planner"),
    session: Session = Depends(_get_session),
):
    """List focus sessions."""
    from common_lib.modules.project_management.planner.service import PlannerService
    svc = PlannerService(session=session)
    sessions = svc.list_focus_sessions(user_id=user_id, project_id=project_id, limit=limit)
    return {"sessions": [s.model_dump() for s in sessions], "total": len(sessions)}


# ===========================================================================
# Daily Plans
# ===========================================================================


@router.post("/plans")
def create_daily_plan(
    user_id: str = Query("system"),
    plan_date: Optional[str] = Query(None),
    project_id: Optional[str] = Query(None),
    title: Optional[str] = Query(None),
    planned_pomodoros: int = Query(8),
    _perm: None = require_permission("planner.create", "*", "planner"),
    session: Session = Depends(_get_session),
):
    """Create a daily plan."""
    from common_lib.modules.project_management.planner.service import PlannerService
    svc = PlannerService(session=session)
    plan = svc.create_daily_plan(
        user_id=user_id, plan_date=plan_date, project_id=project_id,
        title=title, planned_pomodoros=planned_pomodoros,
    )
    return {"id": plan.id, "plan_date": plan.plan_date.isoformat(), "state": plan.state}


@router.get("/plans/today")
def get_today_plan(
    user_id: str = Query("system"),
    _perm: None = require_permission("planner.read", "*", "planner"),
    session: Session = Depends(_get_session),
):
    """Get today's daily plan."""
    from common_lib.modules.project_management.planner.service import PlannerService
    svc = PlannerService(session=session)
    plan = svc.get_daily_plan(user_id)
    if not plan:
        return {"id": None, "plan_date": None, "message": "No plan for today"}
    return {
        "id": plan.id, "plan_date": plan.plan_date.isoformat(),
        "title": plan.title, "state": plan.state,
        "planned_pomodoros": plan.planned_pomodoros,
        "completed_pomodoros": plan.completed_pomodoros,
    }


@router.get("/plans")
def list_daily_plans(
    user_id: str = Query("system"),
    since: Optional[str] = Query(None),
    limit: int = Query(30, ge=1, le=100),
    _perm: None = require_permission("planner.read", "*", "planner"),
    session: Session = Depends(_get_session),
):
    """List daily plans."""
    from common_lib.modules.project_management.planner.service import PlannerService
    svc = PlannerService(session=session)
    plans = svc.list_daily_plans(user_id=user_id, since=since, limit=limit)
    return {"plans": [p.model_dump() for p in plans], "total": len(plans)}


# ===========================================================================
# Productivity Analytics
# ===========================================================================


@router.get("/stats")
def get_productivity_stats(
    user_id: str = Query("system"),
    days: int = Query(30, ge=1, le=365),
    _perm: None = require_permission("planner.read", "*", "planner"),
    session: Session = Depends(_get_session),
):
    """Get productivity statistics for the last N days."""
    from common_lib.modules.project_management.planner.service import PlannerService
    svc = PlannerService(session=session)
    return svc.get_productivity_stats(user_id=user_id, days=days)


@router.get("/stats/weekly")
def get_weekly_summary(
    user_id: str = Query("system"),
    _perm: None = require_permission("planner.read", "*", "planner"),
    session: Session = Depends(_get_session),
):
    """Get this week's productivity summary."""
    from common_lib.modules.project_management.planner.service import PlannerService
    svc = PlannerService(session=session)
    return svc.get_weekly_summary(user_id=user_id)
