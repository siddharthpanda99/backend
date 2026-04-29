"""file_browser API routes — extends file_system with directories + enhanced operations."""

from fastapi import APIRouter, Query, HTTPException, UploadFile, File, Form, Body
from fastapi.responses import FileResponse
from typing import Optional, List
import json

from common_lib.modules.file_browser.service import (
    list_files,
    get_file,
    create_folder,
    delete_file,
    rename_file,
    move_file,
    copy_file,
    star_file,
    trash_file,
    add_tags,
    remove_tags,
    set_label,
    upload_file,
    search_files,
    get_folder_tree,
    get_storage_stats,
    download_file,
    get_versions,
    restore_version,
    copy_folder,
    create_share_link,
    get_share_links,
    revoke_share_link,
    get_share_link_by_token,
    create_upload_session,
    get_upload_session,
    update_upload_chunk,
    complete_upload_session,
    get_all_tags,
    get_all_labels,
    init as _init,
    _row_to_file,
    _engine,
)
from common_lib.modules.file_browser.types import (
    FileListResponse,
    FileNodeResponse,
    DirectoryNode,
    CreateFolderRequest,
    RenameRequest,
    MoveRequest,
    StarRequest,
    BulkDeleteRequest,
    BulkMoveRequest,
    SearchRequest,
    StorageStatsResponse,
    FolderTreeNode,
    ApiResponse,
    BreadcrumbItem,
    FileVersion,
    Tag,
    Label,
    Bookmark,
    AddTagsRequest,
    AddLabelRequest,
    RemoveTagsRequest,
    ShareLinkRequest,
    ShareLinkResponse,
    ShareLink,
    CopyFolderRequest,
    VersionItem,
    UploadSessionCreate,
    UploadSessionResponse,
    ChunkUploadRequest,
    TagItem,
    LabelItem,
)

router = APIRouter(prefix="/file-browser", tags=["file-browser"])


# Initialize storage dirs on first request
def _ensure_init():
    try:
        _init()
    except Exception:
        pass  # already initialized or no-op


# ── Files ───────────────────────────────────────────────────────────────────


@router.get("/files", response_model=FileListResponse)
async def list_files_handler(
    folder_id: Optional[str] = Query(None),
    page: int = Query(1),
    limit: int = Query(50),
    sort_by: str = Query("date"),
    sort_order: str = Query("desc"),
    type: Optional[str] = Query(None, alias="type"),
    date_range: Optional[str] = Query(None),
    tags: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
):
    """List files in a folder with pagination, sorting, and filtering."""
    _ensure_init()
    tag_list = tags.split(",") if tags else None
    return list_files(
        folder_id=folder_id,
        page=page,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
        file_type=type,
        date_range=date_range,
        tags=tag_list,
        search=search,
    )


@router.get("/files/{file_id}", response_model=FileNodeResponse)
async def get_file_handler(file_id: str):
    """Get single file details."""
    result = get_file(file_id)
    if not result:
        raise HTTPException(status_code=404, detail="File not found")
    return result


@router.get("/files/{file_id}/breadcrumbs")
async def breadcrumbs_from_file_handler(file_id: str) -> List[BreadcrumbItem]:
    """Build breadcrumb path from file's folder up to root."""
    if file_id == "root":
        return [{"id": "root", "name": "My Files"}]
    f = get_file(file_id)
    if not f:
        raise HTTPException(status_code=404, detail="File not found")
    if not f.directory_id:
        return [{"id": None, "name": "My Files"}]
    if f.directory_id and not f.directory_id.startswith("/"):
        return [{"id": None, "name": "My Files"}]
    if f.directory_id:
        return [{"id": None, "name": "My Files"}, {"id": f.id, "name": f.name}]
    return [{"id": None, "name": "My Files"}]


@router.post("/files/{file_id}/rename", response_model=FileNodeResponse)
async def rename_handler(file_id: str, body: RenameRequest):
    result = rename_file(file_id, body.new_name)
    if not result:
        raise HTTPException(status_code=404, detail="File not found")
    return result


@router.post("/files/{file_id}/move", response_model=FileNodeResponse)
async def move_handler(file_id: str, body: MoveRequest):
    result = move_file(file_id, body.target_folder_id)
    if not result:
        raise HTTPException(status_code=404, detail="File not found")
    return result


@router.post("/files/{file_id}/copy", response_model=FileNodeResponse)
async def copy_handler(file_id: str, body: MoveRequest):
    result = copy_file(file_id, body.target_folder_id)
    if not result:
        raise HTTPException(status_code=404, detail="File not found")
    return result


