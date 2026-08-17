"""FastMCP compatibility shim.

The installed mcp package may have either `FastMCP` (older) or `MCPServer` (newer).
This module exports `FastMCP` regardless of which version is installed.
"""
try:
    from mcp.server.fastmcp import FastMCP  # type: ignore[import-untyped]
except ImportError:
    try:
        from mcp.server import MCPServer as FastMCP  # type: ignore[assignment]
    except ImportError:
        raise ImportError(
            "No compatible MCP server class found. "
            "Install 'mcp' package: pip install mcp"
        )

__all__ = ["FastMCP"]
