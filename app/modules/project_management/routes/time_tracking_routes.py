"""
Time Tracking API Routes.

Endpoints:
- Manual time entry CRUD (log, edit, delete)
- Timer start/stop
- Time reports per issue/project

RBAC permissions: time.read, time.create, time.update, time.delete
"""

import logging
from typing import Optional
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from app.modules.auth.dependencies import require_permission
from common_lib.modules.project_management.time_tracking.service import TimeTrackingService
from common_lib.modules.project_management.schemas import (
    TimeEntryCreate, TimeEntryUpdate, TimeEntryRead,
    TimerStartResponse, TimerStopResponse, TimeReport,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/time", tags=["project_management", "time_tracking"])


def _get_session():
    from common_lib.modules.integration.adapters.database_adapter import get_db_port
    engine = get_db_port().get_engine()
    return Session(engine)


# ---------------------------------------------------------------------------
# Time Entry CRUD
# ---------------------------------------------------------------------------


@router.post("/entries", response_model=TimeEntryRead, status_code=201)
def log_time(
    data: TimeEntryCreate,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("time.create", "*", "time"),
):
    """Log time against an issue."""
    try:
        svc = TimeTrackingService(session)
        entry = svc.log_time(data)
        return entry
    except Exception as e:
        logger.error("log_time failed: %s", e)
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/entries/{entry_id}", response_model=TimeEntryRead)
def get_time_entry(
    entry_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("time.read", "*", "time"),
):
    """Get a single time entry by ID."""
    svc = TimeTrackingService(session)
    entry = svc.get_entry(entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Time entry not found")
    return entry


@router.put("/entries/{entry_id}", response_model=TimeEntryRead)
def update_time_entry(
    entry_id: str,
    data: TimeEntryUpdate,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("time.update", "*", "time"),
):
    """Update a time entry."""
    svc = TimeTrackingService(session)
    entry = svc.update_entry(entry_id, data)
    if not entry:
        raise HTTPException(status_code=404, detail="Time entry not found")
    return entry


@router.delete("/entries/{entry_id}", status_code=204)
def delete_time_entry(
    entry_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("time.delete", "*", "time"),
):
    """Delete a time entry."""
    svc = TimeTrackingService(session)
    success = svc.delete_entry(entry_id)
    if not success:
        raise HTTPException(status_code=404, detail="Time entry not found")
    return None


# ---------------------------------------------------------------------------
# Timer
# ---------------------------------------------------------------------------


@router.post("/timer/start/{issue_id}", response_model=TimerStartResponse)
def start_timer(
    issue_id: str,
    user_id: str = Query(default="system"),
    session: Session = Depends(_get_session),
    _perm: None = require_permission("time.create", "*", "time"),
):
    """Start a timer for an issue."""
    svc = TimeTrackingService(session)
    result = svc.start_timer(issue_id, user_id)
    if not result:
        raise HTTPException(status_code=400, detail="Cannot start timer -- a timer may already be running")
    return result


@router.post("/timer/stop/{issue_id}", response_model=TimerStopResponse)
def stop_timer(
    issue_id: str,
    user_id: str = Query(default="system"),
    session: Session = Depends(_get_session),
    _perm: None = require_permission("time.update", "*", "time"),
):
    """Stop the running timer for an issue."""
    svc = TimeTrackingService(session)
    result = svc.stop_timer(issue_id, user_id)
    if not result:
        raise HTTPException(status_code=404, detail="No active timer found for this issue/user")
    return result


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------


@router.get("/reports/issue/{issue_id}", response_model=TimeReport)
def get_issue_time_report(
    issue_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("time.read", "*", "time"),
):
    """Get aggregated time report for an issue."""
    svc = TimeTrackingService(session)
    return svc.get_time_report(issue_id=issue_id)


@router.get("/reports/project/{project_id}", response_model=TimeReport)
def get_project_time_report(
    project_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("time.read", "*", "time"),
):
    """Get aggregated time report for an entire project."""
    svc = TimeTrackingService(session)
    return svc.get_time_report(project_id=project_id)


@router.get("/entries")
def list_time_entries(
    issue_id: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0),
    session: Session = Depends(_get_session),
    _perm: None = require_permission("time.read", "*", "time"),
):
    """List time entries with optional filters."""
    svc = TimeTrackingService(session)
    entries = svc.list_entries(
        issue_id=issue_id,
        user_id=user_id,
        from_date=from_date,
        to_date=to_date,
        limit=limit,
        offset=offset,
    )
    return {"items": entries, "total": len(entries), "limit": limit, "offset": offset}