@router.post("/files/{file_id}/star", response_model=FileNodeResponse)
async def star_handler(file_id: str, body: StarRequest):
    result = star_file(file_id, body.starred)
    if not result:
        raise HTTPException(status_code=404, detail="File not found")
    return result


@router.post("/files/{file_id}/unstar", response_model=FileNodeResponse)
async def unstar_handler(file_id: str):
    """Unstar a file (set starred=False)."""
    result = star_file(file_id, False)
    if not result:
        raise HTTPException(status_code=404, detail="File not found")
    return result


@router.post("/files/bulk-delete", response_model=ApiResponse)
async def bulk_delete_handler(body: BulkDeleteRequest):
    deleted = sum(delete_file(id, body.permanent) for id in body.ids)
    return ApiResponse(success=True, name=f"{deleted}/{len(body.ids)} deleted")


@router.post("/files/bulk-move", response_model=ApiResponse)
async def bulk_move_handler(body: BulkMoveRequest):
    moved = sum(1 for id in body.ids if move_file(id, body.target_folder_id))
    return ApiResponse(success=True, name=f"{moved}/{len(body.ids)} moved")


@router.delete("/files/{file_id}", response_model=ApiResponse)
async def delete_handler(file_id: str):
    ok = delete_file(file_id)
    if not ok:
        raise HTTPException(status_code=404, detail="File not found")
    return ApiResponse(success=True)


# ── Upload ──────────────────────────────────────────────────────────────────


@router.post("/files")
async def upload_handler(
    file: UploadFile = File(...),
    folder_id: Optional[str] = Form(None),
    user_id: Optional[str] = Form(None),
):
    """Upload a file. Returns upload result with id, name, size."""
    _ensure_init()
    data = await file.read()
    result = upload_file(data, file.filename, folder_id, user_id)
    return result


@router.post("/upload")
async def upload_alias_handler(
    file: UploadFile = File(...),
    folder_id: Optional[str] = Form(None),
):
    """Upload a file (alias for /files)."""
    _ensure_init()
    data = await file.read()
    result = upload_file(data, file.filename, folder_id, None)
    return result


# ── Folders ─────────────────────────────────────────────────────────────────


@router.post("/folders", response_model=ApiResponse)
async def create_folder_handler(body: CreateFolderRequest):
    """Create a new folder."""
    _ensure_init()
    result = create_folder(body.name, body.parent_id)
    return ApiResponse(**result)


@router.get("/folders/tree")
async def folder_tree_handler() -> List[FolderTreeNode]:
    """Get folder hierarchy as flat list with parent refs."""
    return get_folder_tree()


@router.get("/folders/root")
async def root_folder_handler() -> FileNodeResponse:
    """Get virtual root folder."""
    return FileNodeResponse(
        id="root",
        name="My Files",
        type="folder",
        size=0,
        size_bytes=0,
        mime_type=None,
        extension=None,
        folder_id=None,
        directory_id=None,
        path="/",
        storage_path=None,
        minio_key=None,
        checksum=None,
        is_folder=True,
        is_starred=False,
        is_pinned=False,
        is_trashed=False,
        is_deleted=False,
        child_count=0,
        created_at=None,
        updated_at=None,
    )


@router.get("/folders/breadcrumbs/{folder_id}")
async def breadcrumbs_handler(folder_id: str) -> List[BreadcrumbItem]:
    """Build breadcrumb path from folder up to root."""
    path = []
    current = folder_id
    visited = set()
    while current and current not in visited:
        visited.add(current)
        f = get_file(current)
        if not f or not f.is_folder:
            break
        path.append(BreadcrumbItem(id=current, name=f.name))
        current = f.directory_id or None
        if current and not current.startswith("/"):
            current = None
    path.reverse()
    return [{"id": None, "name": "My Files"}] + path


@router.get("/folders/{folder_id}", response_model=FileNodeResponse)
async def get_folder_handler(folder_id: str):
    """Get folder details by ID."""
    result = get_file(folder_id)
    if not result or not result.is_folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    return result


# ── Search ──────────────────────────────────────────────────────────────────


@router.get("/search")
async def search_handler(
    q: str = Query(...),
    folder_id: Optional[str] = Query(None),
    file_types: Optional[str] = Query(None),
    page: int = Query(1),
    limit: int = Query(50),
):
    """Search files by name or path."""
    types = file_types.split(",") if file_types else None
    return search_files(q, folder_id, types, page, limit)


# ── Storage ─────────────────────────────────────────────────────────────────


@router.get("/storage", response_model=StorageStatsResponse)
async def storage_handler():
    """Get storage usage statistics."""
    return get_storage_stats()


