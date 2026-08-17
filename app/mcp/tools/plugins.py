import logging
from typing import List, Dict, Any, Optional
from app.mcp.fastmcp_compat import FastMCP
from ..mcp_dependencies import resolve_plugin_manager

logger = logging.getLogger("mcp.tools.plugins")

def register_plugin_tools(mcp: FastMCP):
    """Register all platform extension and plugin management tools."""

    @mcp.tool()
    async def plugin_list(category: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all registered plugins on the platform, optionally filtered by category."""
        manager = resolve_plugin_manager()
        plugins = manager.list_plugins()
        if category:
            return [p for p in plugins if p.get("category") == category]
        return plugins

    @mcp.tool()
    async def plugin_onboard(repo_url: str, name: Optional[str] = None) -> Dict[str, Any]:
        """
        Onboard a new plugin from a Git repository.
        The platform will clone, analyze, and register the plugin automatically.
        """
        manager = resolve_plugin_manager()
        try:
            result = await manager.onboard_plugin(repo_url, name)
            return result
        except Exception as e:
            logger.error(f"Plugin onboarding failed: {e}")
            return {"status": "error", "message": str(e)}

    @mcp.tool()
    async def plugin_analyze(plugin_id: str) -> Dict[str, Any]:
        """Perform a deep analysis of a plugin's manifest, capabilities, and security profile."""
        manager = resolve_plugin_manager()
        try:
            return await manager.analyze_plugin(plugin_id)
        except Exception as e:
            logger.error(f"Plugin analysis failed: {e}")
            return {"status": "error", "message": str(e)}

    @mcp.tool()
    async def plugin_set_state(plugin_id: str, enabled: bool) -> Dict[str, Any]:
        """Enable or disable a specific plugin."""
        manager = resolve_plugin_manager()
        try:
            manager.set_plugin_state(plugin_id, enabled)
            return {"status": "success", "plugin_id": plugin_id, "enabled": enabled}
        except Exception as e:
            logger.error(f"Failed to set plugin state: {e}")
            return {"status": "error", "message": str(e)}
