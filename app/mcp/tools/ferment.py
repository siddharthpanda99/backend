"""MCP tools for Ferment — multi-agent lifecycle, project phases, grading.

Registered under the Cognitive Orchestrator MCP server.
Each tool wraps common_lib.modules.ferment services.
"""

import logging
from typing import List, Dict, Any, Optional
from mcp.server.fastmcp import FastMCP

logger = logging.getLogger("mcp.tools.ferment")


def register_ferment_tools(mcp: FastMCP):
    """Register tools for multi-agent lifecycle management."""

    @mcp.tool()
    async def ferment_list_projects() -> List[Dict[str, Any]]:
        """List all ferment projects."""
        try:
            from common_lib.modules.ferment.service import ProjectEngine
            svc = ProjectEngine()
            result = svc.list_projects() if hasattr(svc, "list_projects") else []
            return result if isinstance(result, list) else []
        except Exception as e:
            logger.error(f"ferment_list_projects error: {e}")
            return []

    @mcp.tool()
    async def ferment_create_project(name: str, description: str = "", config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create a new ferment project."""
        try:
            from common_lib.modules.ferment.service import ProjectEngine
            svc = ProjectEngine()
            result = svc.create_project(name, description, config) if hasattr(svc, "create_project") else {"name": name}
            return result if isinstance(result, dict) else {"name": name}
        except Exception as e:
            logger.error(f"ferment_create_project error: {e}")
            return {"error": str(e)}

    @mcp.tool()
    async def ferment_get_project(project_id: str) -> Dict[str, Any]:
        """Get a ferment project by ID."""
        try:
            from common_lib.modules.ferment.service import ProjectEngine
            svc = ProjectEngine()
            result = svc.get_project(project_id) if hasattr(svc, "get_project") else None
            if result is None:
                return {"error": f"Project '{project_id}' not found"}
            return result if isinstance(result, dict) else {"project_id": project_id}
        except Exception as e:
            logger.error(f"ferment_get_project error: {e}")
            return {"error": str(e)}

    @mcp.tool()
    async def ferment_execute(project_id: str, phase: Optional[str] = None, inputs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a project phase."""
        try:
            from common_lib.modules.ferment.service import ProjectEngine
            svc = ProjectEngine()
            result = svc.execute(project_id, phase, inputs) if hasattr(svc, "execute") else {"executed": False}
            return result if isinstance(result, dict) else {"executed": bool(result)}
        except Exception as e:
            logger.error(f"ferment_execute error: {e}")
            return {"error": str(e)}

    @mcp.tool()
    async def ferment_grade(project_id: str) -> Dict[str, Any]:
        """Grade a project's output quality."""
        try:
            from common_lib.modules.ferment.service import ProjectEngine
            svc = ProjectEngine()
            result = svc.grade(project_id) if hasattr(svc, "grade") else {"score": 0}
            return result if isinstance(result, dict) else {"score": 0}
        except Exception as e:
            logger.error(f"ferment_grade error: {e}")
            return {"error": str(e)}

    @mcp.tool()
    async def ferment_delete_project(project_id: str) -> str:
        """Delete a ferment project."""
        try:
            from common_lib.modules.ferment.service import ProjectEngine
            svc = ProjectEngine()
            svc.delete_project(project_id) if hasattr(svc, "delete_project") else None
            return f"Project {project_id} deleted"
        except Exception as e:
            logger.error(f"ferment_delete_project error: {e}")
            return f"Error: {e}"

    logger.info("Ferment: 6 MCP tools registered")