@router.get("/storage/stats", response_model=StorageStatsResponse)
async def storage_stats_handler():
    """Get storage usage statistics (alias for /storage)."""
    return get_storage_stats()


# ── Starred / Favorites ─────────────────────────────────────────────────────


@router.get("/starred")
async def starred_handler():
    """List starred files."""
    from sqlmodel import Session, text

    with Session(_engine()) as db:
        rows = (
            db.execute(
                text("""
                SELECT 
                    f.*,
                    (SELECT json_agg(t.name) FROM file_system.tags t 
                     JOIN file_system.file_tags ft ON t.id = ft.tag_id 
                     WHERE ft.file_id = f.id) as tags_list,
                    (SELECT l.name FROM file_system.labels l 
                     JOIN file_system.file_labels fl ON l.id = fl.label_id 
                     WHERE fl.file_id = f.id LIMIT 1) as label_name
                FROM file_system.files f
                WHERE f.is_starred = true 
                ORDER BY f.updated_at DESC 
                LIMIT 100
            """)
            )
            .mappings()
            .all()
        )

    return {"items": [_row_to_file(r) for r in rows], "total": len(rows)}


# ── Recents ────────────────────────────────────────────────────────────────


@router.get("/recent")
async def recent_handler(limit: int = Query(20)):
    """List recently modified files."""
    from sqlmodel import Session, text

    with Session(_engine()) as db:
        rows = (
            db.execute(
                text("""
                SELECT 
                    f.*,
                    (SELECT json_agg(t.name) FROM file_system.tags t 
                     JOIN file_system.file_tags ft ON t.id = ft.tag_id 
                     WHERE ft.file_id = f.id) as tags_list,
                    (SELECT l.name FROM file_system.labels l 
                     JOIN file_system.file_labels fl ON l.id = fl.label_id 
                     WHERE fl.file_id = f.id LIMIT 1) as label_name
                FROM file_system.files f
                ORDER BY f.updated_at DESC 
                LIMIT :limit
            """),
                {"limit": limit},
            )
            .mappings()
            .all()
        )
    return {"items": [_row_to_file(r) for r in rows], "total": len(rows)}


# ── Trash ──────────────────────────────────────────────────────────────────


@router.get("/trash")
async def list_trash_handler():
    """List trashed files."""
    from sqlmodel import Session, text

    with Session(_engine()) as db:
        rows = (
            db.execute(
                text("""
                SELECT 
                    f.*,
                    (SELECT json_agg(t.name) FROM file_system.tags t 
                     JOIN file_system.file_tags ft ON t.id = ft.tag_id 
                     WHERE ft.file_id = f.id) as tags_list,
                    (SELECT l.name FROM file_system.labels l 
                     JOIN file_system.file_labels fl ON l.id = fl.label_id 
                     WHERE fl.file_id = f.id LIMIT 1) as label_name
                FROM file_system.files f
                WHERE f.is_trashed = true 
                ORDER BY f.updated_at DESC
            """)
            )
            .mappings()
            .all()
        )
    return {"items": [_row_to_file(r) for r in rows], "total": len(rows)}


@router.post("/files/{file_id}/trash", response_model=FileNodeResponse)
async def trash_handler(file_id: str):
    """Move a file to trash."""
    result = trash_file(file_id, True)
    if not result:
        raise HTTPException(status_code=404, detail="File not found")
    return result


@router.post("/files/{file_id}/restore", response_model=FileNodeResponse)
async def restore_handler(file_id: str):
    """Restore a file from trash."""
    result = trash_file(file_id, False)
    if not result:
        raise HTTPException(status_code=404, detail="File not found")
    return result


@router.post("/files/{file_id}/tags", response_model=FileNodeResponse)
async def add_tags_handler(file_id: str, body: AddTagsRequest):
    """Add tags to a file."""
    result = add_tags(file_id, body.tags)
    if not result:
        raise HTTPException(status_code=404, detail="File not found")
    return result


@router.post("/files/{file_id}/label", response_model=FileNodeResponse)
async def set_label_handler(file_id: str, body: AddLabelRequest):
    """Set label for a file."""
    result = set_label(file_id, body.label)
    if not result:
        raise HTTPException(status_code=404, detail="File not found")
    return result


@router.get("/storage", response_model=StorageStatsResponse)
async def get_storage_stats_handler():
    """Get storage statistics."""
    _ensure_init()
    return get_storage_stats()


# ── Download ─────────────────────────────────────────────────────────────────


