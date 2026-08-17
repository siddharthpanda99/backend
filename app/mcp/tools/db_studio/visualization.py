"""Module 27 — Visualization, Dashboards & Reporting MCP tools."""
from typing import Any, Dict, List, Optional
from app.mcp.fastmcp_compat import FastMCP

from common_lib.modules.db_studio.visualization.service import VizDashboardService

svc = VizDashboardService()


def register_visualization_tools(mcp: FastMCP):
    """Register all visualization tools with the MCP server."""

    @mcp.tool()
    async def viz_create_dashboard(
        name: str, description: Optional[str] = None,
        theme: str = "light", is_public: bool = False,
    ) -> Dict[str, Any]:
        """Create a new dashboard"""
        from common_lib.modules.db_studio.visualization.schemas import DashboardCreate
        req = DashboardCreate(name=name, description=description, theme=theme, is_public=is_public)
        result = svc.create_dashboard(req)
        return result.model_dump()

    @mcp.tool()
    async def viz_get_dashboard(dashboard_id: str) -> Optional[Dict[str, Any]]:
        """Get a dashboard by ID"""
        result = svc.get_dashboard(dashboard_id)
        return result.model_dump() if result else None

    @mcp.tool()
    async def viz_list_dashboards(
        is_favorite: Optional[bool] = None,
        workspace_id: Optional[str] = None,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """List dashboards with optional filters"""
        items, total = svc.list_dashboards(
            is_favorite=is_favorite, workspace_id=workspace_id, limit=limit,
        )
        return {"total": total, "items": [i.model_dump() for i in items]}

    @mcp.tool()
    async def viz_delete_dashboard(dashboard_id: str) -> Dict[str, bool]:
        """Delete a dashboard and all its widgets"""
        ok = svc.delete_dashboard(dashboard_id)
        return {"ok": ok}

    @mcp.tool()
    async def viz_add_widget(
        dashboard_id: str, widget_type: str, title: str,
        chart_type: Optional[str] = None,
        width: int = 4, height: int = 4,
    ) -> Dict[str, Any]:
        """Add a widget to a dashboard"""
        from common_lib.modules.db_studio.visualization.schemas import WidgetCreate
        req = WidgetCreate(
            dashboard_id=dashboard_id, widget_type=widget_type,
            chart_type=chart_type, title=title, width=width, height=height,
        )
        result = svc.create_widget(req)
        return result.model_dump()

    @mcp.tool()
    async def viz_list_widgets(dashboard_id: str) -> List[Dict[str, Any]]:
        """List all widgets for a dashboard"""
        results = svc.list_widgets(dashboard_id)
        return [r.model_dump() for r in results]

    @mcp.tool()
    async def viz_create_report(
        name: str, report_type: str = "pdf",
        dashboard_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a report"""
        from common_lib.modules.db_studio.visualization.schemas import ReportCreate
        req = ReportCreate(name=name, report_type=report_type, dashboard_id=dashboard_id)
        result = svc.create_report(req)
        return result.model_dump()

    @mcp.tool()
    async def viz_list_reports(
        report_type: Optional[str] = None,
        dashboard_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List reports with optional filters"""
        results = svc.list_reports(report_type=report_type, dashboard_id=dashboard_id)
        return [r.model_dump() for r in results]

    @mcp.tool()
    async def viz_create_schedule(
        dashboard_id: str, schedule_type: str = "daily",
        format: str = "pdf",
    ) -> Dict[str, Any]:
        """Create a report schedule for a dashboard"""
        from common_lib.modules.db_studio.visualization.schemas import ReportScheduleCreate
        req = ReportScheduleCreate(dashboard_id=dashboard_id, schedule_type=schedule_type, format=format)
        result = svc.create_schedule(req)
        return result.model_dump()

    @mcp.tool()
    async def viz_list_schedules(dashboard_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List report schedules"""
        results = svc.list_schedules(dashboard_id=dashboard_id)
        return [r.model_dump() for r in results]

    @mcp.tool()
    async def viz_get_dashboard_stats() -> Dict[str, Any]:
        """Get visualization dashboard with aggregated stats"""
        dash = svc.get_dashboard_stats()
        return dash.model_dump()
