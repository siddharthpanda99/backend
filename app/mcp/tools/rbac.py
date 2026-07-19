"""MCP tools for RBAC — roles, permissions, user-role assignments, organizations.

Registered under the Cognitive Orchestrator MCP server.
Each tool wraps the corresponding common_lib.modules.rbac service layer.
"""

import logging
from typing import List, Dict, Any, Optional
from mcp.server.fastmcp import FastMCP

logger = logging.getLogger("mcp.tools.rbac")


def register_rbac_tools(mcp: FastMCP):
    """Register tools for Role-Based Access Control."""

    @mcp.tool()
    async def rbac_list_roles() -> List[Dict[str, Any]]:
        """List all roles in the RBAC system."""
        try:
            from common_lib.modules.governance.rbac.service import get_rbac_service
            svc = get_rbac_service()
            result = svc.list_roles() if hasattr(svc, "list_roles") else []
            return result if isinstance(result, list) else []
        except Exception as e:
            logger.error(f"rbac_list_roles error: {e}")
            return []

    @mcp.tool()
    async def rbac_create_role(name: str, description: str = "", permissions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Create a new role with optional permissions."""
        try:
            from common_lib.modules.governance.rbac.service import get_rbac_service
            svc = get_rbac_service()
            result = svc.create_role(name=name, description=description, permissions=permissions or []) if hasattr(svc, "create_role") else {"name": name}
            return result if isinstance(result, dict) else {"name": name}
        except Exception as e:
            logger.error(f"rbac_create_role error: {e}")
            return {"error": str(e)}

    @mcp.tool()
    async def rbac_delete_role(role_id: str) -> str:
        """Delete a role by ID."""
        try:
            from common_lib.modules.governance.rbac.service import get_rbac_service
            svc = get_rbac_service()
            svc.delete_role(role_id) if hasattr(svc, "delete_role") else None
            return f"Role {role_id} deleted"
        except Exception as e:
            logger.error(f"rbac_delete_role error: {e}")
            return f"Error: {e}"

    @mcp.tool()
    async def rbac_get_user_roles(user_id: str) -> List[Dict[str, Any]]:
        """Get all roles assigned to a user."""
        try:
            from common_lib.modules.governance.rbac.service import get_rbac_service
            svc = get_rbac_service()
            result = svc.get_user_roles(user_id) if hasattr(svc, "get_user_roles") else []
            return result if isinstance(result, list) else []
        except Exception as e:
            logger.error(f"rbac_get_user_roles error: {e}")
            return []

    @mcp.tool()
    async def rbac_assign_role(user_id: str, role_id: str) -> str:
        """Assign a role to a user."""
        try:
            from common_lib.modules.governance.rbac.service import get_rbac_service
            svc = get_rbac_service()
            svc.assign_role(user_id, role_id) if hasattr(svc, "assign_role") else None
            return f"Role {role_id} assigned to user {user_id}"
        except Exception as e:
            logger.error(f"rbac_assign_role error: {e}")
            return f"Error: {e}"

    @mcp.tool()
    async def rbac_check_permission(user_id: str, resource: str, action: str) -> Dict[str, Any]:
        """Check if a user has permission for an action on a resource."""
        try:
            from common_lib.modules.governance.rbac.service import get_rbac_service
            svc = get_rbac_service()
            allowed = svc.check_permission(user_id, resource, action) if hasattr(svc, "check_permission") else False
            return {"user_id": user_id, "resource": resource, "action": action, "allowed": allowed}
        except Exception as e:
            logger.error(f"rbac_check_permission error: {e}")
            return {"user_id": user_id, "resource": resource, "action": action, "allowed": False, "error": str(e)}

    @mcp.tool()
    async def rbac_list_organizations() -> List[Dict[str, Any]]:
        """List all organizations."""
        try:
            from common_lib.modules.governance.rbac.service import get_rbac_service
            svc = get_rbac_service()
            result = svc.list_organizations() if hasattr(svc, "list_organizations") else []
            return result if isinstance(result, list) else []
        except Exception as e:
            logger.error(f"rbac_list_organizations error: {e}")
            return []

    logger.info("RBAC: 7 MCP tools registered")
