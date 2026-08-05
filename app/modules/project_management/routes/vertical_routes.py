"""
Vertical Solutions API Routes.

Domain 30: Marketing (30.05), Construction (30.06), Vertical Dashboards (30.07).
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from app.modules.auth.dependencies import require_permission
from common_lib.modules.project_management.verticals.service import VerticalDashboardService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/verticals", tags=["project_management", "verticals"])


def _get_session():
    from common_lib.modules.integration.adapters.database_adapter import get_db_port
    engine = get_db_port().get_engine()
    return Session(engine)


@router.get("/dashboard/{project_id}")
def get_vertical_dashboard(project_id: str, session: Session = Depends(_get_session), _perm: None = require_permission("dashboard.read", "*", "dashboard")):
    """Get the correct vertical dashboard based on project type."""
    svc = VerticalDashboardService(session)
    dashboard = svc.get_vertical_dashboard(project_id)
    if "error" in dashboard:
        raise HTTPException(status_code=404, detail=dashboard["error"])
    return dashboard


@router.get("/marketing/{project_id}")
def get_marketing_dashboard(project_id: str, session: Session = Depends(_get_session), _perm: None = require_permission("dashboard.read", "*", "dashboard")):
    """Get a marketing project dashboard with campaign pipeline and channel metrics."""
    svc = VerticalDashboardService(session)
    dashboard = svc.get_marketing_dashboard(project_id)
    if "error" in dashboard:
        raise HTTPException(status_code=404, detail=dashboard["error"])
    return dashboard


@router.get("/construction/{project_id}")
def get_construction_dashboard(project_id: str, session: Session = Depends(_get_session), _perm: None = require_permission("dashboard.read", "*", "dashboard")):
    """Get a construction project dashboard with phase progress and safety metrics."""
    svc = VerticalDashboardService(session)
    dashboard = svc.get_construction_dashboard(project_id)
    if "error" in dashboard:
        raise HTTPException(status_code=404, detail=dashboard["error"])
    return dashboard
