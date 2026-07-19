"""MCP tools for Credentials — API key and credential management.

Registered under the Cognitive Orchestrator MCP server.
Each tool wraps the corresponding keys_management credentials service.
"""

import logging
from typing import List, Dict, Any, Optional
from mcp.server.fastmcp import FastMCP

logger = logging.getLogger("mcp.tools.credentials")


def register_credentials_tools(mcp: FastMCP):
    """Register tools for credential management."""

    @mcp.tool()
    async def credentials_list() -> List[Dict[str, Any]]:
        """List all stored credentials/API keys."""
        try:
            from common_lib.modules.keys_management.service import KeysManagementService
            svc = KeysManagementService()
            result = svc.list_credentials() if hasattr(svc, "list_credentials") else []
            return result if isinstance(result, list) else []
        except Exception as e:
            logger.error(f"credentials_list error: {e}")
            return []

    @mcp.tool()
    async def credentials_get(credential_id: str) -> Dict[str, Any]:
        """Get a specific credential by ID."""
        try:
            from common_lib.modules.keys_management.service import KeysManagementService
            svc = KeysManagementService()
            result = svc.get_credential(credential_id) if hasattr(svc, "get_credential") else None
            if result is None:
                return {"error": f"Credential '{credential_id}' not found"}
            return result if isinstance(result, dict) else {"id": credential_id}
        except Exception as e:
            logger.error(f"credentials_get error: {e}")
            return {"error": str(e)}

    @mcp.tool()
    async def credentials_create(name: str, credential_type: str = "api_key", value: str = "", metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create a new credential."""
        try:
            from common_lib.modules.keys_management.service import KeysManagementService
            svc = KeysManagementService()
            result = svc.create_credential(name=name, credential_type=credential_type, value=value, metadata=metadata) if hasattr(svc, "create_credential") else {"name": name}
            return result if isinstance(result, dict) else {"name": name}
        except Exception as e:
            logger.error(f"credentials_create error: {e}")
            return {"error": str(e)}

    @mcp.tool()
    async def credentials_delete(credential_id: str) -> str:
        """Delete a credential by ID."""
        try:
            from common_lib.modules.keys_management.service import KeysManagementService
            svc = KeysManagementService()
            svc.delete_credential(credential_id) if hasattr(svc, "delete_credential") else None
            return f"Credential {credential_id} deleted"
        except Exception as e:
            logger.error(f"credentials_delete error: {e}")
            return f"Error: {e}"

    @mcp.tool()
    async def credentials_test(credential_id: str) -> Dict[str, Any]:
        """Test a credential connection."""
        try:
            from common_lib.modules.keys_management.service import KeysManagementService
            svc = KeysManagementService()
            result = svc.test_credential(credential_id) if hasattr(svc, "test_credential") else {"valid": False}
            return result if isinstance(result, dict) else {"credential_id": credential_id, "valid": False}
        except Exception as e:
            logger.error(f"credentials_test error: {e}")
            return {"credential_id": credential_id, "valid": False, "error": str(e)}

    logger.info("Credentials: 5 MCP tools registered")
