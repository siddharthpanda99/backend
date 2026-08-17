import json
import logging
from typing import List, Dict, Any
from app.mcp.fastmcp_compat import FastMCP
from ..mcp_dependencies import resolve_model_container

logger = logging.getLogger("mcp.tools.models")

def register_model_tools(mcp: FastMCP):
    """Register tools for interacting with the AI model registry and health status."""

    @mcp.tool()
    async def list_ai_models() -> List[Dict[str, Any]]:
        """List all AI models available in the platform registry with their local/remote status."""
        container = resolve_model_container()
        # Verify health before listing
        container.health_monitor.verify_all_models()
        models = container.registry_service.list_models()
        return [m.model_dump() for m in models]

    @mcp.tool()
    async def get_ai_model_details(model_id: str) -> Dict[str, Any]:
        """Retrieve full configuration, parameters, and file status for a specific AI model."""
        container = resolve_model_container()
        model = container.registry_service.get_model(model_id)
        if not model:
            return {"status": "error", "message": f"Model '{model_id}' not found"}
        return model.model_dump()
