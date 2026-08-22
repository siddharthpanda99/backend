"""MCP tools for plugin service discovery and execution.

Lets AI agents discover and invoke plugin services (ctx.llm, ctx.tools, etc.)
via the global PluginContext.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("mcp.tools.plugin_services")


def register_plugin_service_tools(mcp):
    """Register plugin service discovery tools on the MCP server."""

    @mcp.tool()
    async def plugin_list_services() -> List[Dict[str, Any]]:
        """List all available plugin services on the platform.

        Returns service keys with their types and documentation.
        Use plugin_call_service() to invoke a specific service method.
        """
        from app.mcp.plugin_context import get_plugin_ctx
        ctx = get_plugin_ctx()
        if not ctx:
            return [{"error": "PluginContext not initialized"}]

        services = []
        for key in ctx.keys():
            service = ctx.get(key)
            cls = type(service) if service else None
            services.append({
                "key": key,
                "type": cls.__name__ if cls else "unknown",
                "module": cls.__module__ if cls else "",
                "doc": (cls.__doc__ or "")[:200] if cls else "",
                "methods": [
                    m for m in dir(service)
                    if not m.startswith("_") and callable(getattr(service, m, None))
                ] if service else [],
            })
        return services

    @mcp.tool()
    async def plugin_get_service(key: str) -> Dict[str, Any]:
        """Get details about a specific plugin service.

        Args:
            key: Service key (e.g. "llm", "tools", "scheduler", "face_restorer")
        """
        from app.mcp.plugin_context import get_plugin_ctx
        ctx = get_plugin_ctx()
        if not ctx:
            return {"error": "PluginContext not initialized"}

        if not ctx.has(key):
            return {"error": f"Service '{key}' not found"}

        service = ctx.get(key)
        cls = type(service) if service else None
        return {
            "key": key,
            "type": cls.__name__ if cls else "unknown",
            "module": cls.__module__ if cls else "",
            "doc": (cls.__doc__ or "")[:500] if cls else "",
            "methods": [
                {
                    "name": m,
                    "doc": (getattr(getattr(service, m), "__doc__", "") or "")[:150],
                }
                for m in dir(service)
                if not m.startswith("_") and callable(getattr(service, m, None))
            ] if service else [],
        }

    @mcp.tool()
    async def plugin_call_service(
        key: str,
        method: str,
        args: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Call a method on a plugin service.

        Args:
            key:    Service key (e.g. "llm", "tools", "scheduler")
            method: Method name (e.g. "complete", "search", "schedule_interval")
            args:   Method arguments as a dict
        """
        from app.mcp.plugin_context import get_plugin_ctx
        import asyncio

        ctx = get_plugin_ctx()
        if not ctx:
            return {"error": "PluginContext not initialized"}

        if not ctx.has(key):
            return {"error": f"Service '{key}' not found"}

        service = ctx.get(key)
        if not hasattr(service, method):
            return {"error": f"Method '{method}' not found on '{key}'"}

        fn = getattr(service, method)
        if not callable(fn):
            return {"error": f"'{method}' is not callable on '{key}'"}

        try:
            result = fn(**(args or {}))
            # Handle async methods
            if asyncio.iscoroutine(result):
                result = await result

            # Serialize result
            if hasattr(result, "model_dump"):
                return {"result": result.model_dump()}
            if hasattr(result, "dict"):
                return {"result": result.dict()}
            if isinstance(result, (list, tuple)):
                return {"result": [r if isinstance(r, dict) else str(r) for r in result]}
            if isinstance(result, dict):
                return {"result": result}
            return {"result": str(result)}
        except Exception as e:
            return {"error": f"{type(e).__name__}: {e}"}

    @mcp.tool()
    async def plugin_stats() -> Dict[str, Any]:
        """Get plugin system statistics — total services, loaded plugins, context name."""
        from app.mcp.plugin_context import get_plugin_ctx
        ctx = get_plugin_ctx()
        if not ctx:
            return {"total": 0, "error": "PluginContext not initialized"}

        services = ctx.keys()
        return {
            "total_services": len(services),
            "service_keys": services,
            "context_name": ctx.name,
        }

    logger.info("Plugin Service MCP tools registered")
