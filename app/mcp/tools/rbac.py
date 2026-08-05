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

    def _get_session():
        from common_lib.modules.integration.adapters.database_adapter import get_db_port
        engine = get_db_port().get_engine()
        from sqlmodel import Session
        return Session(engine)

    # -- Role Management --

    @mcp.tool()
    async def rbac_list_roles() -> List[Dict[str, Any]]:
        """List all roles in the RBAC system."""
        try:
            from common_lib.modules.rbac.service import RBACService
            svc = RBACService()
            result = svc.list_roles()
            return result if isinstance(result, list) else []
        except Exception as e:
            logger.error(f"rbac_list_roles error: {e}")
            return []

    @mcp.tool()
    async def rbac_create_role(name: str, description: str = "", permissions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Create a new role with optional permissions."""
        try:
            from common_lib.modules.rbac.service import RBACService
            svc = RBACService()
            result = svc.create_role(name=name, description=description, permissions=permissions or [])
            return result if isinstance(result, dict) else {"name": name}
        except Exception as e:
            logger.error(f"rbac_create_role error: {e}")
            return {"error": str(e)}

    @mcp.tool()
    async def rbac_delete_role(role_id: str) -> str:
        """Delete a role by ID."""
        try:
            from common_lib.modules.rbac.service import RBACService
            svc = RBACService()
            svc.delete_role(role_id)
            return f"Role {role_id} deleted"
        except Exception as e:
            logger.error(f"rbac_delete_role error: {e}")
            return f"Error: {e}"

    @mcp.tool()
    async def rbac_get_user_roles(user_id: str) -> List[Dict[str, Any]]:
        """Get all roles assigned to a user."""
        try:
            from common_lib.modules.rbac.service import RBACService
            svc = RBACService()
            result = svc.get_user_roles(user_id)
            return result if isinstance(result, list) else []
        except Exception as e:
            logger.error(f"rbac_get_user_roles error: {e}")
            return []

    @mcp.tool()
    async def rbac_assign_role(user_id: str, role_id: str) -> str:
        """Assign a role to a user."""
        try:
            from common_lib.modules.rbac.service import RBACService
            svc = RBACService()
            svc.assign_role(user_id, role_id)
            return f"Role {role_id} assigned to user {user_id}"
        except Exception as e:
            logger.error(f"rbac_assign_role error: {e}")
            return f"Error: {e}"

    @mcp.tool()
    async def rbac_check_permission(user_id: str, resource: str, action: str) -> Dict[str, Any]:
        """Check if a user has permission for an action on a resource."""
        try:
            from common_lib.modules.rbac.api.service import PermissionCheckService
            session = _get_session()
            try:
                svc = PermissionCheckService(session)
                result = svc.check(user_id=int(user_id), resource=resource, action=action)
                return result
            finally:
                session.close()
        except Exception as e:
            logger.error(f"rbac_check_permission error: {e}")
            return {"user_id": user_id, "resource": resource, "action": action, "allowed": False, "error": str(e)}

    @mcp.tool()
    async def rbac_list_organizations() -> List[Dict[str, Any]]:
        """List all organizations."""
        try:
            from common_lib.modules.rbac.tenant_service import OrganizationService
            session = _get_session()
            try:
                orgs = OrganizationService(session).list_orgs()
                return [{"id": o.id, "name": o.name, "slug": o.slug} for o in orgs]
            finally:
                session.close()
        except Exception as e:
            logger.error(f"rbac_list_organizations error: {e}")
            return []

    logger.info("RBAC: 7 MCP tools registered (fixed imports)")
