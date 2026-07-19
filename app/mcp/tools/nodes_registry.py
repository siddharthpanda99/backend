"""MCP tools for Nodes Registry — discover and query all @node wrappers.

Registered under the Cognitive Orchestrator MCP server.
Wraps common_lib.modules.nodes_registry for node discovery.
"""

import logging
from typing import List, Dict, Any, Optional
from mcp.server.fastmcp import FastMCP

logger = logging.getLogger("mcp.tools.nodes_registry")

# Module-level cache: discover_nodes() scans filesystem; avoid repeated calls
_nodes_cache: Optional[List[Dict[str, Any]]] = None
_nodes_by_name: Dict[str, Dict[str, Any]] = {}


def _get_nodes() -> List[Dict[str, Any]]:
    """Return cached list of all discovered nodes, refreshing on first call."""
    global _nodes_cache, _nodes_by_name
    if _nodes_cache is None:
        try:
            from common_lib.modules.plugins.discovery import discover_nodes
            _nodes_cache = list(discover_nodes())
        except Exception as e:
            logger.error(f"discover_nodes failed: {e}")
            _nodes_cache = []
        _nodes_by_name = {n.get("name", ""): n for n in _nodes_cache if n.get("name")}
    return _nodes_cache


def register_nodes_registry_tools(mcp: FastMCP):
    """Register tools for the global node registry."""

    @mcp.tool()
    async def nodes_list_all() -> List[Dict[str, Any]]:
        """List all registered @node wrappers across all modules."""
        nodes = _get_nodes()
        return [
            {
                "name": n.get("name", ""),
                "category": n.get("category", ""),
                "description": n.get("description", ""),
                "tags": n.get("tags", []),
            }
            for n in nodes
        ]

    @mcp.tool()
    async def nodes_search(query: str = "", category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search nodes by name, description, or category."""
        nodes = _get_nodes()
        results = nodes
        if query:
            q = query.lower()
            results = [
                n for n in results
                if q in n.get("name", "").lower()
                or q in n.get("description", "").lower()
                or any(q in t.lower() for t in n.get("tags", []))
            ]
        if category:
            results = [n for n in results if n.get("category", "").lower() == category.lower()]
        return [
            {
                "name": n.get("name", ""),
                "category": n.get("category", ""),
                "description": n.get("description", ""),
                "tags": n.get("tags", []),
            }
            for n in results
        ]

    @mcp.tool()
    async def nodes_list_categories() -> List[Dict[str, Any]]:
        """List all node categories with counts."""
        nodes = _get_nodes()
        cats: Dict[str, int] = {}
        for n in nodes:
            cat = n.get("category", "unknown")
            cats[cat] = cats.get(cat, 0) + 1
        return [{"category": k, "count": v} for k, v in sorted(cats.items(), key=lambda x: -x[1])]

    @mcp.tool()
    async def nodes_get_details(node_name: str) -> Dict[str, Any]:
        """Get detailed information about a specific node by name."""
        if not node_name:
            return {"error": "node_name is required"}
        _get_nodes()  # ensure cache is populated
        n = _nodes_by_name.get(node_name)
        if n is None:
            return {"error": f"Node '{node_name}' not found"}
        return {
            "name": n.get("name", ""),
            "category": n.get("category", ""),
            "description": n.get("description", ""),
            "tags": n.get("tags", []),
            "input_schema": n.get("input_schema", {}),
            "output_schema": n.get("output_schema", {}),
            "audience": n.get("audience", []),
            "execution_timeout": n.get("execution_timeout", 30),
        }

    @mcp.tool()
    async def nodes_stats() -> Dict[str, Any]:
        """Get statistics about all registered nodes."""
        nodes = _get_nodes()
        if not nodes:
            return {"total": 0, "categories": 0, "top_tags": []}
        cats = set(n.get("category", "unknown") for n in nodes)
        tags: Dict[str, int] = {}
        for n in nodes:
            for t in n.get("tags", []):
                tags[t] = tags.get(t, 0) + 1
        top_tags = sorted(tags.items(), key=lambda x: -x[1])[:10]
        return {
            "total": len(nodes),
            "categories": len(cats),
            "top_tags": [{"tag": t, "count": c} for t, c in top_tags],
        }

    logger.info("Nodes Registry: 5 MCP tools registered")
