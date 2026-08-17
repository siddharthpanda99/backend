"""PM MCP Tools — Register all Project Management @node wrappers as MCP tools.

This module bridges the common_lib PM MCP server into the Backend MCP server.
All 250+ PM @node wrappers are automatically discovered and registered
with proper domain categorization (Projects, Issues, Agile, Goals, Risk, etc.).
"""

import logging
from app.mcp.fastmcp_compat import FastMCP

logger = logging.getLogger(__name__)


def register_project_management_tools(mcp_server: FastMCP):
    """Register all PM tools via the common_lib PM MCP server.

    This replaces the previous 4-tool stub with comprehensive coverage
    of all 250+ PM @node wrappers organized by domain.
    """
    try:
        from common_lib.modules.project_management.mcp.server import register_pm_mcp_tools

        count = register_pm_mcp_tools(mcp_server)
        logger.info("PM MCP: %d tools registered via common_lib PM MCP server", count)
    except ImportError as e:
        logger.warning("PM MCP server not available, falling back to basic tools: %s", e)
        _register_basic_pm_tools(mcp_server)
    except Exception as e:
        logger.error("Failed to register PM MCP tools: %s", e)
        _register_basic_pm_tools(mcp_server)


def _register_basic_pm_tools(mcp_server: FastMCP):
    """Fallback: register basic PM tools if comprehensive server unavailable."""
    import json

    try:
        from common_lib.modules.project_management import (
            ProjectService, IssueService, SprintService,
        )
    except ImportError:
        logger.error("Cannot import PM services for fallback tools")
        return

    @mcp_server.tool()
    def pm_list_projects(user_id: str, skip: int = 0, limit: int = 50) -> str:
        """List project management projects."""
        try:
            projects = ProjectService.list_projects(user_id=user_id, skip=skip, limit=limit)
            return json.dumps([p.dict() if hasattr(p, 'dict') else dict(p) for p in projects], default=str)
        except Exception as e:
            return f"Error: {e}"

    @mcp_server.tool()
    def pm_get_project_details(project_id: str, user_id: str = "") -> str:
        """Get project details by ID."""
        try:
            project = ProjectService.get_project(project_id=project_id)
            if not project:
                return "Project not found"
            return json.dumps(project.dict() if hasattr(project, 'dict') else dict(project), default=str)
        except Exception as e:
            return f"Error: {e}"

    @mcp_server.tool()
    def pm_list_issues(project_id: str, user_id: str = "", skip: int = 0, limit: int = 50) -> str:
        """List issues for a specific project."""
        try:
            issues = IssueService.list_issues(project_id=project_id, skip=skip, limit=limit)
            return json.dumps([i.dict() if hasattr(i, 'dict') else dict(i) for i in issues], default=str)
        except Exception as e:
            return f"Error: {e}"

    @mcp_server.tool()
    def pm_list_sprints(project_id: str, user_id: str = "", skip: int = 0, limit: int = 50) -> str:
        """List sprints for a specific project."""
        try:
            sprints = SprintService.list_sprints(project_id=project_id, skip=skip, limit=limit)
            return json.dumps([s.dict() if hasattr(s, 'dict') else dict(s) for s in sprints], default=str)
        except Exception as e:
            return f"Error: {e}"

    logger.info("PM MCP: Registered 4 basic fallback tools")
