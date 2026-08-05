"""Plugin MCP Server — Exposes plugin discovery and execution via MCP protocol.

MCP tools:
- list_plugins: List all available plugins
- get_plugin: Get detailed plugin info
- execute_tool: Execute a specific tool on a plugin
- check_health: Check plugin health
- search_plugins: Search plugins by keyword
"""

import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# In-memory tool registrations
_registered_tools: List[Dict[str, Any]] = []
_tool_handlers: Dict[str, callable] = {}


def register_tool(name: str, description: str, input_schema: Optional[Dict[str, Any]] = None):
    """Decorator to register a tool with the MCP server."""
    def decorator(func):
        _registered_tools.append({
            "name": name,
            "description": description,
            "inputSchema": input_schema or {"type": "object", "properties": {}},
        })
        _tool_handlers[name] = func
        return func
    return decorator


def list_tools() -> List[Dict[str, Any]]:
    """Return all registered MCP tools."""
    return _registered_tools


def call_tool(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a registered MCP tool by name."""
    handler = _tool_handlers.get(name)
    if not handler:
        return {"error": f"Tool '{name}' not found", "success": False}
    try:
        result = handler(**arguments)
        return {"result": result, "success": True}
    except Exception as e:
        logger.error(f"MCP tool '{name}' error: {e}")
        return {"error": str(e), "success": False}


# ── Tool Implementations ────────────────────────────────────────────────────

@register_tool(
    name="list_plugins",
    description="List all available plugins with their status, category, and tool counts",
    input_schema={
        "type": "object",
        "properties": {
            "category": {"type": "string", "description": "Optional category filter"},
            "search": {"type": "string", "description": "Optional search query"},
        },
    },
)
def _list_plugins(category: Optional[str] = None, search: Optional[str] = None) -> List[Dict[str, Any]]:
    from common_lib.modules.plugins.manager import PluginManager
    manager = PluginManager()
    plugins = manager.engine.list_plugins()
    results = []
    for p in plugins:
        health = p.check_health()
        results.append({
            "id": p.id,
            "name": p.metadata.name,
            "description": p.metadata.description,
            "category": p.metadata.category,
            "version": p.metadata.version,
            "status": health.status.value,
            "total_tools": len([n for n in p.get_nodes() if n.get("entity_type") == "tool"]),
        })
    if category:
        results = [r for r in results if r["category"] == category]
    if search:
        q = search.lower()
        results = [r for r in results if q in r["name"].lower() or q in (r.get("description") or "").lower()]
    return results


@register_tool(
    name="get_plugin",
    description="Get detailed information about a specific plugin including all tools and health status",
    input_schema={
        "type": "object",
        "properties": {
            "plugin_id": {"type": "string", "description": "The plugin ID"},
        },
        "required": ["plugin_id"],
    },
)
def _get_plugin(plugin_id: str) -> Optional[Dict[str, Any]]:
    from common_lib.modules.plugins.manager import PluginManager
    manager = PluginManager()
    for p in manager.engine.list_plugins():
        if p.id == plugin_id:
            health = p.check_health()
            nodes = p.get_nodes()
            return {
                "id": p.id,
                "name": p.metadata.name,
                "description": p.metadata.description,
                "category": p.metadata.category,
                "version": p.metadata.version,
                "status": health.status.value,
                "tools": nodes,
            }
    return None


@register_tool(
    name="execute_plugin_tool",
    description="Execute a specific tool on a registered plugin with provided parameters",
    input_schema={
        "type": "object",
        "properties": {
            "plugin_id": {"type": "string", "description": "Plugin ID"},
            "tool_name": {"type": "string", "description": "Tool/method name to execute"},
            "params": {"type": "object", "description": "Parameters as key-value pairs"},
        },
        "required": ["plugin_id", "tool_name"],
    },
)
def _execute_tool(plugin_id: str, tool_name: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    from common_lib.modules.plugins.manager import PluginManager
    manager = PluginManager()
    for p in manager.engine.list_plugins():
        if p.id == plugin_id:
            handler = p.get_node_handler(f"{plugin_id}.{tool_name}")
            if not handler:
                return {"success": False, "error": f"Tool '{tool_name}' not found"}
            try:
                result = handler(**(params or {}))
                return {"success": True, "result": result}
            except Exception as e:
                return {"success": False, "error": str(e)}
    return {"success": False, "error": f"Plugin '{plugin_id}' not found"}


@register_tool(
    name="check_plugin_health",
    description="Check health status of a plugin, including missing API keys or dependencies",
    input_schema={
        "type": "object",
        "properties": {
            "plugin_id": {"type": "string", "description": "The plugin ID to check"},
        },
        "required": ["plugin_id"],
    },
)
def _check_health(plugin_id: str) -> Optional[Dict[str, Any]]:
    from common_lib.modules.plugins.manager import PluginManager
    manager = PluginManager()
    for p in manager.engine.list_plugins():
        if p.id == plugin_id:
            health = p.check_health()
            return {
                "plugin_id": p.id,
                "status": health.status.value,
                "message": health.message,
                "missing_keys": health.missing_keys,
            }
    return None


@register_tool(
    name="search_plugins",
    description="Search for plugins by keyword in name and description fields",
    input_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search keyword"},
        },
        "required": ["query"],
    },
)
def _search_plugins(query: str) -> List[Dict[str, Any]]:
    from common_lib.modules.plugins.manager import PluginManager
    manager = PluginManager()
    q = query.lower()
    results = []
    for p in manager.engine.list_plugins():
        if q in p.metadata.name.lower() or q in (p.metadata.description or "").lower():
            health = p.check_health()
            results.append({
                "id": p.id,
                "name": p.metadata.name,
                "description": p.metadata.description,
                "category": p.metadata.category,
                "status": health.status.value,
            })
    return results


__all__ = ["list_tools", "call_tool", "register_tool", "_registered_tools", "_tool_handlers"]
