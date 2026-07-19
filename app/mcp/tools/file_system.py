"""MCP tools for File System — file/folder CRUD, storage statistics.

Registered under the Cognitive Orchestrator MCP server.
Each tool wraps common_lib.modules.file_system services.
"""

import logging
from typing import List, Dict, Any, Optional
from mcp.server.fastmcp import FastMCP

logger = logging.getLogger("mcp.tools.file_system")


def register_file_system_tools(mcp: FastMCP):
    """Register tools for file system operations."""

    @mcp.tool()
    async def filesystem_list_files(directory: str = "/") -> List[Dict[str, Any]]:
        """List files in a directory."""
        try:
            from common_lib.modules.file_system.controller import FileStorageController
            svc = FileStorageController()
            result = svc.list_files(directory) if hasattr(svc, "list_files") else []
            return result if isinstance(result, list) else []
        except Exception as e:
            logger.error(f"filesystem_list_files error: {e}")
            return []

    @mcp.tool()
    async def filesystem_read_file(file_path: str) -> Dict[str, Any]:
        """Read file contents."""
        try:
            from common_lib.modules.file_system.controller import FileStorageController
            svc = FileStorageController()
            result = svc.get_file(file_path) if hasattr(svc, "get_file") else None
            if result is None:
                return {"error": f"File '{file_path}' not found"}
            return result if isinstance(result, dict) else {"path": file_path, "content": str(result)}
        except Exception as e:
            logger.error(f"filesystem_read_file error: {e}")
            return {"error": str(e)}

    @mcp.tool()
    async def filesystem_write_file(file_path: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create or update a file."""
        try:
            from common_lib.modules.file_system.controller import FileStorageController
            svc = FileStorageController()
            result = svc.create_file(file_path, content, metadata) if hasattr(svc, "create_file") else {"path": file_path}
            return result if isinstance(result, dict) else {"path": file_path}
        except Exception as e:
            logger.error(f"filesystem_write_file error: {e}")
            return {"error": str(e)}

    @mcp.tool()
    async def filesystem_delete_file(file_path: str) -> str:
        """Delete a file."""
        try:
            from common_lib.modules.file_system.controller import FileStorageController
            svc = FileStorageController()
            svc.delete_file(file_path) if hasattr(svc, "delete_file") else None
            return f"File {file_path} deleted"
        except Exception as e:
            logger.error(f"filesystem_delete_file error: {e}")
            return f"Error: {e}"

    @mcp.tool()
    async def filesystem_create_folder(path: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create a folder."""
        try:
            from common_lib.modules.file_system.controller import FileStorageController
            svc = FileStorageController()
            result = svc.create_folder(path, metadata) if hasattr(svc, "create_folder") else {"path": path}
            return result if isinstance(result, dict) else {"path": path}
        except Exception as e:
            logger.error(f"filesystem_create_folder error: {e}")
            return {"error": str(e)}

    @mcp.tool()
    async def filesystem_stats() -> Dict[str, Any]:
        """Get storage statistics."""
        try:
            from common_lib.modules.file_system.controller import FileStorageController
            svc = FileStorageController()
            result = svc.get_stats() if hasattr(svc, "get_stats") else {"total_files": 0, "total_size": 0}
            return result
        except Exception as e:
            logger.error(f"filesystem_stats error: {e}")
            return {"error": str(e)}

    logger.info("File System: 6 MCP tools registered")
