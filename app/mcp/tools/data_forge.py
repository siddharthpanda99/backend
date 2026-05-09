import logging
from typing import List, Dict, Any, Optional
from mcp.server.fastmcp import FastMCP
from ..mcp_dependencies import resolve_data_forge_engine

logger = logging.getLogger("mcp.tools.data_forge")

def register_data_forge_tools(mcp: FastMCP):
    """Register all DataForge simulation and snapshot tools."""

    @mcp.tool()
    async def data_forge_list_categories() -> List[str]:
        """List all available DataForge simulation categories (e.g. 'finance', 'hr', 'inventory')."""
        engine = resolve_data_forge_engine()
        return list(engine.templates.keys())

    @mcp.tool()
    async def data_forge_get_snapshot(category: str = "finance") -> Dict[str, Any]:
        """
        Retrieve a full data snapshot for a specific DataForge category.
        Includes initial states and template metadata.
        """
        engine = resolve_data_forge_engine()
        from common_lib.modules.data_forge.service import market_service
        
        live_data = None
        if category == "finance":
            ids = [t["id"] for t in engine.templates.get("finance", {}).get("tickers", [])]
            if ids:
                try:
                    live_data = await market_service.get_live_market_data(ids)
                except Exception as e:
                    logger.warning(f"Failed to fetch live market data for snapshot: {e}")
        
        return engine.get_full_snapshot(category, live_data=live_data)
