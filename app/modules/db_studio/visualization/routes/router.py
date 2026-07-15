"""Module 27 — Visualization, Dashboards & Reporting routes (thin wrappers)."""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException

from common_lib.modules.db_studio.visualization.service import VizDashboardService
from common_lib.modules.db_studio.visualization.schemas import (
    DashboardCreate, DashboardUpdate, DashboardOut, DashboardVersionOut,
    WidgetCreate, WidgetUpdate, WidgetOut, WidgetConfigOut,
    ReportCreate, ReportOut,
    ReportScheduleCreate, ReportScheduleOut,
    DashboardPermissionOut, VisualizationUsageOut,
    VizDashboardOut,
)

router = APIRouter(tags=["UDS — Visualization, Dashboards & Reporting"])
svc = VizDashboardService()


# ── Dashboards ─────────────────────────────────────────────────

@router.post("/dashboards", response_model=DashboardOut)
def create_dashboard(body: DashboardCreate):
    return svc.create_dashboard(body)

@router.get("/dashboards/{dashboard_id}", response_model=Optional[DashboardOut])
def get_dashboard(dashboard_id: str):
    result = svc.get_dashboard(dashboard_id)
    if not result:
        raise HTTPException(404, "Dashboard not found")
    return result

@router.get("/dashboards", response_model=Dict[str, Any])
def list_dashboards(
    is_favorite: Optional[bool] = None,
    workspace_id: Optional[str] = None,
    limit: int = 50,
):
    items, total = svc.list_dashboards(
        is_favorite=is_favorite, workspace_id=workspace_id, limit=limit,
    )
    return {"total": total, "items": items}

@router.put("/dashboards/{dashboard_id}", response_model=Optional[DashboardOut])
def update_dashboard(dashboard_id: str, body: DashboardUpdate):
    result = svc.update_dashboard(dashboard_id, body)
    if not result:
        raise HTTPException(404, "Dashboard not found")
    return result

@router.delete("/dashboards/{dashboard_id}")
def delete_dashboard(dashboard_id: str):
    if not svc.delete_dashboard(dashboard_id):
        raise HTTPException(404, "Dashboard not found")
    return {"ok": True}


# ── Dashboard Versions ─────────────────────────────────────────

@router.post("/dashboards/{dashboard_id}/versions", response_model=DashboardVersionOut)
def create_version(dashboard_id: str):
    result = svc.create_version(dashboard_id)
    if not result:
        raise HTTPException(404, "Dashboard not found")
    return result

@router.get("/dashboards/{dashboard_id}/versions", response_model=List[DashboardVersionOut])
def list_versions(dashboard_id: str):
    return svc.list_versions(dashboard_id)


# ── Widgets ────────────────────────────────────────────────────

@router.post("/widgets", response_model=WidgetOut)
def create_widget(body: WidgetCreate):
    return svc.create_widget(body)

@router.put("/widgets/{widget_id}", response_model=Optional[WidgetOut])
def update_widget(widget_id: str, body: WidgetUpdate):
    result = svc.update_widget(widget_id, body)
    if not result:
        raise HTTPException(404, "Widget not found")
    return result

@router.get("/dashboards/{dashboard_id}/widgets", response_model=List[WidgetOut])
def list_widgets(dashboard_id: str):
    return svc.list_widgets(dashboard_id)

@router.delete("/widgets/{widget_id}")
def delete_widget(widget_id: str):
    if not svc.delete_widget(widget_id):
        raise HTTPException(404, "Widget not found")
    return {"ok": True}


# ── Widget Configs ─────────────────────────────────────────────

@router.get("/widget-configs", response_model=List[WidgetConfigOut])
def list_widget_configs():
    return svc.list_widget_configs()


# ── Reports ────────────────────────────────────────────────────

@router.post("/reports", response_model=ReportOut)
def create_report(body: ReportCreate):
    return svc.create_report(body)

@router.get("/reports", response_model=List[ReportOut])
def list_reports(report_type: Optional[str] = None, dashboard_id: Optional[str] = None):
    return svc.list_reports(report_type=report_type, dashboard_id=dashboard_id)

@router.delete("/reports/{report_id}")
def delete_report(report_id: str):
    if not svc.delete_report(report_id):
        raise HTTPException(404, "Report not found")
    return {"ok": True}


# ── Schedules ──────────────────────────────────────────────────

@router.post("/schedules", response_model=ReportScheduleOut)
def create_schedule(body: ReportScheduleCreate):
    return svc.create_schedule(body)

@router.get("/schedules", response_model=List[ReportScheduleOut])
def list_schedules(dashboard_id: Optional[str] = None):
    return svc.list_schedules(dashboard_id=dashboard_id)

@router.delete("/schedules/{schedule_id}")
def delete_schedule(schedule_id: str):
    if not svc.delete_schedule(schedule_id):
        raise HTTPException(404, "Schedule not found")
    return {"ok": True}


# ── Permissions ────────────────────────────────────────────────

@router.get("/dashboards/{dashboard_id}/permissions", response_model=List[DashboardPermissionOut])
def list_permissions(dashboard_id: str):
    return svc.list_permissions(dashboard_id)

@router.post("/dashboards/{dashboard_id}/permissions/{user_id}", response_model=DashboardPermissionOut)
def grant_permission(dashboard_id: str, user_id: str, permission: str = "view"):
    return svc.grant_permission(dashboard_id, user_id, permission)

@router.delete("/permissions/{permission_id}")
def revoke_permission(permission_id: str):
    if not svc.revoke_permission(permission_id):
        raise HTTPException(404, "Permission not found")
    return {"ok": True}


# ── Usage ──────────────────────────────────────────────────────

@router.post("/usage", response_model=VisualizationUsageOut)
def track_usage(dashboard_id: Optional[str] = None, action: str = "view", user_id: Optional[str] = None):
    return svc.track_usage(dashboard_id, action, user_id)

@router.get("/usage", response_model=List[VisualizationUsageOut])
def list_usage(dashboard_id: Optional[str] = None, limit: int = 50):
    return svc.list_usage(dashboard_id=dashboard_id, limit=limit)


# ── Dashboard Stats ────────────────────────────────────────────

@router.get("/dashboard/stats", response_model=VizDashboardOut)
def get_dashboard_stats():
    return svc.get_dashboard_stats()


# ── Seed ───────────────────────────────────────────────────────

@router.post("/seed")
def seed_visualization():
    count = svc.seed_defaults()
    return {"seeded": count}
