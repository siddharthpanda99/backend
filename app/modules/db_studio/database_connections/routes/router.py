"""Enhanced REST API routes for the Database Connection Manager (UDS Module 01).

Prefix: /api/v1/databases
"""

import logging
from typing import Any, Dict, Optional, List

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session

from common_lib.modules.integration.adapters.database_adapter import get_db_port
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
    DbConfigProfileService,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pydantic schemas for config-profile endpoints (inline — keeps surface small)
# ---------------------------------------------------------------------------


class ConfigProfileCreate(BaseModel):
    name: str
    display_name: str
    description: Optional[str] = None
    db_type: str
    config_json: Dict[str, Any]


class ConfigProfileUpdate(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    config_json: Optional[Dict[str, Any]] = None


class ConfigProfileClone(BaseModel):
    new_name: str
    new_display_name: str


router = APIRouter()
svc = DatabaseConnectionService()
profile_svc = DbConfigProfileService()


def _get_session():
    """Return a SQLModel session using the platform's shared engine."""
    return Session(get_db_port().get_engine())


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
# Schema Inspection  (optional ?connection_id — defaults to nexus_db)
# ═══════════════════════════════════════════════════════════════════════════


@router.get("/schema/tables", response_model=List[TableInfo])
def schema_tables(connection_id: Optional[str] = Query(None)):
    return svc.get_tables(connection_id)


@router.get("/schema/views")
def schema_views(connection_id: Optional[str] = Query(None)):
    return svc.get_views(connection_id)


@router.get("/schema/functions")
def schema_functions(connection_id: Optional[str] = Query(None)):
    return svc.get_functions(connection_id)


@router.get("/schema/indexes")
def schema_indexes(connection_id: Optional[str] = Query(None)):
    return svc.get_indexes(connection_id)


@router.get("/schema/constraints")
def schema_constraints(connection_id: Optional[str] = Query(None)):
    return svc.get_constraints(connection_id)


@router.get("/schema/triggers")
def schema_triggers(connection_id: Optional[str] = Query(None)):
    return svc.get_triggers(connection_id)


@router.get("/schema/enums")
def schema_enums(connection_id: Optional[str] = Query(None)):
    return svc.get_enums(connection_id)


@router.get("/schema/schemas")
def schema_schemas(connection_id: Optional[str] = Query(None)):
    return svc.get_schemas(connection_id)


@router.get("/schema/table-detail")
def schema_table_detail(
    connection_id: Optional[str] = Query(None),
    schema: str = Query(...),
    table: str = Query(...),
):
    result = svc.get_table_detail(connection_id, schema, table)
    if result is None:
        raise HTTPException(status_code=404, detail="Table not found")
    return result


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


# ═══════════════════════════════════════════════════════════════════════════
# Config Profiles  (/config-profiles/*)
# ═══════════════════════════════════════════════════════════════════════════


@router.get("/config-profiles")
def list_config_profiles(
    db_type: Optional[str] = Query(
        None, description="Filter by DB type (e.g. 'postgres')"
    ),
    is_system: Optional[bool] = Query(
        None, description="True = system profiles only, False = custom only"
    ),
    search: Optional[str] = Query(None),
):
    """List all available config profiles."""
    with _get_session() as session:
        profiles = profile_svc.list_profiles(
            session, db_type=db_type, is_system=is_system, search=search
        )
        return [
            {
                "id": p.id,
                "name": p.name,
                "display_name": p.display_name,
                "description": p.description,
                "db_type": p.db_type,
                "config_json": p.config_json,
                "is_system": p.is_system,
                "created_at": p.created_at,
                "updated_at": p.updated_at,
            }
            for p in profiles
        ]


@router.get("/config-profiles/{pid}")
def get_config_profile(pid: str):
    """Get a single config profile by ID."""
    with _get_session() as session:
        profile = profile_svc.get_profile(session, pid)
        if not profile:
            raise HTTPException(
                status_code=404, detail=f"Config profile '{pid}' not found"
            )
        return {
            "id": profile.id,
            "name": profile.name,
            "display_name": profile.display_name,
            "description": profile.description,
            "db_type": profile.db_type,
            "config_json": profile.config_json,
            "is_system": profile.is_system,
            "created_at": profile.created_at,
            "updated_at": profile.updated_at,
        }


@router.post("/config-profiles", status_code=201)
def create_config_profile(req: ConfigProfileCreate):
    """Create a new custom (user-owned) config profile."""
    with _get_session() as session:
        profile = profile_svc.create_profile(
            session=session,
            name=req.name,
            display_name=req.display_name,
            db_type=req.db_type,
            config_json=req.config_json,
            description=req.description,
        )
        return {"id": profile.id, "name": profile.name, "is_system": profile.is_system}


@router.put("/config-profiles/{pid}")
def update_config_profile(pid: str, req: ConfigProfileUpdate):
    """Update a custom config profile. System profiles are read-only."""
    with _get_session() as session:
        try:
            updated = profile_svc.update_profile(
                session=session,
                profile_id=pid,
                display_name=req.display_name,
                description=req.description,
                config_json=req.config_json,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        if not updated:
            raise HTTPException(
                status_code=404, detail=f"Config profile '{pid}' not found"
            )
        return {"id": updated.id, "updated_at": updated.updated_at}


@router.post("/config-profiles/{pid}/clone", status_code=201)
def clone_config_profile(pid: str, req: ConfigProfileClone):
    """Clone any profile into a new user-owned profile."""
    with _get_session() as session:
        try:
            cloned = profile_svc.clone_profile(
                session=session,
                profile_id=pid,
                new_name=req.new_name,
                new_display_name=req.new_display_name,
            )
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        return {"id": cloned.id, "name": cloned.name}


@router.delete("/config-profiles/{pid}")
def delete_config_profile(pid: str):
    """Delete a custom config profile. System profiles cannot be deleted."""
    with _get_session() as session:
        try:
            deleted = profile_svc.delete_profile(session, pid)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        if not deleted:
            raise HTTPException(
                status_code=404, detail=f"Config profile '{pid}' not found"
            )
        return {"ok": True}


# ── Connection ↔ Profile linking ──────────────────────────────────────────


@router.post("/connections/{conn_id}/config-profile/{pid}")
def apply_config_profile_to_connection(
    conn_id: str,
    pid: str,
    merge: bool = Query(
        True, description="Merge profile config on top of existing extra_params"
    ),
):
    """Attach a config profile to a connection and merge its settings into extra_params."""
    with _get_session() as session:
        try:
            conn = profile_svc.apply_to_connection(
                session=session, profile_id=pid, conn_id=conn_id, merge=merge
            )
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        return {
            "ok": True,
            "connection_id": conn.id,
            "config_profile_id": conn.config_profile_id,
        }


@router.delete("/connections/{conn_id}/config-profile")
def detach_config_profile_from_connection(conn_id: str):
    """Detach the config profile link from a connection (extra_params kept as-is)."""
    with _get_session() as session:
        try:
            conn = profile_svc.detach_from_connection(session=session, conn_id=conn_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        return {"ok": True, "connection_id": conn.id, "config_profile_id": None}


# ═══════════════════════════════════════════════════════════════════════════
# Config Visibility  (/config-profiles/visibility/*)
# ═══════════════════════════════════════════════════════════════════════════


@router.get("/config-profiles/visibility/{db_type}")
def get_config_visibility(db_type: str):
    """Get the admin-defined visibility config for a db_type.

    Returns which config sections/fields appear at which tier (basic /
    advanced / expert) and which are hidden entirely.  Used by the
    admin UI to show all sections with toggle controls, and by the
    user-facing profile-creation UI to render only visible fields.
    """
    with _get_session() as session:
        vis = profile_svc.get_visibility(session, db_type)
        return {
            "db_type": vis.db_type,
            "visibility": vis.visibility,
            "updated_at": vis.updated_at,
        }


class VisibilityUpdate(BaseModel):
    visibility: Dict[str, Any]


@router.put("/config-profiles/visibility/{db_type}")
def update_config_visibility(db_type: str, req: VisibilityUpdate):
    """Admin-only: update the visibility config for a db_type."""
    with _get_session() as session:
        vis = profile_svc.update_visibility(session, db_type, req.visibility)
        return {"ok": True, "db_type": vis.db_type, "updated_at": vis.updated_at}


# ═══════════════════════════════════════════════════════════════════════════
# Platform DB Auto-Connect
# ═══════════════════════════════════════════════════════════════════════════


@router.post("/connections/platform")
def ensure_platform_connection():
    """Auto-register the platform's own PostgreSQL as a connection.

    Reads from config.ini [Database] and creates a connection record
    if one doesn't already exist for this host+port+database.
    """
    conn = svc.ensure_platform_connection()
    if not conn:
        raise HTTPException(
            status_code=500,
            detail="Failed to auto-register platform DB. Check config.ini [Database]."
        )
    return conn
