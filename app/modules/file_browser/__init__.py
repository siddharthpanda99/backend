"""file_browser API routes — extends file_system with directories + enhanced operations."""

from fastapi import APIRouter, Query, HTTPException, UploadFile, File, Form, Body
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
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
    get_versions_legacy,
    restore_version_legacy,
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
    compress_files,
    extract_archive,
    create_version,
    list_versions,
    restore_file_version,
    get_version_download_path,
    create_alert,
    get_user_alerts,
    mark_alert_read,
    log_event,
    get_event_logs,
    generate_file_preview,
    get_file_preview,
    get_preview_image,
    bulk_move,
    bulk_copy,
    bulk_tag,
    bulk_delete,
    search_files_fulltext,
    search_by_content,
    register_webhook,
    list_webhooks,
    delete_webhook,
    trigger_on_file_event,
    generate_signed_url,
    verify_signed_url,
    revoke_signed_url,
    add_file_comment,
    get_file_comments,
    lock_file,
    unlock_file,
    get_file_lock,
    encrypt_file,
    decrypt_file,
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
    """Move multiple files to a target folder."""
    result = bulk_move(body.ids, body.target_folder_id)
    return ApiResponse(
        success=result["failed"] == 0, name=f"{result['success']}/{len(body.ids)} moved"
    )


@router.post("/files/bulk-copy", response_model=ApiResponse)
async def bulk_copy_handler(body: BulkMoveRequest):
    """Copy multiple files to a target folder."""
    result = bulk_copy(body.ids, body.target_folder_id)
    return ApiResponse(
        success=result["failed"] == 0,
        name=f"{result['success']}/{len(body.ids)} copied",
    )


class BulkTagRequest(BaseModel):
    ids: List[str]
    tags: List[str]


@router.post("/files/bulk-tag", response_model=ApiResponse)
async def bulk_tag_handler(body: BulkTagRequest):
    """Add tags to multiple files."""
    result = bulk_tag(body.ids, body.tags)
    return ApiResponse(
        success=result["failed"] == 0,
        name=f"{result['success']}/{len(body.ids)} tagged",
    )


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


@router.get("/upload/{session_id}/status")
async def get_upload_status_handler(session_id: str):
    """Get upload session status with chunk info."""
    from common_lib.modules.file_browser.service import get_upload_session_status

    status = get_upload_session_status(session_id)
    if not status:
        raise HTTPException(status_code=404, detail="Session not found")
    return status


@router.get("/upload/{session_id}/resume")
async def resume_upload_handler(session_id: str):
    """Get info about which chunks are missing for resuming."""
    from common_lib.modules.file_browser.service import resume_upload_session

    return resume_upload_session(session_id)


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
    include_content: bool = Query(True),
    page: int = Query(1),
    limit: int = Query(50),
):
    """Search files by name or content."""
    types = file_types.split(",") if file_types else None
    return search_files_fulltext(q, folder_id, types, include_content, page, limit)


@router.get("/search/content")
async def search_content_handler(
    q: str = Query(...),
    folder_id: Optional[str] = Query(None),
    page: int = Query(1),
    limit: int = Query(50),
):
    """Search only file content."""
    return search_by_content(q, folder_id, page, limit)


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


@router.delete("/files/{file_id}/tags", response_model=FileNodeResponse)
async def remove_tags_handler(file_id: str, body: RemoveTagsRequest):
    """Remove tags from a file."""
    result = remove_tags(file_id, body.tags)
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


# ── Tags & Labels ─────────────────────────────────────────────────────────────


@router.get("/tags")
async def get_tags_handler():
    """Get all tags."""
    from common_lib.modules.file_browser.service import get_all_tags

    return get_all_tags()


@router.get("/labels")
async def get_labels_handler():
    """Get all labels."""
    from common_lib.modules.file_browser.service import get_all_labels

    return get_all_labels()


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


# ── S3-Style Compression ────────────────────────────────────────────────────────


class CompressRequest(BaseModel):
    file_ids: List[str]
    output_name: str


@router.post("/files/compress")
async def compress_files_handler(request: CompressRequest):
    """Compress multiple files into a zip archive."""
    result = compress_files(request.file_ids, request.output_name)
    if not result:
        raise HTTPException(status_code=500, detail="Compression failed")
    return result


