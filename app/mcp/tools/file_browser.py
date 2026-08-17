import logging
from typing import List, Dict, Any, Optional
from app.mcp.fastmcp_compat import FastMCP

logger = logging.getLogger("mcp.tools.file_browser")

def register_file_browser_tools(mcp: FastMCP):
    """Register all enhanced file system and directory management tools."""

    @mcp.tool()
    async def file_list(
        folder_id: Optional[str] = None,
        page: int = 1,
        limit: int = 50,
        sort_by: str = "date",
        sort_order: str = "desc"
    ) -> Dict[str, Any]:
        """
        List files and folders in a specific directory.
        Use 'folder_id' for subdirectories, or leave empty for root.
        """
        from common_lib.modules.file_system.service import list_files
        try:
            return list_files(
                folder_id=folder_id,
                page=page,
                limit=limit,
                sort_by=sort_by,
                sort_order=sort_order
            )
        except Exception as e:
            logger.error(f"Failed to list files: {e}")
            return {"status": "error", "message": str(e)}

    @mcp.tool()
    async def file_read(file_id: str) -> Dict[str, Any]:
        """Read metadata and details for a specific file by its unique ID."""
        from common_lib.modules.file_system.service import get_file
        file_node = get_file(file_id)
        if not file_node:
            return {"status": "error", "message": "File not found"}
        return file_node.model_dump()

    @mcp.tool()
    async def file_write(
        name: str,
        content: str,
        folder_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create or upload a new file with text content.
        Provide the 'name', the 'content', and optionally the 'folder_id'.
        """
        from common_lib.modules.file_system.service import upload_file
        try:
            # We encode content to bytes for upload_file
            data = content.encode("utf-8")
            result = upload_file(data, name, folder_id, user_id=None)
            return result
        except Exception as e:
            logger.error(f"Failed to write file: {e}")
            return {"status": "error", "message": str(e)}

    @mcp.tool()
    async def file_search(query: str, folder_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search for files and folders by name or content."""
        from common_lib.modules.file_system.service import search_files_fulltext
        try:
            results = search_files_fulltext(query, folder_id=folder_id)
            return results.get("items", [])
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    @mcp.tool()
    async def folder_create(name: str, parent_id: Optional[str] = None) -> Dict[str, Any]:
        """Create a new folder in the specified parent directory."""
        from common_lib.modules.file_system.service import create_folder
        try:
            return create_folder(name, parent_id)
        except Exception as e:
            logger.error(f"Failed to create folder: {e}")
            return {"status": "error", "message": str(e)}

    @mcp.tool()
    async def file_delete(file_id: str, permanent: bool = False) -> Dict[str, Any]:
        """Delete a file or folder by its ID. Set 'permanent=True' for immediate deletion."""
        from common_lib.modules.file_system.service import delete_file
        try:
            ok = delete_file(file_id, permanent=permanent)
            return {"status": "success" if ok else "error"}
        except Exception as e:
            logger.error(f"Failed to delete file: {e}")
            return {"status": "error", "message": str(e)}