@router.get("/files/{file_id}/download")
async def download_handler(file_id: str):
    """Download a file."""
    from fastapi.responses import FileResponse

    result = download_file(file_id)
    if not result:
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path=result["path"],
        filename=result["name"],
        media_type=result.get("mime_type", "application/octet-stream"),
    )


# ── Remove Tags ───────────────────────────────────────────────────────────


@router.delete("/files/{file_id}/tags", response_model=FileNodeResponse)
async def remove_tags_handler(file_id: str, body: RemoveTagsRequest):
    """Remove tags from a file."""
    result = remove_tags(file_id, body.tags)
    if not result:
        raise HTTPException(status_code=404, detail="File not found")
    return result


# ── Versions ───────────────────────────────────────────────────────────────


@router.get("/files/{file_id}/versions")
async def versions_handler(file_id: str) -> List[VersionItem]:
    """Get version history for a file."""
    versions = get_versions(file_id)
    return [VersionItem(**v) for v in versions]


@router.post(
    "/files/{file_id}/versions/{version_id}/restore", response_model=FileNodeResponse
)
async def restore_version_handler(file_id: str, version_id: str):
    """Restore a specific version."""
    result = restore_version(file_id, version_id)
    if not result:
        raise HTTPException(status_code=404, detail="File or version not found")
    return result


# ── Copy Folder ───────────────────────────────────────────────────────────


@router.post("/folders/{folder_id}/copy", response_model=ApiResponse)
async def copy_folder_handler(folder_id: str, body: CopyFolderRequest):
    """Copy a folder recursively."""
    result = copy_folder(folder_id, body.target_folder_id, body.new_name)
    if not result.get("success", False):
        raise HTTPException(
            status_code=404, detail=result.get("error", "Folder not found")
        )
    return ApiResponse(**result)


# ── Share Links ───────────────────────────────────────────────────────────


@router.post("/files/{file_id}/share", response_model=ShareLinkResponse)
async def create_share_link_handler(file_id: str, body: ShareLinkRequest):
    """Create a share link for a file."""
    file = get_file(file_id)
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    result = create_share_link(file_id, body.access_level, body.expires_days)
    return ShareLinkResponse(**result)


@router.get("/files/{file_id}/shares")
async def list_share_links_handler(file_id: str) -> List[ShareLink]:
    """List share links for a file."""
    links = get_share_links(file_id)
    return [ShareLink(**l) for l in links]


@router.get("/shares")
async def list_all_share_links_handler() -> List[ShareLink]:
    """List all share links."""
    links = get_share_links()
    return [ShareLink(**l) for l in links]


@router.delete("/shares/{link_id}")
async def revoke_share_link_handler(link_id: str):
    """Revoke a share link."""
    revoke_share_link(link_id)
    return ApiResponse(success=True)


@router.get("/share/{token}")
async def get_shared_file_handler(token: str):
    """Get file info via share token."""
    info = get_share_link_by_token(token)
    if not info:
        raise HTTPException(status_code=404, detail="Share link invalid or expired")
    info["file_id"] = info.get("resource_id")
    return info


# ── Chunked Upload ─────────────────────────────────────────────────────────


@router.post("/upload/session", response_model=UploadSessionResponse)
async def create_upload_session_handler(body: UploadSessionCreate):
    """Create a chunked upload session."""
    session = create_upload_session(
        body.filename,
        body.total_size_bytes,
        body.mime_type,
        body.folder_id,
        None,
        body.chunk_size_bytes,
    )
    return UploadSessionResponse(**session)


@router.get("/upload/session/{session_id}")
async def get_upload_session_handler(session_id: str):
    """Get upload session status."""
    session = get_upload_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.post("/upload/chunk")
async def upload_chunk_handler(
    session_id: str = Form(...),
    chunk_index: int = Form(...),
    chunk: UploadFile = File(...),
):
    """Upload a chunk."""
    result = update_upload_chunk(session_id, chunk_index)
    return result


@router.post("/upload/session/{session_id}/complete")
async def complete_upload_handler(session_id: str, file_id: str):
    """Mark upload session as complete."""
    complete_upload_session(session_id, file_id)
    return ApiResponse(success=True)


# ── Tags & Labels ──────────────────────────────────────────────────────────


@router.get("/tags", response_model=List[TagItem])
async def list_tags_handler():
    """List all tags with usage count."""
    tags = get_all_tags()
    return [TagItem(**t) for t in tags]


@router.get("/labels", response_model=List[LabelItem])
async def list_labels_handler():
    """List all labels with usage count."""
    labels = get_all_labels()
    return [LabelItem(**l) for l in labels]
