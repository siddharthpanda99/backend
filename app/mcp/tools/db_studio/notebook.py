"""MCP tools for Notebook & Interactive Workspace (UDS Module 20)."""

from typing import Any, Dict, List, Optional

from common_lib.modules.db_studio.notebook import (
    NotebookService, NotebookCreate, NotebookUpdate,
    CellCreate, CellUpdate, ExecuteCellRequest,
    TemplateCreate, PublishRequest,
)

svc = NotebookService()


def mcp_notebook_create(title: str, description: str = None, language: str = "sql",
                         owner_id: str = None, workspace_id: str = None,
                         tags: list = None, template_id: str = None) -> dict:
    """Create a new notebook."""
    req = NotebookCreate(
        title=title, description=description, language=language,
        owner_id=owner_id, workspace_id=workspace_id,
        tags=tags, template_id=template_id,
    )
    result = svc.create_notebook(req)
    return result.model_dump()


def mcp_notebook_get(notebook_id: str) -> Optional[dict]:
    """Get notebook details by ID."""
    result = svc.get_notebook(notebook_id)
    return result.model_dump() if result else None


def mcp_notebook_list(owner_id: str = None, workspace_id: str = None,
                       language: str = None, limit: int = 50) -> list:
    """List notebooks with optional filters."""
    results = svc.list_notebooks(owner_id, workspace_id, language, limit=limit)
    return [r.model_dump() for r in results]


def mcp_notebook_update(notebook_id: str, title: str = None,
                         description: str = None, is_archived: bool = None) -> Optional[dict]:
    """Update a notebook."""
    req = NotebookUpdate(title=title, description=description, is_archived=is_archived)
    result = svc.update_notebook(notebook_id, req)
    return result.model_dump() if result else None


def mcp_notebook_delete(notebook_id: str) -> bool:
    """Delete a notebook."""
    return svc.delete_notebook(notebook_id)


def mcp_cell_create(notebook_id: str, cell_type: str = "sql", content: str = "",
                     language: str = None, position: int = 0) -> dict:
    """Create a cell in a notebook."""
    req = CellCreate(cell_type=cell_type, content=content, language=language, position=position)
    result = svc.create_cell(notebook_id, req)
    return result.model_dump()


def mcp_cell_list(notebook_id: str) -> list:
    """List all cells in a notebook."""
    results = svc.list_cells(notebook_id)
    return [r.model_dump() for r in results]


def mcp_cell_update(cell_id: str, content: str = None, cell_type: str = None) -> Optional[dict]:
    """Update a cell."""
    req = CellUpdate(content=content, cell_type=cell_type)
    result = svc.update_cell(cell_id, req)
    return result.model_dump() if result else None


def mcp_cell_delete(cell_id: str) -> bool:
    """Delete a cell."""
    return svc.delete_cell(cell_id)


def mcp_cell_execute(notebook_id: str, cell_id: str,
                      params: dict = None) -> dict:
    """Execute a cell (simulated)."""
    req = ExecuteCellRequest(params=params)
    result = svc.execute_cell(notebook_id, cell_id, req)
    return result.model_dump()


def mcp_notebook_create_version(notebook_id: str, changelog: str = None) -> Optional[dict]:
    """Create a version snapshot of a notebook."""
    result = svc.create_version(notebook_id, changelog)
    return result.model_dump() if result else None


def mcp_notebook_list_versions(notebook_id: str, limit: int = 50) -> list:
    """List version history for a notebook."""
    results = svc.list_versions(notebook_id, limit)
    return [r.model_dump() for r in results]


def mcp_template_create(name: str, description: str = None, category: str = "general",
                         language: str = "sql") -> dict:
    """Create a notebook template."""
    req = TemplateCreate(name=name, description=description, category=category, language=language)
    result = svc.create_template(req)
    return result.model_dump()


def mcp_template_list(category: str = None, language: str = None, limit: int = 50) -> list:
    """List notebook templates."""
    results = svc.list_templates(category, language, limit)
    return [r.model_dump() for r in results]


def mcp_notebook_publish(notebook_id: str, format: str = "html",
                          title: str = None, is_public: bool = False) -> Optional[dict]:
    """Publish a notebook."""
    req = PublishRequest(format=format, title=title, is_public=is_public)
    result = svc.publish_notebook(notebook_id, req)
    return result.model_dump() if result else None


def mcp_notebook_dashboard() -> dict:
    """Get notebook workspace dashboard summary."""
    result = svc.get_dashboard()
    return result.model_dump()


def mcp_execution_history(notebook_id: str = None, cell_id: str = None,
                           limit: int = 50) -> list:
    """List execution history."""
    results = svc.list_execution_history(notebook_id, cell_id, limit)
    return [r.model_dump() for r in results]


def register_notebook_tools(mcp_server):
    """Register all notebook tools with the MCP server."""
    for name, fn in TOOLS.items():
        mcp_server.tool(name=name)(fn)
    return mcp_server


# Tool registry
TOOLS = {
    "notebook_create": mcp_notebook_create,
    "notebook_get": mcp_notebook_get,
    "notebook_list": mcp_notebook_list,
    "notebook_update": mcp_notebook_update,
    "notebook_delete": mcp_notebook_delete,
    "cell_create": mcp_cell_create,
    "cell_list": mcp_cell_list,
    "cell_update": mcp_cell_update,
    "cell_delete": mcp_cell_delete,
    "cell_execute": mcp_cell_execute,
    "notebook_create_version": mcp_notebook_create_version,
    "notebook_list_versions": mcp_notebook_list_versions,
    "template_create": mcp_template_create,
    "template_list": mcp_template_list,
    "notebook_publish": mcp_notebook_publish,
    "notebook_dashboard": mcp_notebook_dashboard,
    "execution_history": mcp_execution_history,
}
