"""
PM Dashboard & Widget Routes — Full CRUD for dashboards and widgets.

Endpoints:
- Dashboards: GET/POST /dashboards, GET/PUT/DELETE /dashboards/{id}
- Widgets: GET/POST /dashboards/{id}/widgets, GET/PUT/DELETE /widgets/{id}
- Widget Data: GET /widgets/{id}/data

RBAC permissions: dashboard.read, dashboard.create, dashboard.update, dashboard.delete
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlmodel import Session

from app.modules.auth.dependencies import require_permission
from app.modules.project_management.field_security_deps import (
    filter_single_response,
    filter_list_response,
    strip_field_security_metadata,
)
from common_lib.modules.project_management.schemas import (
    DashboardCreate,
    DashboardUpdate,
    WidgetCreate,
    WidgetUpdate,
    CustomReportCreate,
    CustomReportUpdate,
)


def _get_session():
    from common_lib.modules.integration.adapters.database_adapter import get_db_port

    engine = get_db_port().get_engine()
    return Session(engine)


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboards", tags=["project_management", "dashboards"])


# ===========================================================================
# Dashboard CRUD
# ===========================================================================


@router.get("")
def list_dashboards(
    request: Request,
    project_id: Optional[str] = Query(None, description="Filter by project ID"),
    session: Session = Depends(_get_session),
    _perm: None = require_permission("dashboard.read", "*", "dashboard"),
):
    """List all dashboards, optionally filtered by project."""
    from common_lib.modules.project_management.dashboard.service import DashboardService

    svc = DashboardService(session=session)
    dashboards = svc.list_dashboards()
    if project_id:
        dashboards = [d for d in dashboards if d.project_id == project_id]
    items = [d.model_dump() for d in dashboards]
    items = filter_list_response(
        request, session, "dashboard", items, project_id=project_id
    )
    return {
        "dashboards": items,
        "total": len(items),
    }


@router.get("/{dashboard_id}")
def get_dashboard(
    request: Request,
    dashboard_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("dashboard.read", "*", "dashboard"),
):
    """Get a single dashboard by ID with its widgets."""
    from common_lib.modules.project_management.dashboard.service import DashboardService

    svc = DashboardService(session=session)
    dashboard = svc.get_dashboard(dashboard_id)
    if not dashboard:
        raise HTTPException(
            status_code=404, detail=f"Dashboard {dashboard_id} not found"
        )

    # Include widgets
    widgets = svc.list_widgets(dashboard_id)
    data = {
        **dashboard.model_dump(),
        "widgets": [w.model_dump() for w in widgets],
    }
    data = filter_single_response(
        request, session, "dashboard", data, project_id=dashboard.project_id
    )
    return strip_field_security_metadata(data)


@router.post("", status_code=201)
def create_dashboard(
    data: DashboardCreate,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("dashboard.create", "*", "dashboard"),
):
    """Create a new dashboard."""
    from common_lib.modules.project_management.schemas import DashboardCreate
    from common_lib.modules.project_management.dashboard.service import DashboardService

    svc = DashboardService(session=session)
    dashboard = svc.create_dashboard(data)
    return dashboard.model_dump()


@router.put("/{dashboard_id}")
def update_dashboard(
    dashboard_id: str,
    data: DashboardUpdate,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("dashboard.update", "*", "dashboard"),
):
    """Update a dashboard."""
    from common_lib.modules.project_management.schemas import DashboardUpdate
    from common_lib.modules.project_management.dashboard.service import DashboardService

    svc = DashboardService(session=session)
    dashboard = svc.update_dashboard(dashboard_id, data)
    if not dashboard:
        raise HTTPException(
            status_code=404, detail=f"Dashboard {dashboard_id} not found"
        )
    return dashboard.model_dump()


@router.delete("/{dashboard_id}")
def delete_dashboard(
    dashboard_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("dashboard.delete", "*", "dashboard"),
):
    """Delete a dashboard and all its widgets."""
    from common_lib.modules.project_management.dashboard.service import DashboardService

    svc = DashboardService(session=session)
    success = svc.delete_dashboard(dashboard_id)
    if not success:
        raise HTTPException(
            status_code=404, detail=f"Dashboard {dashboard_id} not found"
        )
    return {"success": True, "dashboard_id": dashboard_id}


# ===========================================================================
# Widget CRUD (nested under dashboards)
# ===========================================================================


@router.get("/{dashboard_id}/widgets")
def list_widgets(
    request: Request,
    dashboard_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("dashboard.read", "*", "dashboard"),
):
    """List all widgets in a dashboard."""
    from common_lib.modules.project_management.dashboard.service import DashboardService

    svc = DashboardService(session=session)

    # Verify dashboard exists
    dashboard = svc.get_dashboard(dashboard_id)
    if not dashboard:
        raise HTTPException(
            status_code=404, detail=f"Dashboard {dashboard_id} not found"
        )

    widgets = svc.list_widgets(dashboard_id)
    items = [w.model_dump() for w in widgets]
    items = filter_list_response(
        request, session, "dashboard", items, project_id=dashboard.project_id
    )
    return {
        "widgets": items,
        "total": len(items),
    }


@router.post("/{dashboard_id}/widgets", status_code=201)
def create_widget(
    dashboard_id: str,
    data: WidgetCreate,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("dashboard.create", "*", "dashboard"),
):
    """Create a new widget in a dashboard."""
    from common_lib.modules.project_management.schemas import WidgetCreate
    from common_lib.modules.project_management.dashboard.service import DashboardService

    svc = DashboardService(session=session)

    # Verify dashboard exists
    dashboard = svc.get_dashboard(dashboard_id)
    if not dashboard:
        raise HTTPException(
            status_code=404, detail=f"Dashboard {dashboard_id} not found"
        )

    widget = svc.create_widget(dashboard_id, data)
    return widget.model_dump()


@router.put("/widgets/{widget_id}")
def update_widget(
    widget_id: str,
    data: WidgetUpdate,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("dashboard.update", "*", "dashboard"),
):
    """Update a widget."""
    from common_lib.modules.project_management.schemas import WidgetUpdate
    from common_lib.modules.project_management.dashboard.service import DashboardService

    svc = DashboardService(session=session)
    widget = svc.update_widget(widget_id, data)
    if not widget:
        raise HTTPException(status_code=404, detail=f"Widget {widget_id} not found")
    return widget.model_dump()


@router.delete("/widgets/{widget_id}")
def delete_widget(
    widget_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("dashboard.delete", "*", "dashboard"),
):
    """Delete a widget."""
    from common_lib.modules.project_management.dashboard.service import DashboardService

    svc = DashboardService(session=session)
    success = svc.delete_widget(widget_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Widget {widget_id} not found")
    return {"success": True, "widget_id": widget_id}


# ===========================================================================
# Widget Data Execution
# ===========================================================================


@router.get("/widgets/{widget_id}/data")
def get_widget_data(
    widget_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("dashboard.read", "*", "dashboard"),
):
    """Execute a widget's data query and return live results."""
    from common_lib.modules.project_management.dashboard.service import DashboardService

    svc = DashboardService(session=session)
    data = svc.get_widget_data(widget_id)
    if data is None:
        raise HTTPException(status_code=404, detail=f"Widget {widget_id} not found")
    return data


