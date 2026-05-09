import logging
from typing import List, Dict, Any, Optional
from mcp.server.fastmcp import FastMCP
from ..mcp_dependencies import resolve_dip_service

logger = logging.getLogger("mcp.tools.data_pipeline")

def register_data_pipeline_tools(mcp: FastMCP):
    """Register tools for data ingestion and integration pipelines (DIP)."""

    @mcp.tool()
    async def list_data_pipelines() -> List[Dict[str, Any]]:
        """List all configured data integration pipelines."""
        service = resolve_dip_service()
        pipelines = await service.list_pipelines()
        return [p.model_dump() for p in pipelines]

    @mcp.tool()
    async def get_pipeline_status(pipeline_id: str) -> Dict[str, Any]:
        """Retrieve the current status and latest run results for a specific pipeline."""
        service = resolve_dip_service()
        return await service.get_pipeline_status(pipeline_id)

    @mcp.tool()
    async def run_data_pipeline(pipeline_id: str, trigger_type: str = "manual") -> Dict[str, Any]:
        """Trigger an immediate execution of a data pipeline."""
        service = resolve_dip_service()
        return await service.run_pipeline(pipeline_id, trigger_type)

    @mcp.tool()
    async def list_ingestion_sources() -> List[Dict[str, Any]]:
        """List all active data ingestion sources (databases, APIs, file streams)."""
        service = resolve_dip_service()
        return await service.list_sources()
