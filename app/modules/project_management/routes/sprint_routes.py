"""
PM Sprint Routes — Thin API layer.

Registered at: /api/v1/jira/sprints/
"""
from __future__ import annotations

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlmodel import Session

from common_lib.modules.project_management import SprintService
from common_lib.modules.project_management.schemas import (
    SprintCreate, SprintUpdate, SprintRead, SprintMetrics,
)
from app.modules.project_management.field_security_deps import (
    filter_single_response,
    filter_list_response,
    check_field_editable,
    strip_field_security_metadata,
)
from app.modules.auth.dependencies import require_permission


# ---------------------------------------------------------------------------
# DB session helper
# ---------------------------------------------------------------------------
def _get_session():
    from common_lib.modules.integration.adapters.database_adapter import get_db_port
    engine = get_db_port().get_engine()
    return Session(engine)


logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/", response_model=List[SprintRead])
def list_sprints(
    request: Request,
    project_id: str = Query(...),
    status: Optional[str] = Query(None),
    session: Session = Depends(_get_session),
    _perm: None = require_permission("sprint.read", "*", "sprint"),
):
    """List sprints for a project."""
    svc = SprintService(session)
    sprints = svc.list_sprints(project_id=project_id, status=status)
    items = [s.model_dump() for s in sprints]
    items = filter_list_response(request, session, "sprint", items, project_id=project_id)
    return [SprintRead.model_validate(i) for i in items]


@router.post("/", response_model=SprintRead, status_code=201)
def create_sprint(
    data: SprintCreate,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("sprint.create", "*", "sprint"),
):
    """Create a new sprint."""
    svc = SprintService(session)
    try:
        return svc.create_sprint(data)
    except Exception as e:
        logger.exception("Failed to create sprint")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/active", response_model=Optional[SprintRead])
def get_active_sprint(
    request: Request,
    project_id: str = Query(...),
    session: Session = Depends(_get_session),
    _perm: None = require_permission("sprint.read", "*", "sprint"),
):
    """Get the active sprint for a project."""
    svc = SprintService(session)
    sprint = svc.get_active_sprint(project_id)
    if not sprint:
        raise HTTPException(status_code=404, detail="No active sprint")
    data = sprint.model_dump()
    data = filter_single_response(request, session, "sprint", data, project_id=project_id)
    return SprintRead.model_validate(strip_field_security_metadata(data))


@router.get("/{sprint_id}", response_model=SprintRead)
def get_sprint(
    request: Request,
    sprint_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("sprint.read", "*", "sprint"),
):
    """Get sprint by ID."""
    svc = SprintService(session)
    sprint = svc.get_sprint(sprint_id)
    if not sprint:
        raise HTTPException(status_code=404, detail="Sprint not found")
    data = sprint.model_dump()
    data = filter_single_response(request, session, "sprint", data, project_id=sprint.project_id)
    return SprintRead.model_validate(strip_field_security_metadata(data))


@router.patch("/{sprint_id}", response_model=SprintRead)
def update_sprint(
    request: Request,
    sprint_id: str,
    data: SprintUpdate,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("sprint.update", "*", "sprint"),
):
    """Update a sprint."""
    svc = SprintService(session)
    update_fields = data.model_dump(exclude_unset=True)
    existing = svc.get_sprint(sprint_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Sprint not found")
    for field_key in update_fields:
        if not check_field_editable(request, session, "sprint", field_key, project_id=existing.project_id):
            raise HTTPException(status_code=403, detail=f"Field '{field_key}' is not editable for your role")
    sprint = svc.update_sprint(sprint_id, data)
    if not sprint:
        raise HTTPException(status_code=404, detail="Sprint not found")
    return sprint


@router.post("/{sprint_id}/start", response_model=SprintRead)
def start_sprint(
    sprint_id: str,
    session: Session = Depends(_get_session),
):
    """Start a planned sprint."""
    svc = SprintService(session)
    sprint = svc.start_sprint(sprint_id)
    if not sprint:
        raise HTTPException(status_code=400, detail="Cannot start sprint")
    return sprint


@router.post("/{sprint_id}/complete", response_model=SprintRead)
def complete_sprint(
    sprint_id: str,
    session: Session = Depends(_get_session),
):
    """Complete an active sprint."""
    svc = SprintService(session)
    sprint = svc.complete_sprint(sprint_id)
    if not sprint:
        raise HTTPException(status_code=400, detail="Cannot complete sprint")
    return sprint


@router.get("/{sprint_id}/metrics", response_model=SprintMetrics)
def get_sprint_metrics(
    sprint_id: str,
    session: Session = Depends(_get_session),
):
    """Get sprint metrics (velocity, burndown, etc.)."""
    svc = SprintService(session)
    metrics = svc.get_sprint_metrics(sprint_id)
    if not metrics:
        raise HTTPException(status_code=404, detail="Sprint not found")
    return SprintMetrics(**metrics)
