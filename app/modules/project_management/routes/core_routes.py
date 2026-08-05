"""PM Core REST Routes — engineering metrics, analytics, calendar (Domain 32.x)."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session

from app.modules.project_management.deps import get_pm_session
from app.modules.auth.dependencies import require_permission

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/core", tags=["PM Core & Analytics"])


class MetricsSnapshotCreate(BaseModel):
    data: Dict[str, Any]


def _svc(session: Session):
    from common_lib.modules.project_management.core.service import CoreService

    return CoreService(session=session)


@router.get("/analytics/{project_id}")
def project_analytics(project_id: str, session: Session = Depends(get_pm_session), _perm: None = require_permission("core.read", "*", "core")):
    """Get aggregate project analytics."""
    return _svc(session).get_project_analytics(project_id=project_id)


@router.get("/metrics/{project_id}")
def engineering_metrics(project_id: str, days_back: int = Query(30, ge=1, le=365), session: Session = Depends(get_pm_session), _perm: None = require_permission("core.read", "*", "core")):
    """Get engineering metrics for a project."""
    return _svc(session).get_engineering_metrics(project_id=project_id, days_back=days_back)


@router.get("/snapshots/{project_id}")
def metric_snapshots(project_id: str, limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0), session: Session = Depends(get_pm_session), _perm: None = require_permission("core.read", "*", "core")):
    """List persisted metric snapshots."""
    snapshots = _svc(session).list_metric_snapshots(project_id=project_id, limit=limit, offset=offset)
    return {"snapshots": snapshots, "total": len(snapshots)}


@router.post("/snapshots/{project_id}")
def metric_snapshot_create(project_id: str, req: MetricsSnapshotCreate, session: Session = Depends(get_pm_session), _perm: None = require_permission("core.write", "*", "core")):
    """Persist a metrics snapshot."""
    snap = _svc(session).create_metric_snapshot(project_id=project_id, data=req.data)
    return {"id": getattr(snap, "id", None), "project_id": project_id}


@router.get("/calendar/{project_id}")
def calendar_events(project_id: str, start_date: Optional[str] = None, end_date: Optional[str] = None, limit: int = Query(100, ge=1, le=500), session: Session = Depends(get_pm_session), _perm: None = require_permission("core.read", "*", "core")):
    """List PM calendar events."""
    events = _svc(session).list_calendar_events(project_id=project_id, start_date=start_date, end_date=end_date, limit=limit)
    return {"events": events, "total": len(events)}


@router.post("/reports/{report_id}/execute")
def execute_report(report_id: str, report_format: str = Query("json"), session: Session = Depends(get_pm_session), _perm: None = require_permission("core.write", "*", "core")):
    """Execute a PM report."""
    return _svc(session).execute_report(report_id=report_id, report_format=report_format)
