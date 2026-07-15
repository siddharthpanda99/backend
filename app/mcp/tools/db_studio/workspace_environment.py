"""MCP tools for Workspace, Projects & Environment Management (UDS Module 24)."""

from typing import Optional

from common_lib.modules.db_studio.workspace_environment import (
    WorkspaceEnvironmentService,
    WorkspaceCreate, WorkspaceUpdate,
    ProjectCreate, ProjectUpdate,
    FolderCreate,
    EnvironmentCreate, EnvironmentUpdate,
    VariableCreate, VariableUpdate,
    ConnectionProfileCreate,
    PromotionCreate, PromotionUpdate,
)

svc = WorkspaceEnvironmentService()


def mcp_workspace_create(name: str, workspace_type: str = "personal",
                          description: str = None, owner_id: str = None) -> dict:
    """Create a workspace with default environments (Dev, QA, Staging, Prod)."""
    req = WorkspaceCreate(
        name=name, workspace_type=workspace_type, description=description, owner_id=owner_id,
    )
    result = svc.create_workspace(req)
    return result.model_dump()


def mcp_workspace_list(workspace_type: str = None, owner_id: str = None,
                        limit: int = 50) -> list:
    """List workspaces with optional filters."""
    results = svc.list_workspaces(workspace_type, owner_id, limit=limit)
    return [r.model_dump() for r in results]


def mcp_workspace_get(workspace_id: str) -> Optional[dict]:
    """Get a workspace by ID."""
    result = svc.get_workspace(workspace_id)
    return result.model_dump() if result else None


def mcp_project_create(workspace_id: str, name: str, description: str = None,
                        folder_id: str = None) -> dict:
    """Create a project in a workspace."""
    req = ProjectCreate(workspace_id=workspace_id, name=name,
                         description=description, folder_id=folder_id)
    result = svc.create_project(req)
    return result.model_dump()


def mcp_project_list(workspace_id: str = None, folder_id: str = None,
                      limit: int = 50) -> list:
    """List projects."""
    results = svc.list_projects(workspace_id, folder_id, limit=limit)
    return [r.model_dump() for r in results]


def mcp_environment_list(workspace_id: str) -> list:
    """List environments for a workspace."""
    results = svc.list_environments(workspace_id)
    return [r.model_dump() for r in results]


def mcp_variable_create(workspace_id: str, key: str, value: str,
                         environment_id: str = None, is_secret: bool = False) -> dict:
    """Create a variable."""
    req = VariableCreate(
        workspace_id=workspace_id, key=key, value=value,
        environment_id=environment_id, is_secret=is_secret,
    )
    result = svc.create_variable(req)
    return result.model_dump()


def mcp_variable_list(workspace_id: str, environment_id: str = None) -> list:
    """List variables for a workspace."""
    results = svc.list_variables(workspace_id, environment_id)
    return [r.model_dump() for r in results]


def mcp_promotion_create(workspace_id: str, source_environment_id: str,
                          target_environment_id: str, changelog: str = None) -> dict:
    """Create a promotion request."""
    req = PromotionCreate(
        workspace_id=workspace_id, source_environment_id=source_environment_id,
        target_environment_id=target_environment_id, changelog=changelog,
    )
    result = svc.create_promotion(req)
    return result.model_dump()


def mcp_workspace_dashboard() -> dict:
    """Get workspace dashboard summary."""
    result = svc.get_dashboard()
    return result.model_dump()


def register_workspace_tools(mcp_server):
    """Register all workspace tools with the MCP server."""
    for name, fn in TOOLS.items():
        mcp_server.tool(name=name)(fn)
    return mcp_server


TOOLS = {
    "workspace_create": mcp_workspace_create,
    "workspace_list": mcp_workspace_list,
    "workspace_get": mcp_workspace_get,
    "project_create": mcp_project_create,
    "project_list": mcp_project_list,
    "environment_list": mcp_environment_list,
    "variable_create": mcp_variable_create,
    "variable_list": mcp_variable_list,
    "promotion_create": mcp_promotion_create,
    "workspace_dashboard": mcp_workspace_dashboard,
}
