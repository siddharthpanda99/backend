import logging
from typing import Dict, Any
from mcp.server.fastmcp import FastMCP
from common_lib.modules.graph import GraphService

logger = logging.getLogger("mcp.tools.graph")

_svc = GraphService()


def register_graph_tools(mcp: FastMCP):
    """Register all Knowledge Graph maintenance and query tools."""

    @mcp.tool()
    async def graph_get_stats() -> Dict[str, Any]:
        """Retrieve overall Knowledge Graph statistics including node counts by category and type."""
        return await _svc.get_stats()

    @mcp.tool()
    async def graph_search(query: str) -> Dict[str, Any]:
        """Search the Knowledge Graph for nodes matching labels, descriptions, or tags."""
        return await _svc.search(query)

    @mcp.tool()
    async def graph_project_kb() -> Dict[str, Any]:
        """
        Trigger a projection of the Knowledgebase (Markdown/Documentation) into the Knowledge Graph.
        Parses headers, tags, and internal links to build semantic relationships.
        """
        try:
            result = await _svc.project_knowledgebase()
            return result
        except Exception as e:
            logger.error(f"KB Projection failed: {e}")
            return {"status": "error", "message": f"{type(e).__name__}: {e}"}

    @mcp.tool()
    async def graph_clear(confirm: bool = False) -> Dict[str, str]:
        """
        [DESTRUCTIVE] Clear the Knowledge Graph. 
        Requires 'confirm=True' to execute.
        """
        return await _svc.clear_graph(confirm)
