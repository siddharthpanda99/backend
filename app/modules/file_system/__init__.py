from fastapi import APIRouter, Query, HTTPException, Form
from typing import Optional
import json
from common_lib.modules.file_system.controller import (
    list_files,
    get_file_details,
    delete_file,
    rename_file,
    move_file,
    copy_file,
    create_folder,
    get_folder_tree,
    search_files,
    get_storage_stats,
)

router = APIRouter(prefix="/file-system", tags=["file-system"])


@router.get("/files")
async def list_files_handler(
    folder_id: Optional[str] = Query(None),
    page: int = Query(1),
    limit: int = Query(50),
    sort_by: str = Query("date"),
    sort_order: str = Query("desc"),
    view: str = Query("list"),
):
    """List files in a folder."""
    return list_files(folder_id, page, limit, sort_by, sort_order, view)


@router.get("/files/{file_id}")
async def get_file_handler(file_id: str):
    """Get file details."""
    result = get_file_details(file_id)
    if not result:
        raise HTTPException(status_code=404, detail="File not found")
    return result


@router.delete("/files/{file_id}")
async def delete_file_handler(file_id: str):
    """Delete a file."""
    success = delete_file(file_id)
    if not success:
        raise HTTPException(status_code=404, detail="File not found")
    return {"success": True}


@router.post("/files/{file_id}/rename")
async def rename_file_handler(file_id: str, new_name: str):
    """Rename a file."""
    success = rename_file(file_id, new_name)
    if not success:
        raise HTTPException(status_code=404, detail="File not found")
    return {"success": True}


@router.post("/files/{file_id}/move")
async def move_file_handler(file_id: str, target_folder_id: str):
    """Move a file to another folder."""
    success = move_file(file_id, target_folder_id)
    if not success:
        raise HTTPException(status_code=404, detail="File not found")
    return {"success": True}


@router.post("/files/{file_id}/copy")
async def copy_file_handler(file_id: str, target_folder_id: str):
    """Copy a file to another folder."""
    success = copy_file(file_id, target_folder_id)
    if not success:
        raise HTTPException(status_code=404, detail="File not found")
    return {"success": True}


@router.post("/folders")
async def create_folder_handler(name: str, parent_id: Optional[str] = None):
    """Create a new folder."""
    return create_folder(name, parent_id)


@router.get("/folders/tree")
async def get_folder_tree_handler():
    """Get folder tree structure."""
    return get_folder_tree()


@router.get("/search")
async def search_handler(
    q: str = Query(...),
    folder_id: Optional[str] = Query(None),
    file_types: Optional[str] = Query(None),
    page: int = Query(1),
    limit: int = Query(50),
):
    """Search files."""
    file_type_list = file_types.split(",") if file_types else None
    return search_files(q, folder_id, file_type_list, page, limit)


@router.get("/storage")
async def get_storage_stats_handler():
    """Get storage statistics."""
    return get_storage_stats()
