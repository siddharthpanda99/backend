"""REST API routes for Data Browser & Grid Editor (UDS Module 04).

Prefix: /api/v1/data-browser
Thin wrapper — all logic in common_lib.modules.data_browser.service.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from common_lib.modules.db_studio.data_browser import (
    DataBrowserService,
    DataQueryRequest,
    DataQueryResponse,
    RowInsertRequest,
    RowUpdateRequest,
    RowDeleteRequest,
    BulkDeleteRequest,
    RowMutationResponse,
    EditSessionCreate,
    EditSessionOut,
    ChangeHistoryOut,
    SavedFilterCreate,
    SavedFilterOut,
    ColumnViewDef,
    SavedViewCreate,
    SavedViewOut,
    ExportRequest,
    ExportJobOut,
    RowPreviewRequest,
    RowPreviewResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()
svc = DataBrowserService()


# ═══════════════════════════════════════════════════════════════════════════
# Data Query / Browsing
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/query", response_model=DataQueryResponse)
def query_data(req: DataQueryRequest):
    """Fetch paginated, sortable, filterable data from a table."""
    return svc.query_data(req)


@router.post("/preview", response_model=RowPreviewResponse)
def preview_row(req: RowPreviewRequest):
    """Fetch a single row by primary key for inspection."""
    return svc.preview_row(req)


# ═══════════════════════════════════════════════════════════════════════════
# Row CRUD
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/rows", response_model=RowMutationResponse)
def insert_row(req: RowInsertRequest):
    """Insert a new row into a table."""
    return svc.insert_row(req)


@router.put("/rows", response_model=RowMutationResponse)
def update_row(req: RowUpdateRequest):
    """Update a row by primary key."""
    return svc.update_row(req)


@router.delete("/rows", response_model=RowMutationResponse)
def delete_row(req: RowDeleteRequest):
    """Delete a row by primary key."""
    return svc.delete_row(req)


@router.post("/rows/bulk-delete", response_model=RowMutationResponse)
def bulk_delete(req: BulkDeleteRequest):
    """Delete multiple rows by their primary keys."""
    return svc.bulk_delete(req)


# ═══════════════════════════════════════════════════════════════════════════
# Saved Filters
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/filters", response_model=List[SavedFilterOut])
def list_filters(connection_id: Optional[str] = Query(None), table: Optional[str] = Query(None)):
    """List saved filter presets."""
    return svc.list_saved_filters(connection_id=connection_id, table_name=table)


@router.post("/filters", status_code=201, response_model=SavedFilterOut)
def save_filter(req: SavedFilterCreate):
    """Save a filter preset."""
    return svc.save_filter(req)


@router.delete("/filters/{filter_id}")
def delete_filter(filter_id: str):
    if not svc.delete_saved_filter(filter_id):
        raise HTTPException(status_code=404, detail=f"Filter '{filter_id}' not found")
    return {"ok": True}


# ═══════════════════════════════════════════════════════════════════════════
# Saved Views
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/views", response_model=List[SavedViewOut])
def list_views(connection_id: Optional[str] = Query(None), table: Optional[str] = Query(None)):
    """List saved column layout presets."""
    return svc.list_saved_views(connection_id=connection_id, table_name=table)


@router.post("/views", status_code=201, response_model=SavedViewOut)
def save_view(req: SavedViewCreate):
    """Save a column layout view preset."""
    return svc.save_view(req)


@router.delete("/views/{view_id}")
def delete_view(view_id: str):
    if not svc.delete_saved_view(view_id):
        raise HTTPException(status_code=404, detail=f"View '{view_id}' not found")
    return {"ok": True}


# ═══════════════════════════════════════════════════════════════════════════
# Edit Sessions
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/edit-sessions", status_code=201, response_model=EditSessionOut)
def create_edit_session(req: EditSessionCreate):
    """Create a batch edit session."""
    return svc.create_edit_session(req)


@router.get("/edit-sessions", response_model=List[EditSessionOut])
def list_edit_sessions(connection_id: Optional[str] = Query(None)):
    """List edit sessions."""
    return svc.list_edit_sessions(connection_id=connection_id)


@router.post("/edit-sessions/{session_id}/commit")
def commit_edit_session(session_id: str):
    if not svc.commit_edit_session(session_id):
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found or already closed")
    return {"ok": True}


@router.post("/edit-sessions/{session_id}/rollback")
def rollback_edit_session(session_id: str):
    if not svc.rollback_edit_session(session_id):
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found or already closed")
    return {"ok": True}


# ═══════════════════════════════════════════════════════════════════════════
# Change History
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/change-history", response_model=List[ChangeHistoryOut])
def list_change_history(
    connection_id: Optional[str] = Query(None),
    table: Optional[str] = Query(None),
    session_id: Optional[str] = Query(None),
    limit: int = Query(50),
):
    """List data change history."""
    return svc.list_change_history(
        connection_id=connection_id, table_name=table,
        session_id=session_id, limit=limit,
    )


# ═══════════════════════════════════════════════════════════════════════════
# Export
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/export", response_model=ExportJobOut)
def export_data(req: ExportRequest):
    """Export table data (CSV, JSON, XLSX)."""
    return svc.export_data(req)


@router.get("/export-jobs", response_model=List[ExportJobOut])
def list_export_jobs(connection_id: Optional[str] = Query(None)):
    """List export jobs."""
    return svc.list_export_jobs(connection_id=connection_id)
