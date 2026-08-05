"""Secrets Manager MCP Server — Exposes secrets management via MCP protocol."""

from app.modules.secrets_manager.mcp.secrets_mcp import (
    list_tools,
    call_tool,
    register_tool,
    _registered_tools,
    _tool_handlers,
)

__all__ = ["list_tools", "call_tool", "register_tool", "_registered_tools", "_tool_handlers"]