@router.post("/files/{file_id}/extract")
async def extract_archive_handler(file_id: str, folder_id: Optional[str] = None):
    """Extract a zip archive."""
    result = extract_archive(file_id, folder_id)
    return {"extracted_files": result, "count": len(result)}


# ── S3-Style Versioning ─────────────────────────────────────────────────────────


@router.post("/files/{file_id}/versions")
async def create_version_handler(file_id: str):
    """Create a new version of a file."""
    version = create_version(file_id)
    if not version:
        raise HTTPException(status_code=404, detail="File not found")
    return version


@router.get("/files/{file_id}/versions")
async def list_versions_handler(file_id: str):
    """List all versions of a file."""
    versions = list_versions(file_id)
    return versions
    """Create a new version of a file."""
    version = create_version(file_id)
    if not version:
        raise HTTPException(status_code=404, detail="File not found")
    return version


@router.get("/files/{file_id}/versions")
async def list_versions_handler(file_id: str):
    """List all versions of a file."""
    versions = list_versions(file_id)
    return versions


@router.post("/files/{file_id}/versions/{version_id}/restore")
async def restore_version_handler(file_id: str, version_id: str):
    """Restore a file to a specific version."""
    result = restore_file_version(file_id, version_id)
    if not result:
        raise HTTPException(status_code=404, detail="Version not found")
    return result


# ── S3-Style Alerts & Events ─────────────────────────────────────────────────────────


class CreateAlertRequest(BaseModel):
    title: str
    message: str
    alert_type: str = "info"
    severity: str = "info"
    source_type: Optional[str] = None
    source_id: Optional[str] = None
    action_url: Optional[str] = None


@router.post("/alerts")
async def create_alert_handler(user_id: str, request: CreateAlertRequest):
    """Create an alert for a user."""
    alert = create_alert(
        user_id=user_id,
        title=request.title,
        message=request.message,
        alert_type=request.alert_type,
        severity=request.severity,
        source_type=request.source_type,
        source_id=request.source_id,
        action_url=request.action_url,
    )
    return alert


@router.get("/alerts/{user_id}")
async def get_user_alerts_handler(user_id: str, unread_only: bool = False):
    """Get alerts for a user."""
    alerts = get_user_alerts(user_id, unread_only)
    return alerts


@router.post("/alerts/{alert_id}/read")
async def mark_alert_read_handler(alert_id: str):
    """Mark an alert as read."""
    mark_alert_read(alert_id)
    return {"success": True}


@router.get("/events")
async def get_event_logs_handler(
    event_type: Optional[str] = None,
    source_id: Optional[str] = None,
    limit: int = 100,
):
    """Get event logs."""
    logs = get_event_logs(event_type, source_id, limit)
    return logs


# ── File Preview/Viewer ─────────────────────────────────────────────────────────


@router.post("/files/{file_id}/preview")
async def generate_preview_handler(file_id: str, preview_type: str = "thumbnail"):
    """Generate a preview for a file."""
    preview = generate_file_preview(file_id, preview_type)
    if not preview:
        raise HTTPException(
            status_code=404, detail="File not found or preview generation failed"
        )
    return preview


@router.get("/files/{file_id}/preview")
async def get_preview_handler(file_id: str):
    """Get preview info for a file."""
    preview = get_file_preview(file_id)
    if not preview:
        raise HTTPException(status_code=404, detail="No preview found")
    return preview


@router.get("/files/{file_id}/preview/image")
async def get_preview_image_handler(file_id: str):
    """Get the actual preview image."""
    image_data = get_preview_image(file_id)
    if not image_data:
        raise HTTPException(status_code=404, detail="No preview image found")
    return Response(content=image_data, media_type="image/jpeg")


# ── S3-Style Versioning ─────────────────────────────────────────────────────────


@router.post("/files/{file_id}/versions")
async def create_version_handler(file_id: str):
    """Create a new version of a file."""
    version = create_version(file_id)
    if not version:
        raise HTTPException(status_code=404, detail="File not found")
    return version


@router.get("/files/{file_id}/versions")
async def list_versions_handler(file_id: str):
    """List all versions of a file."""
    versions = list_versions(file_id)
    return versions


@router.post("/files/{file_id}/versions/{version_id}/restore")
async def restore_version_handler(file_id: str, version_id: str):
    """Restore a file to a specific version."""
    result = restore_file_version(file_id, version_id)
    if not result:
        raise HTTPException(status_code=404, detail="Version not found")
    return result


