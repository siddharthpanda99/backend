"""Agile, Scrum & Kanban extended REST Routes — Domain 05 gaps."""
import logging
from datetime import date, datetime
from typing import Optional
from fastapi import APIRouter, Query, HTTPException, Body
from sqlmodel import Session

from app.modules.auth.dependencies import require_permission
from common_lib.modules.project_management.agile.service import AgileService

logger = logging.getLogger(__name__)
router = APIRouter()


def _get_session():
    from common_lib.modules.integration.adapters.database_adapter import get_db_port
    engine = get_db_port().get_engine()
    return Session(engine)


# --- Cumulative Flow Diagram ---
@router.post("/cfd/snapshot/{project_id}", tags=["PM Agile"])
async def generate_cfd_snapshot(project_id: str, _perm: None = require_permission("agile.update", "*", "agile")):
    svc = AgileService(_get_session())
    result = svc.generate_cfd_snapshot(project_id)
    return {"ok": result}


@router.get("/cfd/{project_id}", tags=["PM Agile"])
async def get_cfd_data(project_id: str, days: int = Query(30, ge=1, le=365), _perm: None = require_permission("agile.read", "*", "agile")):
    svc = AgileService(_get_session())
    return svc.get_cfd_data(project_id, days)


# --- WIP Limits ---
@router.post("/wip-limits", tags=["PM Agile"])
async def set_wip_limit(
    project_id: str = Query(...),
    status_id: str = Query(...),
    status_name: str = Query(...),
    max_count: int = Query(5, ge=1),
    max_points: Optional[int] = Query(None),
    is_hard_limit: bool = Query(False),
):
    svc = AgileService(_get_session())
    return svc.set_wip_limit(project_id, status_id, status_name, max_count, max_points, is_hard_limit)


@router.get("/wip-limits/{project_id}", tags=["PM Agile"])
async def get_wip_limits(project_id: str, _perm: None = require_permission("agile.read", "*", "agile")):
    svc = AgileService(_get_session())
    return svc.get_wip_limits(project_id)


@router.get("/wip-limits/{project_id}/check", tags=["PM Agile"])
async def check_wip_limits(project_id: str, _perm: None = require_permission("agile.read", "*", "agile")):
    svc = AgileService(_get_session())
    return svc.check_wip_limits(project_id)


# --- Swimlanes ---
@router.post("/swimlanes", tags=["PM Agile"])
async def create_swimlane(
    project_id: str = Query(...),
    name: str = Query(...),
    swimlane_type: str = Query("standard"),
    sort_order: int = Query(0),
):
    svc = AgileService(_get_session())
    return svc.create_swimlane(project_id, name, swimlane_type=swimlane_type, sort_order=sort_order)


@router.get("/swimlanes/{project_id}", tags=["PM Agile"])
async def list_swimlanes(project_id: str, _perm: None = require_permission("agile.read", "*", "agile")):
    svc = AgileService(_get_session())
    return svc.list_swimlanes(project_id)


# --- Retrospectives ---
@router.post("/retrospectives", tags=["PM Agile"])
async def create_retrospective(
    sprint_id: str = Query(...),
    project_id: str = Query(...),
    what_went_well: Optional[str] = Query(None),
    what_could_improve: Optional[str] = Query(None),
    action_items: Optional[str] = Query(None),
    team_morale: Optional[int] = Query(None, ge=1, le=5),
    facilitator: Optional[str] = Query(None),
):
    svc = AgileService(_get_session())
    return svc.create_retrospective(
        sprint_id, project_id,
        what_went_well=what_went_well, what_could_improve=what_could_improve,
        action_items=action_items, team_morale=team_morale, facilitator=facilitator,
    )


@router.get("/retrospectives/{sprint_id}", tags=["PM Agile"])
async def get_retrospective(sprint_id: str, _perm: None = require_permission("agile.read", "*", "agile")):
    svc = AgileService(_get_session())
    retro = svc.get_retrospective(sprint_id)
    if not retro:
        raise HTTPException(status_code=404, detail="Retrospective not found")
    return retro


