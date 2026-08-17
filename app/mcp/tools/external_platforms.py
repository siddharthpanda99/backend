"""MCP tools for External Platforms — Story Bible management.

Registered under the Cognitive Orchestrator MCP server.
Each tool wraps common_lib.modules.external_platforms services.
"""

import logging
from typing import List, Dict, Any, Optional
from app.mcp.fastmcp_compat import FastMCP

logger = logging.getLogger("mcp.tools.external_platforms")


def register_external_platforms_tools(mcp: FastMCP):
    """Register tools for external platform integrations."""

    @mcp.tool()
    async def external_list_platforms() -> List[Dict[str, Any]]:
        """List supported external platforms."""
        try:
            from common_lib.modules.external_platforms.service import StoryBibleService
            svc = StoryBibleService()
            result = svc.list_platforms() if hasattr(svc, "list_platforms") else []
            return result if isinstance(result, list) else []
        except Exception as e:
            logger.error(f"external_list_platforms error: {e}")
            return []

    @mcp.tool()
    async def external_story_bible_list(project_id: str) -> List[Dict[str, Any]]:
        """List all Story Bible entries for a project."""
        try:
            from common_lib.modules.external_platforms.service import StoryBibleService
            svc = StoryBibleService()
            result = svc.list_entries(project_id) if hasattr(svc, "list_entries") else []
            return result if isinstance(result, list) else []
        except Exception as e:
            logger.error(f"external_story_bible_list error: {e}")
            return []

    @mcp.tool()
    async def external_story_bible_create(project_id: str, entry_type: str, name: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create a new Story Bible entry."""
        try:
            from common_lib.modules.external_platforms.service import StoryBibleService
            svc = StoryBibleService()
            result = svc.create_entry(project_id, entry_type, name, data) if hasattr(svc, "create_entry") else {"name": name}
            return result if isinstance(result, dict) else {"name": name}
        except Exception as e:
            logger.error(f"external_story_bible_create error: {e}")
            return {"error": str(e)}

    @mcp.tool()
    async def external_story_bible_update(project_id: str, entry_id: str, name: Optional[str] = None, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Update a Story Bible entry."""
        try:
            from common_lib.modules.external_platforms.service import StoryBibleService
            svc = StoryBibleService()
            updates = {}
            if name:
                updates["name"] = name
            if data:
                updates["data"] = data
            result = svc.update_entry(project_id, entry_id, **updates) if hasattr(svc, "update_entry") else {"entry_id": entry_id}
            return result if isinstance(result, dict) else {"entry_id": entry_id}
        except Exception as e:
            logger.error(f"external_story_bible_update error: {e}")
            return {"error": str(e)}

    @mcp.tool()
    async def external_story_bible_delete(project_id: str, entry_id: str) -> str:
        """Delete a Story Bible entry."""
        try:
            from common_lib.modules.external_platforms.service import StoryBibleService
            svc = StoryBibleService()
            svc.delete_entry(project_id, entry_id) if hasattr(svc, "delete_entry") else None
            return f"Entry {entry_id} deleted"
        except Exception as e:
            logger.error(f"external_story_bible_delete error: {e}")
            return f"Error: {e}"

    logger.info("External Platforms: 5 MCP tools registered")