# ===========================================================================
# Widget CRUD (top-level convenience endpoints)
# ===========================================================================


@router.get("/widgets/{widget_id}")
def get_widget(
    request: Request,
    widget_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("dashboard.read", "*", "dashboard"),
):
    """Get a single widget by ID."""
    from common_lib.modules.project_management.dashboard.service import DashboardService

    svc = DashboardService(session=session)
    widget = svc.get_widget(widget_id)
    if not widget:
        raise HTTPException(status_code=404, detail=f"Widget {widget_id} not found")
    data = widget.model_dump()
    data = filter_single_response(request, session, "dashboard", data)
    return strip_field_security_metadata(data)


# ===========================================================================
# Custom Reports (20.05)
# ===========================================================================


@router.get("/reports")
def list_reports(
    project_id: Optional[str] = Query(None),
    session: Session = Depends(_get_session),
    _perm: None = require_permission("dashboard.read", "*", "dashboard"),
):
    """List custom reports for a project."""
    from common_lib.modules.project_management.dashboard.service import DashboardService

    svc = DashboardService(session=session)
    reports = svc.list_custom_reports(project_id)
    return {"reports": [r.model_dump() for r in reports], "total": len(reports)}


@router.get("/reports/{report_id}")
def get_report(
    report_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("dashboard.read", "*", "dashboard"),
):
    """Get a custom report by ID."""
    from common_lib.modules.project_management.dashboard.service import DashboardService

    svc = DashboardService(session=session)
    report = svc.get_custom_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail=f"Report {report_id} not found")
    return report.model_dump()


@router.post("/reports", status_code=201)
def create_report(
    data: CustomReportCreate,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("dashboard.create", "*", "dashboard"),
):
    """Create a custom report with filters, grouping, and aggregation."""
    from common_lib.modules.project_management.schemas import CustomReportCreate
    from common_lib.modules.project_management.dashboard.service import DashboardService

    svc = DashboardService(session=session)
    report = svc.create_custom_report(data)
    return report.model_dump()


