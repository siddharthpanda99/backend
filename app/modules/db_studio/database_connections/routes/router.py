"""Enhanced REST API routes for the Database Connection Manager (UDS Module 01).

Prefix: /api/v1/databases
"""

import logging
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query

from common_lib.modules.db_studio.database_connections import (
    DatabaseConnectionService,
    DatabaseConnectionCreate,
    DatabaseConnectionUpdate,
    ConnectionListResponse,
    ConnectionTestResult,
    TableInfo,
    CollectionInfo,
    WorkspaceCreate,
    WorkspaceUpdate,
    WorkspaceOut,
    FolderCreate,
    FolderOut,
    TagCreate,
    TagOut,
    HealthHistoryOut,
    AuditLogOut,
)

logger = logging.getLogger(__name__)

router = APIRouter()
svc = DatabaseConnectionService()


# ═══════════════════════════════════════════════════════════════════════════
# Connections
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/connections", response_model=ConnectionListResponse)
def list_connections(
    workspace_id: Optional[str] = Query(None),
    environment: Optional[str] = Query(None),
    db_type: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    include_archived: bool = Query(False),
):
    return svc.list_connections(
        workspace_id=workspace_id,
        environment=environment,
        db_type=db_type,
        search=search,
        include_archived=include_archived,
    )


@router.get("/connections/{conn_id}")
def get_connection(conn_id: str):
    conn = svc.get_connection(conn_id)
    if not conn:
        raise HTTPException(status_code=404, detail=f"Connection '{conn_id}' not found")
    return conn


@router.post("/connections", status_code=201)
def create_connection(req: DatabaseConnectionCreate):
    return svc.create_connection(req)


@router.put("/connections/{conn_id}")
def update_connection(conn_id: str, req: DatabaseConnectionUpdate):
    updated = svc.update_connection(conn_id, req)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Connection '{conn_id}' not found")
    return updated


@router.delete("/connections/{conn_id}")
def delete_connection(conn_id: str):
    if not svc.delete_connection(conn_id):
        raise HTTPException(status_code=404, detail=f"Connection '{conn_id}' not found")
    return {"ok": True}


@router.post("/connections/{conn_id}/archive")
def archive_connection(conn_id: str):
    if not svc.archive_connection(conn_id):
        raise HTTPException(status_code=404, detail=f"Connection '{conn_id}' not found")
    return {"ok": True}


@router.post("/connections/{conn_id}/favorite")
def toggle_favorite(conn_id: str):
    conn = svc.toggle_favorite(conn_id)
    if not conn:
        raise HTTPException(status_code=404, detail=f"Connection '{conn_id}' not found")
    return conn


@router.post("/connections/{conn_id}/test", response_model=ConnectionTestResult)
def test_connection(conn_id: str):
    return svc.test_connection(conn_id)


@router.get("/connections/{conn_id}/tables", response_model=List[TableInfo])
def get_tables(conn_id: str):
    return svc.get_tables(conn_id)


@router.get("/connections/{conn_id}/collections", response_model=List[CollectionInfo])
def get_collections(conn_id: str):
    return svc.get_collections(conn_id)


# ═══════════════════════════════════════════════════════════════════════════
# Health History
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/connections/{conn_id}/health", response_model=List[HealthHistoryOut])
def get_health_history(conn_id: str, limit: int = Query(20)):
    return svc.get_health_history(conn_id, limit=limit)


# ═══════════════════════════════════════════════════════════════════════════
# Audit Log
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/audit-log", response_model=List[AuditLogOut])
def get_audit_log(connection_id: Optional[str] = Query(None), limit: int = Query(50)):
    return svc.get_audit_log(connection_id=connection_id, limit=limit)


# ═══════════════════════════════════════════════════════════════════════════
# Workspaces
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/workspaces", response_model=List[WorkspaceOut])
def list_workspaces():
    return svc.list_workspaces()


@router.post("/workspaces", status_code=201, response_model=WorkspaceOut)
def create_workspace(req: WorkspaceCreate):
    return svc.create_workspace(req)


@router.put("/workspaces/{wid}", response_model=WorkspaceOut)
def update_workspace(wid: str, req: WorkspaceUpdate):
    updated = svc.update_workspace(wid, req)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Workspace '{wid}' not found")
    return updated


@router.delete("/workspaces/{wid}")
def delete_workspace(wid: str):
    if not svc.delete_workspace(wid):
        raise HTTPException(status_code=404, detail=f"Workspace '{wid}' not found")
    return {"ok": True}


# ═══════════════════════════════════════════════════════════════════════════
# Folders
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/folders", response_model=List[FolderOut])
def list_folders(workspace_id: Optional[str] = Query(None)):
    return svc.list_folders(workspace_id=workspace_id)


@router.post("/folders", status_code=201, response_model=FolderOut)
def create_folder(req: FolderCreate):
    return svc.create_folder(req)


@router.delete("/folders/{fid}")
def delete_folder(fid: str):
    if not svc.delete_folder(fid):
        raise HTTPException(status_code=404, detail=f"Folder '{fid}' not found")
    return {"ok": True}


# ═══════════════════════════════════════════════════════════════════════════
# Tags
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/tags", response_model=List[TagOut])
def list_tags():
    return svc.list_tags()


@router.post("/tags", status_code=201, response_model=TagOut)
def create_tag(req: TagCreate):
    return svc.create_tag(req)


@router.delete("/tags/{tid}")
def delete_tag(tid: str):
    if not svc.delete_tag(tid):
        raise HTTPException(status_code=404, detail=f"Tag '{tid}' not found")
    return {"ok": True}


__all__ = ["router"]