@router.patch("/retrospectives/{sprint_id}", tags=["PM Agile"])
async def update_retrospective(sprint_id: str, data: dict, _perm: None = require_permission("agile.update", "*", "agile")):
    svc = AgileService(_get_session())
    retro = svc.update_retrospective(sprint_id, data)
    if not retro:
        raise HTTPException(status_code=404, detail="Retrospective not found")
    return retro


# --- Standups ---
@router.post("/standups", tags=["PM Agile"])
async def create_standup(
    project_id: str = Query(...),
    user_id: str = Query(...),
    standup_date: str = Query(...),
    yesterday: Optional[str] = Query(None),
    today: Optional[str] = Query(None),
    blockers: Optional[str] = Query(None),
    mood: Optional[int] = Query(None, ge=1, le=5),
    sprint_id: Optional[str] = Query(None),
):
    svc = AgileService(_get_session())
    try:
        s_date = date.fromisoformat(standup_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
    return svc.create_standup(project_id, user_id, s_date, yesterday=yesterday, today=today, blockers=blockers, mood=mood, sprint_id=sprint_id)


@router.get("/standups/{project_id}", tags=["PM Agile"])
async def list_standups(
    project_id: str,
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    svc = AgileService(_get_session())
    d_from = date.fromisoformat(date_from) if date_from else None
    d_to = date.fromisoformat(date_to) if date_to else None
    return svc.list_standups(project_id, date_from=d_from, date_to=d_to, user_id=user_id, limit=limit, offset=offset)


@router.get("/standups/{project_id}/blockers", tags=["PM Agile"])
async def get_standup_blockers(project_id: str, sprint_id: Optional[str] = Query(None), _perm: None = require_permission("agile.read", "*", "agile")):
    svc = AgileService(_get_session())
    return svc.get_standup_blockers(project_id, sprint_id=sprint_id)


# --- Velocity Trend ---
@router.get("/velocity-trend/{project_id}", tags=["PM Agile"])
async def get_velocity_trend(project_id: str, num_sprints: int = Query(10, ge=3, le=50), _perm: None = require_permission("agile.read", "*", "agile")):
    svc = AgileService(_get_session())
    return svc.get_velocity_trend(project_id, num_sprints)

# --- Planning Poker ---
@router.post("/planning-poker/start", tags=["PM Agile"])
async def start_planning_poker(project_id: str = Body(...), issue_id: str = Body(...), sprint_id: Optional[str] = Body(None), _perm: None = require_permission("agile.manage", "*", "agile")):
    svc = AgileService(_get_session())
    return svc.start_planning_poker_session(project_id, issue_id, sprint_id)

@router.post("/planning-poker/{session_id}/vote", tags=["PM Agile"])
async def submit_poker_vote(session_id: str, user_id: str = Body(...), vote: str = Body(...), _perm: None = require_permission("agile.participate", "*", "agile")):
    svc = AgileService(_get_session())
    return svc.submit_poker_vote(session_id, user_id, vote)

@router.post("/planning-poker/{session_id}/end", tags=["PM Agile"])
async def end_planning_poker(session_id: str, final_estimation: Optional[float] = Body(None), _perm: None = require_permission("agile.manage", "*", "agile")):
    svc = AgileService(_get_session())
    return svc.end_planning_poker_session(session_id, final_estimation)

# --- LexoRank ---
@router.post("/backlog/reorder-lexorank", tags=["PM Agile"])
async def reorder_backlog_lexorank(issue_id: str = Body(...), prev_issue_id: Optional[str] = Body(None), next_issue_id: Optional[str] = Body(None), _perm: None = require_permission("agile.manage", "*", "agile")):
    svc = AgileService(_get_session())
    return svc.reorder_backlog_item_lexorank(issue_id, prev_issue_id, next_issue_id)

# --- Actual Burndown ---
@router.post("/sprints/{sprint_id}/track-actual-burndown", tags=["PM Agile"])
async def track_actual_burndown(sprint_id: str, _perm: None = require_permission("agile.manage", "*", "agile")):
    svc = AgileService(_get_session())
    return {"success": svc.track_actual_burndown(sprint_id)}
