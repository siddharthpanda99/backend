"""Views, Boards, Calendar & Timeline REST routes — Domain 14."""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query

from app.modules.auth.dependencies import require_permission
from common_lib.modules.project_management.schemas import (
    TableViewConfigCreate, TableViewConfigUpdate,
)

router = APIRouter(prefix="/views", tags=["PM Views & Boards"])


# ===========================================================================
# Table View Configs (14.02)
# ===========================================================================

@router.get("/table-configs")
def list_table_configs(
    _perm: None = require_permission("view.read", "*", "view"),
    project_id: str = Query(...),
    user_id: Optional[str] = Query(None),
):
    """List table view configurations for a project."""
    from common_lib.modules.project_management.views.service import ViewsService
    configs = ViewsService.list_table_configs(project_id, user_id)
    return {"configs": [c.model_dump() for c in configs], "total": len(configs)}


@router.get("/table-configs/default")
def get_default_table_config(
    _perm: None = require_permission("view.read", "*", "view"),
    project_id: str = Query(...),
    user_id: Optional[str] = Query(None),
):
    """Get the default table view configuration."""
    from common_lib.modules.project_management.views.service import ViewsService
    config = ViewsService.get_default_config(project_id, user_id)
    if not config:
        raise HTTPException(status_code=404, detail="No default configuration found")
    return config.model_dump()


@router.get("/table-configs/{config_id}")
def get_table_config(config_id: str, _perm: None = require_permission("view.read", "*", "view")):
    """Get a table view configuration by ID."""
    from common_lib.modules.project_management.views.service import ViewsService
    config = ViewsService.get_table_config(config_id)
    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")
    return config.model_dump()


@router.post("/table-configs", status_code=201)
def create_table_config(
    data: TableViewConfigCreate,
    _perm: None = require_permission("view.create", "*", "view"),
):
    """Create a new table view configuration."""
    from common_lib.modules.project_management.views.service import ViewsService
    config = ViewsService.create_table_config(data)
    return config.model_dump()


@router.put("/table-configs/{config_id}")
def update_table_config(
    config_id: str,
    data: TableViewConfigUpdate,
    _perm: None = require_permission("view.update", "*", "view"),
):
    """Update a table view configuration."""
    from common_lib.modules.project_management.views.service import ViewsService
    config = ViewsService.update_table_config(config_id, data)
    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")
    return config.model_dump()


@router.delete("/table-configs/{config_id}")
def delete_table_config(config_id: str, _perm: None = require_permission("view.delete", "*", "view")):
    """Delete a table view configuration."""
    from common_lib.modules.project_management.views.service import ViewsService
    if not ViewsService.delete_table_config(config_id):
        raise HTTPException(status_code=404, detail="Configuration not found")
    return {"success": True, "config_id": config_id}


# ===========================================================================
# Calendar View (14.05)
# ===========================================================================

@router.get("/calendar")
def get_calendar_events(
    _perm: None = require_permission("view.read", "*", "view"),
    project_id: str = Query(...),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    include_sprints: bool = Query(True),
    include_releases: bool = Query(True),
    include_issues: bool = Query(True),
):
    """Get calendar events (issues, sprints, milestones) for a date range."""
    from common_lib.modules.project_management.views.service import ViewsService
    events = ViewsService.get_calendar_events(
        project_id, start_date, end_date,
        include_sprints, include_releases, include_issues,
    )
    return {"events": events, "total": len(events)}


# ===========================================================================
# Enhanced Timeline (14.06)
# ===========================================================================

@router.get("/timeline")
def get_enhanced_timeline(
    _perm: None = require_permission("view.read", "*", "view"),
    project_id: str = Query(...),
    zoom: str = Query("month"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    group_by: Optional[str] = Query(None),
):
    """Get enhanced timeline with zoom levels and date range filtering."""
    from common_lib.modules.project_management.views.service import ViewsService
    data = ViewsService.get_enhanced_timeline(
        project_id, zoom, start_date, end_date, group_by,
    )
    return data


# ===========================================================================
# Board Data with Swimlanes (14.03)
# ===========================================================================

@router.get("/board")
def get_board_data(
    _perm: None = require_permission("view.read", "*", "view"),
    project_id: str = Query(...),
    board_type: str = Query("kanban"),
    swimlane_by: Optional[str] = Query(None),
):
    """Get board data with columns, cards, and optional swimlanes."""
    from common_lib.modules.project_management.views.service import ViewsService
    data = ViewsService.get_board_data(project_id, board_type, swimlane_by)
    return data


# ===========================================================================
# Map View (14.07)
# ===========================================================================

@router.get("/map")
def get_map_view_data(
    _perm: None = require_permission("view.read", "*", "view"),
    project_id: str = Query(...),
    entity_type: str = Query("issue"),
):
    """Get location-tagged entities for map visualization."""
    from common_lib.modules.project_management.views.service import ViewsService
    items = ViewsService.get_map_view_data(project_id, entity_type)
    return {"items": items, "total": len(items)}
