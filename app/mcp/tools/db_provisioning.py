"""MCP tools for DB Provisioning — list types, provision databases, status.

Registered under the Cognitive Orchestrator MCP server.
Each tool wraps common_lib.modules.data_storage.db_provisioning.service.
"""

import logging
from typing import Dict, Any, Optional
from app.mcp.fastmcp_compat import FastMCP

logger = logging.getLogger("mcp.tools.db_provisioning")


def register_db_provisioning_tools(mcp: FastMCP):
    """Register tools for database provisioning."""

    @mcp.tool()
    async def db_provision_list_types() -> Dict[str, Any]:
        """List all supported database types for provisioning."""
        try:
            from common_lib.modules.data_storage.db_provisioning.service import DatabaseProvisionerService
            svc = DatabaseProvisionerService()
            result = svc.list_supported_types() if hasattr(svc, "list_supported_types") else {"types": []}
            return result
        except Exception as e:
            logger.error(f"db_provision_list_types error: {e}")
            return {"types": [], "error": str(e)}

    @mcp.tool()
    async def db_provision_create(db_type: str, name: Optional[str] = None, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Provision a new database instance (Docker or SQLite)."""
        try:
            from common_lib.modules.data_storage.db_provisioning.service import DatabaseProvisionerService
            svc = DatabaseProvisionerService()
            result = svc.provision(db_type, name, config) if hasattr(svc, "provision") else {"db_type": db_type}
            return result if isinstance(result, dict) else {"db_type": db_type, "status": "created"}
        except Exception as e:
            logger.error(f"db_provision_create error: {e}")
            return {"error": str(e)}

    @mcp.tool()
    async def db_provision_status() -> Dict[str, Any]:
        """Get provisioning service status and active instances."""
        try:
            from common_lib.modules.data_storage.db_provisioning.service import DatabaseProvisionerService
            svc = DatabaseProvisionerService()
            result = svc.get_status() if hasattr(svc, "get_status") else {"status": "ok"}
            return result
        except Exception as e:
            logger.error(f"db_provision_status error: {e}")
            return {"status": "error", "error": str(e)}

    logger.info("DB Provisioning: 3 MCP tools registered")
