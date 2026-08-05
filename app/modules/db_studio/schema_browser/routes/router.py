"""REST API routes for Metadata & Schema Explorer (UDS Module 03).

Prefix: /api/v1/schema-browser
Thin wrapper — all logic in common_lib.modules.schema_browser.service.
"""

import logging
import time
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from common_lib.modules.db_studio.schema_browser import (
    SchemaBrowserService,
    TreeBrowseRequest,
    TreeBrowseResponse,
    ObjectDetail,
    ObjectDetailRequest,
    SearchRequest,
    SearchResponse,
    CompareRequest,
    CompareResponse,
    SnapshotCreateRequest,
    SnapshotOut,
    DDLRequest,
    DDLResponse,
    FavoriteCreate,
    FavoriteOut,
    RecentObjectOut,
    CommentCreate,
    CommentUpdate,
    CommentOut,
    RefreshRequest,
    RefreshResponse,
    EnumType,
    EnumTypeDetail,
    EnumListResponse,
    TriggerInfo,
    TriggerListResponse,
    ViewDetail,
    ViewListResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()
svc = SchemaBrowserService()


# ═══════════════════════════════════════════════════════════════════════════
# Tree Browser
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/browse", response_model=TreeBrowseResponse)
def browse_schema(req: TreeBrowseRequest):
    """Browse the schema tree — root level returns schemas, drill down returns tables/columns."""
    return svc.browse(req)


@router.get("/browse", response_model=TreeBrowseResponse)
def browse_schema_get(
    connection_id: str = Query(...),
    parent_id: Optional[str] = Query(None),
    object_type: Optional[str] = Query(None),
    schema_name: Optional[str] = Query(None),
    refresh: bool = Query(False),
):
    """Browse the schema tree via GET query params."""
    req = TreeBrowseRequest(
        connection_id=connection_id,
        parent_id=parent_id,
        object_type=object_type,
        schema_name=schema_name,
        refresh=refresh,
    )
    return svc.browse(req)


# ═══════════════════════════════════════════════════════════════════════════
# Object Detail
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/object/detail", response_model=ObjectDetail)
def get_object_detail(req: ObjectDetailRequest):
    """Get detailed metadata for a schema object (table/view with columns, constraints, indexes)."""
    return svc.get_object_detail(req)


@router.get("/object/detail", response_model=ObjectDetail)
def get_object_detail_get(
    connection_id: str = Query(...),
    object_type: str = Query(...),
    schema_name: Optional[str] = Query(None),
    object_name: str = Query(...),
):
    """Get object detail via GET query params."""
    req = ObjectDetailRequest(
        connection_id=connection_id,
        object_type=object_type,
        schema_name=schema_name,
        object_name=object_name,
    )
    return svc.get_object_detail(req)


# ═══════════════════════════════════════════════════════════════════════════
# Search
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/search", response_model=SearchResponse)
def search_metadata(req: SearchRequest):
    """Search across cached metadata objects."""
    return svc.search(req)


# ═══════════════════════════════════════════════════════════════════════════
# Refresh / Cache
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/refresh", response_model=RefreshResponse)
def refresh_metadata(req: RefreshRequest):
    """Refresh cached metadata from live database."""
    return svc.refresh_metadata(req)


# ═══════════════════════════════════════════════════════════════════════════
# Favorites
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/favorites", response_model=List[FavoriteOut])
def list_favorites(connection_id: Optional[str] = Query(None)):
    """List favorite/pinned objects."""
    return svc.list_favorites(connection_id=connection_id)


@router.post("/favorites", status_code=201, response_model=FavoriteOut)
def add_favorite(req: FavoriteCreate):
    """Add an object to favorites."""
    return svc.add_favorite(req)


@router.delete("/favorites/{favorite_id}")
def remove_favorite(favorite_id: str):
    """Remove a favorite."""
    if not svc.remove_favorite(favorite_id):
        raise HTTPException(status_code=404, detail=f"Favorite '{favorite_id}' not found")
    return {"ok": True}


# ═══════════════════════════════════════════════════════════════════════════
# Recent Objects
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/recent", response_model=List[RecentObjectOut])
def list_recent(connection_id: Optional[str] = Query(None), limit: int = Query(20)):
    """List recently viewed objects."""
    return svc.list_recent(connection_id=connection_id, limit=limit)


@router.post("/recent")
def record_view(connection_id: str = Query(...), object_type: str = Query(...), object_path: str = Query(...)):
    """Record that an object was viewed."""
    svc.record_view(connection_id=connection_id, object_type=object_type, object_path=object_path)
    return {"ok": True}


# ═══════════════════════════════════════════════════════════════════════════
# Schema Comparison & Snapshots
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/snapshots", status_code=201, response_model=SnapshotOut)
def create_snapshot(req: SnapshotCreateRequest):
    """Create a point-in-time schema snapshot."""
    try:
        return svc.create_snapshot(req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/snapshots", response_model=List[SnapshotOut])
def list_snapshots(connection_id: Optional[str] = Query(None)):
    """List schema snapshots."""
    return svc.list_snapshots(connection_id=connection_id)


@router.delete("/snapshots/{snapshot_id}")
def delete_snapshot(snapshot_id: str):
    """Delete a schema snapshot."""
    if not svc.delete_snapshot(snapshot_id):
        raise HTTPException(status_code=404, detail=f"Snapshot '{snapshot_id}' not found")
    return {"ok": True}


@router.post("/compare", response_model=CompareResponse)
def compare_schemas(req: CompareRequest):
    """Compare two schemas or compare against a snapshot."""
    return svc.compare(req)


# ═══════════════════════════════════════════════════════════════════════════
# DDL Generation
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/ddl", response_model=DDLResponse)
def generate_ddl(req: DDLRequest):
    """Generate DDL for a schema object based on its metadata."""
    return svc.generate_ddl(req)


# ═══════════════════════════════════════════════════════════════════════════
# Comments / Data Dictionary
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/comments", response_model=List[CommentOut])
def list_comments(connection_id: Optional[str] = Query(None), object_type: Optional[str] = Query(None)):
    """List documentation comments for schema objects."""
    return svc.list_comments(connection_id=connection_id, object_type=object_type)


@router.post("/comments", status_code=201, response_model=CommentOut)
def add_comment(req: CommentCreate):
    """Add a documentation comment to a schema object."""
    return svc.add_comment(req)


@router.put("/comments/{comment_id}", response_model=CommentOut)
def update_comment(comment_id: str, req: CommentUpdate):
    """Update a documentation comment."""
    result = svc.update_comment(comment_id, req)
    if not result:
        raise HTTPException(status_code=404, detail=f"Comment '{comment_id}' not found")
    return result


@router.delete("/comments/{comment_id}")
def delete_comment(comment_id: str):
    """Delete a documentation comment."""
    if not svc.delete_comment(comment_id):
        raise HTTPException(status_code=404, detail=f"Comment '{comment_id}' not found")
    return {"ok": True}


# ═══════════════════════════════════════════════════════════════════════════
# ENUM Types
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/enums", response_model=EnumListResponse)
def list_enums(connection_id: str, schema: str = Query("public")):
    """List all ENUM types in a schema."""
    start = time.time()
    enums = svc.get_enums(connection_id, schema)
    return EnumListResponse(
        enums=enums, total=len(enums),
        connection_id=connection_id,
        duration_ms=round((time.time() - start) * 1000, 2),
    )


@router.get("/enums/{enum_name}", response_model=EnumTypeDetail)
def get_enum_detail(connection_id: str, schema: str = Query("public"), enum_name: str = ...):
    """Get detailed info for a single ENUM type."""
    result = svc.get_enum_detail(connection_id, schema, enum_name)
    if not result:
        raise HTTPException(status_code=404, detail=f"Enum '{enum_name}' not found")
    return result


# ═══════════════════════════════════════════════════════════════════════════
# Triggers
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/triggers", response_model=TriggerListResponse)
def list_triggers(connection_id: str, schema: str = Query("public")):
    """List all triggers in a schema."""
    start = time.time()
    triggers = svc.get_triggers(connection_id, schema)
    return TriggerListResponse(
        triggers=triggers, total=len(triggers),
        connection_id=connection_id,
        duration_ms=round((time.time() - start) * 1000, 2),
    )


# ═══════════════════════════════════════════════════════════════════════════
# Views
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/views", response_model=ViewListResponse)
def list_views(connection_id: str, schema: str = Query("public")):
    """List all views in a schema."""
    start = time.time()
    views = svc.get_views(connection_id, schema)
    return ViewListResponse(
        views=views, total=len(views),
        connection_id=connection_id,
        duration_ms=round((time.time() - start) * 1000, 2),
    )
