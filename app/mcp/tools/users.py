import logging
from typing import List, Dict, Any, Optional
from app.mcp.fastmcp_compat import FastMCP
from ..mcp_dependencies import resolve_user_service

logger = logging.getLogger("mcp.tools.users")

def register_user_tools(mcp: FastMCP):
    """Register tools for user management and platform identity context."""

    @mcp.tool()
    async def list_users(active_only: bool = True) -> List[Dict[str, Any]]:
        """List platform users and their current status."""
        service = resolve_user_service()
        users = await service.get_users(active_only=active_only)
        return [u.model_dump(exclude={"hashed_password"}) for u in users]

    @mcp.tool()
    async def get_user_profile(user_id: str) -> Dict[str, Any]:
        """Retrieve the full profile of a user by their ID."""
        service = resolve_user_service()
        user = await service.get_user(user_id)
        if not user:
            return {"status": "error", "message": "User not found"}
        return user.model_dump(exclude={"hashed_password"})

    @mcp.tool()
    async def user_get_current() -> Dict[str, Any]:
        """Get the identity context of the current platform session."""
        # In an MCP tool, we often want to know who is 'acting'
        # For now, we return the mock system user or platform identity
        return {"id": "system", "role": "admin", "permissions": ["*"]}
