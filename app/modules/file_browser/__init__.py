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
    upload_file,
    search_files,
    get_folder_tree,
    get_storage_stats,
    init as _init,
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
):
    """List files in a folder with pagination."""
    _ensure_init()
    return list_files(folder_id, page, limit, sort_by, sort_order)


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


@router.post("/files/{file_id}/rename", response_model=ApiResponse)
async def rename_handler(file_id: str, body: RenameRequest):
    ok = rename_file(file_id, body.new_name)
    if not ok:
        raise HTTPException(status_code=404, detail="File not found")
    return ApiResponse(success=True)


@router.post("/files/{file_id}/move", response_model=ApiResponse)
async def move_handler(file_id: str, body: MoveRequest):
    ok = move_file(file_id, body.target_folder_id)
    if not ok:
        raise HTTPException(status_code=404, detail="File not found")
    return ApiResponse(success=True)


@router.post("/files/{file_id}/copy", response_model=ApiResponse)
async def copy_handler(file_id: str, body: MoveRequest):
    ok = copy_file(file_id, body.target_folder_id)
    if not ok:
        raise HTTPException(status_code=404, detail="File not found")
    return ApiResponse(success=True)


@router.post("/files/{file_id}/star", response_model=ApiResponse)
async def star_handler(file_id: str, body: StarRequest):
    ok = star_file(file_id, body.starred)
    if not ok:
        raise HTTPException(status_code=404, detail="File not found")
    return ApiResponse(success=True)


@router.post("/files/{file_id}/unstar", response_model=ApiResponse)
async def unstar_handler(file_id: str):
    """Unstar a file (set starred=False)."""
    ok = star_file(file_id, False)
    if not ok:
        raise HTTPException(status_code=404, detail="File not found")
    return ApiResponse(success=True)


@router.post("/files/bulk-delete", response_model=ApiResponse)
async def bulk_delete_handler(body: BulkDeleteRequest):
    deleted = sum(delete_file(id, body.permanent) for id in body.ids)
    return ApiResponse(success=True, name=f"{deleted}/{len(body.ids)} deleted")


@router.post("/files/bulk-move", response_model=ApiResponse)
async def bulk_move_handler(body: BulkMoveRequest):
    moved = sum(move_file(id, body.target_folder_id) for id in body.ids)
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
    # Re-use list with is_starred filter via raw query
    from sqlmodel import Session, text
    from common_lib.modules.file_browser.service import _engine

    with Session(_engine()) as db:
        rows = db.execute(
            text(
                "SELECT * FROM file_system.files WHERE is_starred = true ORDER BY updated_at DESC LIMIT 100"
            )
        ).fetchall()
    from common_lib.modules.file_browser.service import _row_to_file

    return {"items": [_row_to_file(r) for r in rows], "total": len(rows)}


# ── Recents ────────────────────────────────────────────────────────────────


@router.get("/recent")
async def recent_handler(limit: int = Query(20)):
    """List recently modified files."""
    from sqlmodel import Session, text
    from common_lib.modules.file_browser.service import _engine, _row_to_file

    with Session(_engine()) as db:
        rows = db.execute(
            text(
                "SELECT * FROM file_system.files ORDER BY updated_at DESC LIMIT :limit"
            ),
            {"limit": limit},
        ).fetchall()
    return {"items": [_row_to_file(r) for r in rows], "total": len(rows)}


# ── Trash ──────────────────────────────────────────────────────────────────


@router.get("/trash")
async def trash_handler():
    """List trashed files."""
    from sqlmodel import Session, text
    from common_lib.modules.file_browser.service import _engine, _row_to_file

    with Session(_engine()) as db:
        rows = db.execute(
            text(
                "SELECT * FROM file_system.files WHERE is_trashed = true ORDER BY updated_at DESC"
            )
        ).fetchall()
    return {"items": [_row_to_file(r) for r in rows], "total": len(rows)}


@router.post("/files/{file_id}/restore", response_model=ApiResponse)
async def restore_handler(file_id: str):
    """Restore a file from trash."""
    from sqlmodel import Session, text
    from common_lib.modules.file_browser.service import _engine

    with Session(_engine()) as db:
        db.execute(
            text(
                "UPDATE file_system.files SET is_trashed = false, is_deleted = false WHERE id = :id"
            ),
            {"id": file_id},
        )
        db.commit()
    return ApiResponse(success=True)
