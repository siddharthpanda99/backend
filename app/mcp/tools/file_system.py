"""MCP tools for File System — file/folder CRUD, storage statistics, search.

Registered under the Cognitive Orchestrator MCP server.
Each tool wraps common_lib.modules.file_system services (DB-backed file manager).
"""

import logging
from typing import Any, Dict, List, Optional

from app.mcp.fastmcp_compat import FastMCP

logger = logging.getLogger("mcp.tools.file_system")


def _dump(obj: Any) -> Any:
    """Serialize Pydantic/SQLModel responses to JSON-safe dicts."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if isinstance(obj, list):
        return [_dump(item) for item in obj]
    if isinstance(obj, dict):
        return {k: _dump(v) for k, v in obj.items()}
    return obj


def register_file_system_tools(mcp: FastMCP):
    """Register tools for file system operations."""

    @mcp.tool()
    async def filesystem_list_files(
        folder_id: Optional[str] = None,
        page: int = 1,
        limit: int = 50,
        sort_by: str = "date",
        sort_order: str = "desc",
        search: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List files in a folder (or the root). Returns paginated file/folder nodes."""
        try:
            from common_lib.modules.file_system.service import list_files

            result = list_files(
                folder_id=folder_id,
                page=page,
                limit=limit,
                sort_by=sort_by,
                sort_order=sort_order,
                search=search,
            )
            return _dump(result)
        except Exception as e:
            logger.error(f"filesystem_list_files error: {e}")
            return {"error": str(e), "items": [], "count": 0}

    @mcp.tool()
    async def filesystem_get_file(file_id: str) -> Dict[str, Any]:
        """Get file/folder details by id."""
        try:
            from common_lib.modules.file_system.service import get_file

            result = get_file(file_id=file_id)
            return _dump(result) if result else {"error": f"File '{file_id}' not found"}
        except Exception as e:
            logger.error(f"filesystem_get_file error: {e}")
            return {"error": str(e)}

    @mcp.tool()
    async def filesystem_create_folder(name: str, parent_id: Optional[str] = None) -> Dict[str, Any]:
        """Create a folder (optionally inside a parent folder)."""
        try:
            from common_lib.modules.file_system.service import create_folder

            result = create_folder(name=name, parent_id=parent_id)
            return _dump(result)
        except Exception as e:
            logger.error(f"filesystem_create_folder error: {e}")
            return {"error": str(e)}

    @mcp.tool()
    async def filesystem_delete_file(file_id: str, permanent: bool = False) -> Dict[str, Any]:
        """Delete a file/folder by id (soft-delete to trash unless permanent=True)."""
        try:
            from common_lib.modules.file_system.service import delete_file

            result = delete_file(file_id=file_id, permanent=permanent)
            return {"success": bool(result), "file_id": file_id}
        except Exception as e:
            logger.error(f"filesystem_delete_file error: {e}")
            return {"error": str(e), "success": False}

    @mcp.tool()
    async def filesystem_rename_file(file_id: str, new_name: str) -> Dict[str, Any]:
        """Rename a file or folder."""
        try:
            from common_lib.modules.file_system.service import rename_file

            result = rename_file(file_id=file_id, new_name=new_name)
            return _dump(result) if result else {"error": f"File '{file_id}' not found"}
        except Exception as e:
            logger.error(f"filesystem_rename_file error: {e}")
            return {"error": str(e)}

    @mcp.tool()
    async def filesystem_get_folder_tree() -> Dict[str, Any]:
        """Get the full folder tree."""
        try:
            from common_lib.modules.file_system.service import get_folder_tree

            result = get_folder_tree()
            return {"tree": _dump(result)}
        except Exception as e:
            logger.error(f"filesystem_get_folder_tree error: {e}")
            return {"error": str(e), "tree": []}

    @mcp.tool()
    async def filesystem_search_files(
        q: str,
        folder_id: Optional[str] = None,
        file_types: Optional[List[str]] = None,
        page: int = 1,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """Search files by name/path query, optionally filtered by file types."""
        try:
            from common_lib.modules.file_system.service import search_files

            result = search_files(q=q, folder_id=folder_id, file_types=file_types, page=page, limit=limit)
            return _dump(result)
        except Exception as e:
            logger.error(f"filesystem_search_files error: {e}")
            return {"error": str(e), "items": [], "count": 0}

    @mcp.tool()
    async def filesystem_stats() -> Dict[str, Any]:
        """Get storage statistics (total files, folders, size)."""
        try:
            from common_lib.modules.file_system.service import get_storage_stats

            result = get_storage_stats()
            return _dump(result)
        except Exception as e:
            logger.error(f"filesystem_stats error: {e}")
            return {"error": str(e), "total_files": 0, "total_size": 0}

    logger.info("File System: 7 MCP tools registered")
