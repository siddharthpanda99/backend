"""
PM Module — Goals, OKRs & Key Results Routes (Domain 10)

REST API endpoints for strategic goals, objectives, key results,
check-ins, progress tracking, and goal-to-work linking.

All routes are under /goals prefix, mounted in index.py.

RBAC permissions: goal.read, goal.create, goal.update, goal.delete
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request

from sqlmodel import Session

from app.modules.auth.dependencies import require_permission
from app.modules.project_management.field_security_deps import (
    filter_single_response,
    filter_list_response,
    strip_field_security_metadata,
)


def _get_session():
    from common_lib.modules.integration.adapters.database_adapter import get_db_port
    engine = get_db_port().get_engine()
    return Session(engine)


router = APIRouter(prefix="/goals", tags=["PM Goals & OKRs"])


# ------------------------------------------------------------------ #
# Goal CRUD
# ------------------------------------------------------------------ #

@router.get("")
def list_goals(
    request: Request,
    project_id: Optional[str] = Query(None),
    portfolio_id: Optional[str] = Query(None),
    goal_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50),
    offset: int = Query(0),
    session: Session = Depends(_get_session),
    _perm: None = require_permission("goal.read", "*", "goal"),
):
    """List strategic goals with optional filters."""
    from common_lib.modules.project_management.goals.service import GoalService

    svc = GoalService(session)
    goals = svc.list_goals(
        project_id=project_id,
        portfolio_id=portfolio_id,
        goal_type=goal_type,
        status=status,
        limit=limit,
        offset=offset,
    )
    items = [g.model_dump() for g in goals] if hasattr(goals[0], 'model_dump') else goals
    items = filter_list_response(request, session, "goal", items, project_id=project_id)
    total = len(items)
    return {"items": items, "total": total, "limit": limit, "offset": offset, "has_more": (offset + limit) < total}


@router.post("")
def create_goal(
    data: dict,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("goal.create", "*", "goal"),
):
    """Create a new strategic goal."""
    from common_lib.modules.project_management.goals.service import GoalService
    from common_lib.modules.project_management.schemas import GoalCreate

    schema = GoalCreate(**data)
    svc = GoalService(session)
    goal = svc.create_goal(schema)
    return goal


@router.get("/{goal_id}")
def get_goal(
    request: Request,
    goal_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("goal.read", "*", "goal"),
):
    """Get a single goal by ID."""
    from common_lib.modules.project_management.goals.service import GoalService

    svc = GoalService(session)
    goal = svc.get_goal(goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    data = goal.model_dump() if hasattr(goal, 'model_dump') else goal
    data = filter_single_response(request, session, "goal", data)
    return strip_field_security_metadata(data)


@router.patch("/{goal_id}")
def update_goal(
    goal_id: str,
    data: dict,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("goal.update", "*", "goal"),
):
    """Update a goal (partial update)."""
    from common_lib.modules.project_management.goals.service import GoalService
    from common_lib.modules.project_management.schemas import GoalUpdate

    schema = GoalUpdate(**data)
    svc = GoalService(session)
    goal = svc.update_goal(goal_id, schema)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    return goal


@router.delete("/{goal_id}")
def delete_goal(
    goal_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("goal.delete", "*", "goal"),
):
    """Delete a goal and cascade its objectives and key results."""
    from common_lib.modules.project_management.goals.service import GoalService

    svc = GoalService(session)
    success = svc.delete_goal(goal_id)
    if not success:
        raise HTTPException(status_code=404, detail="Goal not found")
    return {"ok": True}


@router.get("/{goal_id}/tree")
def get_goal_tree(
    goal_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("goal.read", "*", "goal"),
):
    """Get a goal with its objectives and key results."""
    from common_lib.modules.project_management.goals.service import GoalService

    svc = GoalService(session)
    tree = svc.get_goal_tree(goal_id)
    if not tree:
        raise HTTPException(status_code=404, detail="Goal not found")
    return tree


@router.get("/{goal_id}/progress")
def get_goal_progress(
    goal_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("goal.read", "*", "goal"),
):
    """Get progress rollup for a goal (objectives -> KRs)."""
    from common_lib.modules.project_management.goals.service import GoalService

    svc = GoalService(session)
    progress = svc.get_goal_progress(goal_id)
    if not progress:
        raise HTTPException(status_code=404, detail="Goal not found")
    return progress


@router.get("/hierarchy")
def get_goal_hierarchy(
    session: Session = Depends(_get_session),
    _perm: None = require_permission("goal.read", "*", "goal"),
):
    """Get all goals organized by hierarchy (company -> department -> team)."""
    from common_lib.modules.project_management.goals.service import GoalService

    svc = GoalService(session)
    return svc.get_goal_hierarchy()


# ------------------------------------------------------------------ #
# Objective CRUD
# ------------------------------------------------------------------ #

@router.post("/{goal_id}/objectives")
def create_objective(
    goal_id: str,
    data: dict,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("goal.create", "*", "goal"),
):
    """Create an objective under a goal."""
    from common_lib.modules.project_management.goals.service import GoalService
    from common_lib.modules.project_management.schemas import ObjectiveCreate

    data["goal_id"] = goal_id
    schema = ObjectiveCreate(**data)
    svc = GoalService(session)
    objective = svc.create_objective(schema)
    return objective


@router.get("/{goal_id}/objectives")
def list_objectives(
    goal_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("goal.read", "*", "goal"),
):
    """List all objectives under a goal."""
    from common_lib.modules.project_management.goals.service import GoalService

    svc = GoalService(session)
    return svc.list_objectives(goal_id)


@router.patch("/objectives/{objective_id}")
def update_objective(
    objective_id: str,
    data: dict,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("goal.update", "*", "goal"),
):
    """Update an objective."""
    from common_lib.modules.project_management.goals.service import GoalService
    from common_lib.modules.project_management.schemas import ObjectiveUpdate

    schema = ObjectiveUpdate(**data)
    svc = GoalService(session)
    objective = svc.update_objective(objective_id, schema)
    if not objective:
        raise HTTPException(status_code=404, detail="Objective not found")
    return objective


@router.delete("/objectives/{objective_id}")
def delete_objective(
    objective_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("goal.delete", "*", "goal"),
):
    """Delete an objective and cascade its key results."""
    from common_lib.modules.project_management.goals.service import GoalService

    svc = GoalService(session)
    success = svc.delete_objective(objective_id)
    if not success:
        raise HTTPException(status_code=404, detail="Objective not found")
    return {"ok": True}


# ------------------------------------------------------------------ #
# Key Result CRUD
# ------------------------------------------------------------------ #

@router.post("/objectives/{objective_id}/key-results")
def create_key_result(
    objective_id: str,
    data: dict,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("goal.create", "*", "goal"),
):
    """Create a key result under an objective."""
    from common_lib.modules.project_management.goals.service import GoalService
    from common_lib.modules.project_management.schemas import KeyResultCreate

    data["objective_id"] = objective_id
    schema = KeyResultCreate(**data)
    svc = GoalService(session)
    kr = svc.create_key_result(schema)
    return kr


@router.get("/objectives/{objective_id}/key-results")
def list_key_results(
    objective_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("goal.read", "*", "goal"),
):
    """List all key results under an objective."""
    from common_lib.modules.project_management.goals.service import GoalService

    svc = GoalService(session)
    return svc.list_key_results(objective_id)


@router.patch("/key-results/{kr_id}")
def update_key_result(
    kr_id: str,
    data: dict,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("goal.update", "*", "goal"),
):
    """Update a key result (updates progress automatically)."""
    from common_lib.modules.project_management.goals.service import GoalService
    from common_lib.modules.project_management.schemas import KeyResultUpdate

    schema = KeyResultUpdate(**data)
    svc = GoalService(session)
    kr = svc.update_key_result(kr_id, schema)
    if not kr:
        raise HTTPException(status_code=404, detail="Key result not found")
    return kr


@router.delete("/key-results/{kr_id}")
def delete_key_result(
    kr_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("goal.delete", "*", "goal"),
):
    """Delete a key result."""
    from common_lib.modules.project_management.goals.service import GoalService

    svc = GoalService(session)
    success = svc.delete_key_result(kr_id)
    if not success:
        raise HTTPException(status_code=404, detail="Key result not found")
    return {"ok": True}


# ------------------------------------------------------------------ #
# Check-Ins
# ------------------------------------------------------------------ #

@router.post("/key-results/{kr_id}/checkins")
def create_checkin(
    kr_id: str,
    data: dict,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("goal.update", "*", "goal"),
):
    """Record a progress check-in on a key result."""
    from common_lib.modules.project_management.goals.service import GoalService
    from common_lib.modules.project_management.schemas import CheckInCreate

    data["key_result_id"] = kr_id
    schema = CheckInCreate(**data)
    svc = GoalService(session)
    checkin = svc.create_checkin(schema)
    return checkin


@router.get("/key-results/{kr_id}/checkins")
def list_checkins(
    kr_id: str,
    limit: int = Query(50),
    offset: int = Query(0),
    session: Session = Depends(_get_session),
    _perm: None = require_permission("goal.read", "*", "goal"),
):
    """List progress check-ins for a key result."""
    from common_lib.modules.project_management.goals.service import GoalService

    svc = GoalService(session)
    return svc.list_checkins(kr_id, limit=limit, offset=offset)


# ------------------------------------------------------------------ #
# Goal-to-Work Linking
# ------------------------------------------------------------------ #

@router.post("/{goal_id}/link")
def link_goal_to_work(
    goal_id: str,
    data: dict,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("goal.update", "*", "goal"),
):
    """Link a goal to a project or portfolio."""
    from common_lib.modules.project_management.goals.service import GoalService

    svc = GoalService(session)
    success = svc.link_goal_to_work(
        goal_id=goal_id,
        target_type=data.get("target_type", ""),
        target_id=data.get("target_id", ""),
        target_name=data.get("target_name"),
    )
    if not success:
        raise HTTPException(status_code=404, detail="Goal not found")
    return {"ok": True}


@router.post("/{goal_id}/unlink")
def unlink_goal_from_work(
    goal_id: str,
    data: dict,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("goal.update", "*", "goal"),
):
    """Unlink a goal from a project or portfolio."""
    from common_lib.modules.project_management.goals.service import GoalService

    svc = GoalService(session)
    success = svc.unlink_goal_from_work(
        goal_id=goal_id,
        target_type=data.get("target_type", ""),
    )
    if not success:
        raise HTTPException(status_code=404, detail="Goal not found")
    return {"ok": True}


# ------------------------------------------------------------------ #
# Benefits Tracking — Domain 10.07
# ------------------------------------------------------------------ #

@router.get("/{goal_id}/benefits")
def list_goal_benefits(
    goal_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("goal.read", "*", "goal"),
):
    """List benefits tracked against a goal."""
    from common_lib.modules.project_management.goals.service import GoalService
    svc = GoalService(session)
    benefits = svc.list_benefits(goal_id=goal_id)
    return {"items": benefits, "total": len(benefits)}


@router.post("/{goal_id}/benefits")
def create_goal_benefit(
    goal_id: str,
    data: dict,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("goal.create", "*", "goal"),
):
    """Create a benefit tracking record linked to a goal."""
    from common_lib.modules.project_management.goals.service import GoalService
    from common_lib.modules.project_management.schemas import BenefitCreate

    data["goal_id"] = goal_id
    schema = BenefitCreate(**data)
    svc = GoalService(session)
    benefit = svc.create_benefit(schema)
    return benefit


@router.get("/benefits/{benefit_id}")
def get_benefit(
    benefit_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("goal.read", "*", "goal"),
):
    """Get a benefit tracking record by ID."""
    from common_lib.modules.project_management.goals.service import GoalService
    svc = GoalService(session)
    benefit = svc.get_benefit(benefit_id)
    if not benefit:
        raise HTTPException(status_code=404, detail="Benefit not found")
    return benefit


@router.patch("/benefits/{benefit_id}")
def update_benefit(
    benefit_id: str,
    data: dict,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("goal.update", "*", "goal"),
):
    """Update a benefit tracking record."""
    from common_lib.modules.project_management.goals.service import GoalService
    from common_lib.modules.project_management.schemas import BenefitUpdate

    schema = BenefitUpdate(**data)
    svc = GoalService(session)
    benefit = svc.update_benefit(benefit_id, schema)
    if not benefit:
        raise HTTPException(status_code=404, detail="Benefit not found")
    return benefit


@router.delete("/benefits/{benefit_id}")
def delete_benefit(
    benefit_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("goal.delete", "*", "goal"),
):
    """Delete a benefit tracking record."""
    from common_lib.modules.project_management.goals.service import GoalService
    svc = GoalService(session)
    if not svc.delete_benefit(benefit_id):
        raise HTTPException(status_code=404, detail="Benefit not found")
    return {"ok": True}


# ------------------------------------------------------------------ #
# KPI Dashboard — Domain 10.03
# ------------------------------------------------------------------ #

@router.get("/kpi-dashboard")
def get_kpi_dashboard(
    session: Session = Depends(_get_session),
    _perm: None = require_permission("goal.read", "*", "goal"),
):
    """Get KPI aggregation dashboard from all goals, OKRs, and benefits."""
    from common_lib.modules.project_management.goals.service import GoalService
    svc = GoalService(session)
    return svc.get_kpi_dashboard()