@router.get("/versions/{version_id}/download")
async def download_version_handler(version_id: str):
    """Download a specific version of a file."""
    from fastapi.responses import FileResponse

    ver = get_version_download_path(version_id)
    if not ver or not ver.get("storage_path"):
        raise HTTPException(status_code=404, detail="Version not found")
    return FileResponse(
        path=ver["storage_path"],
        filename=f"v{ver['version_number']}_{ver.get('file_id', 'file')}",
    )


# ── Webhooks ───────────────────────────────────────────────────────────────


class WebhookRequest(BaseModel):
    url: str
    events: List[str]
    name: Optional[str] = None
    secret: Optional[str] = None


@router.post("/webhooks", response_model=ApiResponse)
async def register_webhook_handler(request: WebhookRequest):
    result = register_webhook(request.url, request.events, request.name, request.secret)
    return ApiResponse(success=True, name=result["id"])


@router.get("/webhooks")
async def list_webhooks_handler():
    return list_webhooks()


@router.delete("/webhooks/{webhook_id}", response_model=ApiResponse)
async def delete_webhook_handler(webhook_id: str):
    delete_webhook(webhook_id)
    return ApiResponse(success=True)


# ── Pre-signed URLs ───────────────────────────────────────────────────────


class SignedUrlRequest(BaseModel):
    expires_seconds: int = 3600
    user_id: Optional[str] = None


@router.post("/files/{file_id}/signed-url", response_model=ApiResponse)
async def generate_signed_url_handler(file_id: str, request: SignedUrlRequest):
    """Generate a pre-signed URL for secure file download."""
    result = generate_signed_url(file_id, request.expires_seconds, request.user_id)
    return ApiResponse(success=True, name=result["url"], id=result["token"])


@router.get("/signed/{token}")
async def verify_signed_url_handler(token: str):
    """Verify and access a pre-signed URL."""
    result = verify_signed_url(token)
    if not result:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return result


@router.delete("/signed/{token}", response_model=ApiResponse)
async def revoke_signed_url_handler(token: str):
    """Revoke a pre-signed URL."""
    revoke_signed_url(token)
    return ApiResponse(success=True)


# ── File Comments ───────────────────────────────────────────────────────────────


class CommentRequest(BaseModel):
    content: str
    user_id: str = "anonymous"


@router.post("/files/{file_id}/comments")
async def add_comment_handler(file_id: str, request: CommentRequest):
    from common_lib.modules.file_browser.service import add_file_comment

    result = add_file_comment(file_id, request.user_id, request.content)
    return result


@router.get("/files/{file_id}/comments")
async def list_comments_handler(file_id: str):
    from common_lib.modules.file_browser.service import get_file_comments

    return get_file_comments(file_id)


# ── File Locking ───────────────────────────────────────────────────────────────


class LockRequest(BaseModel):
    user_id: str = "anonymous"
    reason: Optional[str] = None


@router.post("/files/{file_id}/lock")
async def lock_file_handler(file_id: str, request: LockRequest):
    from common_lib.modules.file_browser.service import lock_file

    return lock_file(file_id, request.user_id, request.reason)


@router.delete("/files/{file_id}/lock")
async def unlock_file_handler(file_id: str, user_id: str = "anonymous"):
    from common_lib.modules.file_browser.service import unlock_file

    return unlock_file(file_id, user_id)


@router.get("/files/{file_id}/lock")
async def get_lock_handler(file_id: str):
    from common_lib.modules.file_browser.service import get_file_lock

    result = get_file_lock(file_id)
    if not result:
        return {"locked": False}
    return {"locked": True, **result}


# ── File Encryption ─────────────────────────────────────────────────────────────


@router.post("/files/{file_id}/encrypt")
async def encrypt_file_handler(file_id: str):
    from common_lib.modules.file_browser.service import encrypt_file

    result = encrypt_file(file_id)
    if not result:
        raise HTTPException(status_code=404, detail="File not found")
    return result


@router.post("/files/{file_id}/decrypt")
async def decrypt_file_handler(file_id: str):
    from common_lib.modules.file_browser.service import decrypt_file

    result = decrypt_file(file_id)
    if not result:
        raise HTTPException(status_code=404, detail="File not found")
    return result
