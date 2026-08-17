"""MCP tools for Core Infrastructure — tool registry, discovery, catalog, sandbox execution.

Registered under the Cognitive Orchestrator MCP server.
Each tool wraps common_lib.modules.core_infrastructure services.
"""

import logging
from typing import List, Dict, Any, Optional
from app.mcp.fastmcp_compat import FastMCP

logger = logging.getLogger("mcp.tools.core_infrastructure")


def register_core_infrastructure_tools(mcp: FastMCP):
    """Register tools for core infrastructure services."""

    @mcp.tool()
    async def infra_list_tools() -> List[Dict[str, Any]]:
        """List all registered tools in the infrastructure registry."""
        try:
            from common_lib.modules.core_infrastructure.service import ToolRegistry
            svc = ToolRegistry()
            result = svc.list_tools() if hasattr(svc, "list_tools") else []
            return result if isinstance(result, list) else []
        except Exception as e:
            logger.error(f"infra_list_tools error: {e}")
            return []

    @mcp.tool()
    async def infra_register_tool(name: str, description: str = "", category: str = "", parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Register a new tool in the infrastructure."""
        try:
            from common_lib.modules.core_infrastructure.service import ToolRegistry
            svc = ToolRegistry()
            result = svc.register(name, description, category, parameters) if hasattr(svc, "register") else {"name": name}
            return result if isinstance(result, dict) else {"name": name}
        except Exception as e:
            logger.error(f"infra_register_tool error: {e}")
            return {"error": str(e)}

    @mcp.tool()
    async def infra_discover_tools(query: str = "") -> List[Dict[str, Any]]:
        """Discover tools matching a query."""
        try:
            from common_lib.modules.core_infrastructure.service import ToolRegistry
            svc = ToolRegistry()
            result = svc.discover(query) if hasattr(svc, "discover") else []
            return result if isinstance(result, list) else []
        except Exception as e:
            logger.error(f"infra_discover_tools error: {e}")
            return []

    @mcp.tool()
    async def infra_get_catalog() -> Dict[str, Any]:
        """Get the full tool catalog."""
        try:
            from common_lib.modules.core_infrastructure.service import ToolRegistry
            svc = ToolRegistry()
            result = svc.get_catalog() if hasattr(svc, "get_catalog") else {}
            return result if isinstance(result, dict) else {"catalog": result}
        except Exception as e:
            logger.error(f"infra_get_catalog error: {e}")
            return {"error": str(e)}

    @mcp.tool()
    async def infra_sandbox_execute(code: str, language: str = "python", timeout: int = 30) -> Dict[str, Any]:
        """Execute code in the sandbox."""
        try:
            from common_lib.modules.core_infrastructure.service import SandboxExecutor
            svc = SandboxExecutor()
            result = svc.execute(code, language, timeout) if hasattr(svc, "execute") else {"output": ""}
            return result if isinstance(result, dict) else {"output": str(result)}
        except Exception as e:
            logger.error(f"infra_sandbox_execute error: {e}")
            return {"error": str(e)}

    @mcp.tool()
    async def infra_sandbox_status() -> Dict[str, Any]:
        """Get sandbox execution status."""
        try:
            from common_lib.modules.core_infrastructure.service import SandboxExecutor
            svc = SandboxExecutor()
            result = svc.status() if hasattr(svc, "status") else {"status": "ok"}
            return result
        except Exception as e:
            logger.error(f"infra_sandbox_status error: {e}")
            return {"status": "error", "error": str(e)}

    logger.info("Core Infrastructure: 6 MCP tools registered")
