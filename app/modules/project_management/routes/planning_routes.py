"""Planning, Scheduling, Gantt & Baseline REST Routes — Domain 06."""
import logging
from datetime import date
from typing import Optional, List
from fastapi import APIRouter, Query, HTTPException, Body

from app.modules.auth.dependencies import require_permission
from common_lib.modules.project_management.planning.service import PlanningService

logger = logging.getLogger(__name__)
router = APIRouter()


# --- Timeline & Gantt ---
@router.get("/timeline/{project_id}", tags=["PM Planning"])
async def get_timeline(project_id: str, _perm: None = require_permission("project.read", "*", "project")):
    return PlanningService.get_timeline_data(project_id)


@router.get("/gantt/{project_id}", tags=["PM Planning"])
async def get_gantt(project_id: str, _perm: None = require_permission("project.read", "*", "project")):
    return PlanningService.get_gantt_data(project_id)


# --- Critical Path ---
@router.get("/critical-path/{project_id}", tags=["PM Planning"])
async def get_critical_path(project_id: str, _perm: None = require_permission("project.read", "*", "project")):
    return PlanningService.calculate_critical_path(project_id)


# --- Baselines ---
@router.post("/baselines", tags=["PM Planning"])
async def create_baseline(_perm: None = require_permission("project.write", "*", "project"),
    project_id: str = Query(...),
    name: str = Query(...),
    description: Optional[str] = Query(None),
    baseline_type: str = Query("schedule"),
    is_active: bool = Query(False),
    saved_by: Optional[str] = Query(None),
):
    from common_lib.modules.project_management.schemas import BaselineCreate
    data = BaselineCreate(
        project_id=project_id, name=name, description=description,
        baseline_type=baseline_type, is_active=is_active, saved_by=saved_by,
    )
    baseline = PlanningService.create_baseline(data)
    if not baseline:
        raise HTTPException(status_code=400, detail="Failed to create baseline")
    return baseline


@router.get("/baselines/{project_id}", tags=["PM Planning"])
async def list_baselines(project_id: str, limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0), _perm: None = require_permission("project.read", "*", "project")):
    return PlanningService.list_baselines(project_id, limit=limit, offset=offset)


@router.get("/baselines/detail/{baseline_id}", tags=["PM Planning"])
async def get_baseline(baseline_id: str, _perm: None = require_permission("project.read", "*", "project")):
    baseline = PlanningService.get_baseline(baseline_id)
    if not baseline:
        raise HTTPException(status_code=404, detail="Baseline not found")
    return baseline


@router.get("/baselines/{baseline_id}/tasks", tags=["PM Planning"])
async def get_baseline_tasks(baseline_id: str, _perm: None = require_permission("project.read", "*", "project")):
    return PlanningService.get_baseline_tasks(baseline_id)


@router.post("/baselines/{baseline_id}/activate", tags=["PM Planning"])
async def set_active_baseline(baseline_id: str, _perm: None = require_permission("project.write", "*", "project")):
    baseline = PlanningService.set_active_baseline(baseline_id)
    if not baseline:
        raise HTTPException(status_code=404, detail="Baseline not found")
    return baseline


@router.get("/baselines/{baseline_id}/compare", tags=["PM Planning"])
async def compare_to_baseline(baseline_id: str, _perm: None = require_permission("project.read", "*", "project")):
    return PlanningService.compare_to_baseline(baseline_id)


# --- Progress ---
@router.get("/progress/{project_id}", tags=["PM Planning"])
async def get_project_progress(project_id: str, _perm: None = require_permission("project.read", "*", "project")):
    return PlanningService.get_project_progress(project_id)


# --- Constraints ---
@router.post("/constraints", tags=["PM Planning"])
async def set_constraint(_perm: None = require_permission("project.write", "*", "project"),
    issue_id: str = Query(...),
    constraint_type: str = Query("as_soon_as_possible"),
    constraint_date: Optional[str] = Query(None),
):
    d = date.fromisoformat(constraint_date) if constraint_date else None
    return PlanningService.add_schedule_constraint(issue_id, constraint_type, d)


@router.get("/constraints/{issue_id}", tags=["PM Planning"])
async def get_constraints(issue_id: str, _perm: None = require_permission("project.read", "*", "project")):
    return PlanningService.get_issue_schedule_constraints(issue_id)


@router.post("/calendars/calculate-end-date", tags=["PM Planning"])
async def calculate_end_date(
    project_id: str = Query(...), 
    start_date: str = Query(...), 
    duration_days: int = Query(...), 
    _perm: None = require_permission("project.read", "*", "project")
):
    """Test utility to calculate end date by applying calendar exceptions."""
    d = date.fromisoformat(start_date)
    return {"end_date": PlanningService.apply_calendar_exceptions(project_id, d, duration_days)}


# --- WBS ---
@router.post("/wbs", tags=["PM Planning"])
async def create_wbs_node(_perm: None = require_permission("project.write", "*", "project"),
    project_id: str = Query(...),
    name: str = Query(...),
    parent_id: Optional[str] = Query(None),
    description: Optional[str] = Query(None),
    sort_order: int = Query(0),
    linked_issue_id: Optional[str] = Query(None),
    planned_start: Optional[str] = Query(None),
    planned_end: Optional[str] = Query(None),
    pct_complete: int = Query(0, ge=0, le=100),
):
    from common_lib.modules.project_management.schemas import WBSNodeCreate
    ps = date.fromisoformat(planned_start) if planned_start else None
    pe = date.fromisoformat(planned_end) if planned_end else None
    data = WBSNodeCreate(
        project_id=project_id, name=name, parent_id=parent_id,
        description=description, sort_order=sort_order,
        linked_issue_id=linked_issue_id, planned_start=ps,
        planned_end=pe, pct_complete=pct_complete,
    )
    return PlanningService.create_wbs_node(data)


@router.get("/wbs/{project_id}", tags=["PM Planning"])
async def get_wbs_tree(project_id: str, _perm: None = require_permission("project.read", "*", "project")):
    return PlanningService.get_wbs_tree(project_id)


# --- Calendars ---
@router.post("/calendars", tags=["PM Planning"])
async def create_calendar(_perm: None = require_permission("project.write", "*", "project"),
    project_id: str = Query(...),
    name: str = Query("Standard"),
    working_days: str = Query("1,2,3,4,5"),
    working_hours: float = Query(8.0),
):
    from decimal import Decimal
    return PlanningService.create_calendar(project_id, name, working_days, Decimal(str(working_hours)))


@router.get("/calendars/{project_id}", tags=["PM Planning"])
async def list_calendars(project_id: str, _perm: None = require_permission("project.read", "*", "project")):
    return PlanningService.list_calendars(project_id)


@router.post("/calendar-exceptions", tags=["PM Planning"])
async def add_calendar_exception(_perm: None = require_permission("project.write", "*", "project"),
    calendar_id: str = Query(...),
    exception_date: str = Query(...),
    exception_type: str = Query("holiday"),
    label: Optional[str] = Query(None),
):
    d = date.fromisoformat(exception_date)
    return PlanningService.add_calendar_exception(calendar_id, d, exception_type, label)


@router.get("/calendar-exceptions/{calendar_id}", tags=["PM Planning"])
async def list_calendar_exceptions(calendar_id: str, _perm: None = require_permission("project.read", "*", "project")):
    return PlanningService.list_calendar_exceptions(calendar_id)
