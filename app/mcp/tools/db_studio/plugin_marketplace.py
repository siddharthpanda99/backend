"""MCP tools for Plugin Marketplace & Extension SDK (UDS Module 23)."""

from typing import Optional

from common_lib.modules.db_studio.plugin_marketplace import (
    PluginMarketplaceService,
    PluginCreate, PluginUpdate,
    PluginVersionCreate,
    ReviewCreate,
    MarketplaceCatalogUpdate,
    InstallRequest,
)

svc = PluginMarketplaceService()


def mcp_plugin_create(name: str, display_name: str, plugin_type: str = "backend_service",
                       description: str = None, author: str = None) -> dict:
    """Register a new plugin."""
    req = PluginCreate(
        name=name, display_name=display_name, plugin_type=plugin_type,
        description=description, author=author,
    )
    result = svc.create_plugin(req)
    return result.model_dump()


def mcp_plugin_list(plugin_type: str = None, is_installed: bool = None,
                     limit: int = 50) -> list:
    """List plugins with optional filters."""
    results = svc.list_plugins(plugin_type, is_installed, limit=limit)
    return [r.model_dump() for r in results]


def mcp_plugin_get(plugin_id: str) -> Optional[dict]:
    """Get a plugin by ID."""
    result = svc.get_plugin(plugin_id)
    return result.model_dump() if result else None


def mcp_plugin_enable(plugin_id: str) -> Optional[dict]:
    """Enable a plugin."""
    result = svc.enable_plugin(plugin_id)
    return result.model_dump() if result else None


def mcp_plugin_disable(plugin_id: str) -> Optional[dict]:
    """Disable a plugin."""
    result = svc.disable_plugin(plugin_id)
    return result.model_dump() if result else None


def mcp_plugin_create_version(plugin_id: str, version: str,
                               changelog: str = None) -> Optional[dict]:
    """Create a new plugin version."""
    req = PluginVersionCreate(version=version, changelog=changelog)
    result = svc.create_version(plugin_id, req)
    return result.model_dump() if result else None


def mcp_plugin_install(plugin_id: str, workspace_id: str = None) -> Optional[dict]:
    """Install a plugin."""
    req = InstallRequest(workspace_id=workspace_id)
    result = svc.install_plugin(plugin_id, req)
    return result.model_dump() if result else None


def mcp_plugin_uninstall(plugin_id: str) -> bool:
    """Uninstall a plugin."""
    return svc.uninstall_plugin(plugin_id)


def mcp_marketplace_list(category: str = None, is_featured: bool = None,
                          limit: int = 50) -> list:
    """List marketplace catalog."""
    results = svc.list_marketplace(category, is_featured, limit=limit)
    return [r.model_dump() for r in results]


def mcp_plugin_review_create(plugin_id: str, user_id: str = "api",
                              rating: int = 5, body: str = None) -> dict:
    """Create a review for a plugin."""
    req = ReviewCreate(rating=rating, body=body)
    result = svc.create_review(plugin_id, user_id, req)
    return result.model_dump()


def mcp_plugin_dashboard() -> dict:
    """Get plugin marketplace dashboard summary."""
    result = svc.get_dashboard()
    return result.model_dump()


def register_plugin_marketplace_tools(mcp_server):
    """Register all plugin marketplace tools with the MCP server."""
    for name, fn in TOOLS.items():
        mcp_server.tool(name=name)(fn)
    return mcp_server


TOOLS = {
    "plugin_create": mcp_plugin_create,
    "plugin_list": mcp_plugin_list,
    "plugin_get": mcp_plugin_get,
    "plugin_enable": mcp_plugin_enable,
    "plugin_disable": mcp_plugin_disable,
    "plugin_create_version": mcp_plugin_create_version,
    "plugin_install": mcp_plugin_install,
    "plugin_uninstall": mcp_plugin_uninstall,
    "marketplace_list": mcp_marketplace_list,
    "plugin_review_create": mcp_plugin_review_create,
    "plugin_dashboard": mcp_plugin_dashboard,
}
