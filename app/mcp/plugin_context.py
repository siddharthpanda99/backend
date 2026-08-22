"""Shared plugin context accessor for MCP tools.

Provides a central way for any MCP tool to access the global PluginContext
and its registered services (ctx.llm, ctx.tools, ctx.scheduler, etc.).

Usage in MCP tools:
    from app.mcp.plugin_context import get_plugin_ctx, require_plugin_ctx

    # Optional access (returns None if not initialized)
    ctx = get_plugin_ctx()
    if ctx and ctx.has("llm"):
        result = ctx.llm.complete(...)

    # Required access (raises if not initialized)
    ctx = require_plugin_ctx()
    result = ctx.llm.complete(...)
"""

import logging
from typing import Optional

logger = logging.getLogger("mcp.plugin_context")


def get_plugin_ctx():
    """Get the global PluginContext (returns None if not initialized).

    This is the preferred way for MCP tools to access plugin services.
    The context is set during FastAPI startup in main.py.
    """
    try:
        from common_lib.modules.orchestration.plugin import get_context
        ctx = get_context()
        # Verify it has services loaded (not just an empty fallback)
        if ctx and ctx.keys():
            return ctx
        return None
    except Exception as e:
        logger.debug(f"Plugin context unavailable: {e}")
        return None


def require_plugin_ctx():
    """Get the global PluginContext, raising if not available."""
    ctx = get_plugin_ctx()
    if ctx is None:
        raise RuntimeError(
            "PluginContext not initialized. "
            "Ensure the FastAPI server has started and plugins are loaded."
        )
    return ctx


def has_service(service_key: str) -> bool:
    """Check if a plugin service is available."""
    ctx = get_plugin_ctx()
    return ctx is not None and ctx.has(service_key)


def get_service(service_key: str, default=None):
    """Get a plugin service by key, returning default if not found."""
    ctx = get_plugin_ctx()
    if ctx and ctx.has(service_key):
        return ctx.get(service_key)
    return default
