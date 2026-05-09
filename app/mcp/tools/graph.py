import logging
from typing import List, Dict, Any, Optional
from mcp.server.fastmcp import FastMCP
from ..mcp_dependencies import resolve_graph_projector

logger = logging.getLogger("mcp.tools.graph")

def register_graph_tools(mcp: FastMCP):
    """Register all Knowledge Graph maintenance and query tools."""

    @mcp.tool()
    async def graph_get_stats() -> Dict[str, Any]:
        """Retrieve overall Knowledge Graph statistics including node counts by category and type."""
        from ..modules.graph.routes.index import get_graph_stats
        return await get_graph_stats()

    @mcp.tool()
    async def graph_search(query: str) -> Dict[str, Any]:
        """Search the Knowledge Graph for nodes matching labels, descriptions, or tags."""
        from ..modules.graph.routes.index import search_graph
        return await search_graph(query)

    @mcp.tool()
    async def graph_project_kb() -> Dict[str, Any]:
        """
        Trigger a projection of the Knowledgebase (Markdown/Documentation) into the Knowledge Graph.
        Parses headers, tags, and internal links to build semantic relationships.
        """
        projector = resolve_graph_projector()
        try:
            projector.project_all()
            from ..modules.graph.routes.index import _load_graph
            graph = await _load_graph(refresh=True)
            return {
                "status": "projected",
                "nodes": graph.summary["nodes"],
                "edges": graph.summary["edges"]
            }
        except Exception as e:
            logger.error(f"KB Projection failed: {e}")
            return {"status": "error", "message": str(e)}

    @mcp.tool()
    async def graph_clear(confirm: bool = False) -> Dict[str, str]:
        """
        [DESTRUCTIVE] Clear the Knowledge Graph. 
        Requires 'confirm=True' to execute.
        """
        from ..modules.graph.routes.index import clear_graph
        return await clear_graph(confirm)