@router.put("/reports/{report_id}")
def update_report(
    report_id: str,
    data: CustomReportUpdate,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("dashboard.update", "*", "dashboard"),
):
    """Update a custom report."""
    from common_lib.modules.project_management.schemas import CustomReportUpdate
    from common_lib.modules.project_management.dashboard.service import DashboardService

    svc = DashboardService(session=session)
    report = svc.update_custom_report(report_id, data)
    if not report:
        raise HTTPException(status_code=404, detail=f"Report {report_id} not found")
    return report.model_dump()


@router.delete("/reports/{report_id}")
def delete_report(
    report_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("dashboard.delete", "*", "dashboard"),
):
    """Delete a custom report."""
    from common_lib.modules.project_management.dashboard.service import DashboardService

    svc = DashboardService(session=session)
    if not svc.delete_custom_report(report_id):
        raise HTTPException(status_code=404, detail=f"Report {report_id} not found")
    return {"success": True, "report_id": report_id}


# ===========================================================================
# Report Execution & Export (20.05 / 20.07)
# ===========================================================================


@router.post("/reports/{report_id}/execute")
def execute_report(
    report_id: str,
    format: str = Query("json", pattern="^(json|csv)$"),
    session: Session = Depends(_get_session),
    _perm: None = require_permission("dashboard.read", "*", "dashboard"),
):
    """Execute a custom report and return data. Supports json and csv formats."""
    from common_lib.modules.project_management.dashboard.service import DashboardService

    svc = DashboardService(session=session)
    result = svc.execute_custom_report(report_id, fmt=format)
    if not result:
        raise HTTPException(status_code=404, detail=f"Report {report_id} not found")
    return result


@router.get("/reports/{report_id}/export")
def export_report(
    report_id: str,
    format: str = Query("csv", pattern="^(json|csv)$"),
    session: Session = Depends(_get_session),
    _perm: None = require_permission("dashboard.read", "*", "dashboard"),
):
    """Export a custom report in the specified format."""
    from common_lib.modules.project_management.dashboard.service import DashboardService

    svc = DashboardService(session=session)
    result = svc.execute_custom_report(report_id, fmt=format)
    if not result:
        raise HTTPException(status_code=404, detail=f"Report {report_id} not found")
    if format == "csv":
        from fastapi.responses import PlainTextResponse

        return PlainTextResponse(
            content=result["data"],
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="{result["name"]}.csv"'
            },
        )
    return result


# ===========================================================================
# Scheduled Report Execution (20.06)
# ===========================================================================


@router.post("/schedules/{schedule_id}/execute")
def execute_schedule(
    schedule_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("dashboard.update", "*", "dashboard"),
):
    """Execute a scheduled report immediately."""
    from common_lib.modules.project_management.dashboard.service import DashboardService

    svc = DashboardService(session=session)
    result = svc.execute_scheduled_report(schedule_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Schedule {schedule_id} not found")
    return result


@router.post("/schedules/run-due")
def run_due_schedules(
    session: Session = Depends(_get_session),
    _perm: None = require_permission("dashboard.update", "*", "dashboard"),
):
    """Execute all due scheduled reports."""
    from common_lib.modules.project_management.dashboard.service import DashboardService

    svc = DashboardService(session=session)
    results = svc.run_all_due_schedules()
    return {"executed": len(results), "results": results}


# ===========================================================================
# Analytics Aggregation (20.08)
# ===========================================================================


@router.get("/analytics/{project_id}")
def get_project_analytics(
    project_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("dashboard.read", "*", "dashboard"),
):
    """Get aggregated analytics for a project."""
    from common_lib.modules.project_management.dashboard.service import DashboardService

    svc = DashboardService(session=session)
    return svc.get_project_analytics(project_id)


@router.get("/analytics/sprints/{sprint_id}")
def get_sprint_analytics(
    sprint_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("dashboard.read", "*", "dashboard"),
):
    """Get aggregated analytics for a sprint."""
    from common_lib.modules.project_management.dashboard.service import DashboardService

    svc = DashboardService(session=session)
    return svc.get_sprint_analytics(sprint_id)


@router.get("/analytics/portfolios/{portfolio_id}")
def get_portfolio_analytics(
    portfolio_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("dashboard.read", "*", "dashboard"),
):
    """Get aggregated analytics for a portfolio across all projects."""
    from common_lib.modules.project_management.portfolio.service import PortfolioService

    svc = PortfolioService(session=session)
    portfolio = svc.get_portfolio(portfolio_id)
    if not portfolio:
        raise HTTPException(
            status_code=404, detail=f"Portfolio {portfolio_id} not found"
        )
    from common_lib.modules.project_management.dashboard.service import DashboardService

    dash_svc = DashboardService(session=session)
    return dash_svc.get_portfolio_analytics(portfolio)
