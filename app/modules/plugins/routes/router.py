"""Plugin Routes — Plugin discovery, listing, and execution API."""

from fastapi import APIRouter, HTTPException
from typing import Optional
import logging

from common_lib.modules.plugins.manager import PluginManager
from common_lib.modules.plugins.schemas import PluginResponse, PluginDetailResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/plugins", tags=["plugins"])


@router.get("")
async def list_plugins(
    category: Optional[str] = None,
    search: Optional[str] = None,
):
    """List all available plugins."""
    manager = PluginManager()
    plugins = manager.engine.list_plugins()
    
    results = []
    for p in plugins:
        health = p.check_health()
        results.append({
            "id": p.id,
            "name": p.metadata.name,
            "description": p.metadata.description,
            "category": p.metadata.category,
            "version": p.metadata.version,
            "status": health.status.value,
            "total_tools": p.total_tools,
            "total_nodes": p.total_nodes,
        })
    
    if category:
        results = [r for r in results if r["category"] == category]
    if search:
        q = search.lower()
        results = [r for r in results if q in r["name"].lower() or q in (r.get("description") or "").lower()]
    
    return {"plugins": results}


@router.get("/categories")
async def list_categories():
    """List all available plugin categories."""
    manager = PluginManager()
    plugins = manager.engine.list_plugins()
    categories = set()
    for p in plugins:
        if p.metadata.category:
            categories.add(p.metadata.category)
    return {"categories": sorted(categories)}


@router.get("/{plugin_id}")
async def get_plugin(plugin_id: str):
    """Get detailed info about a specific plugin."""
    manager = PluginManager()
    for p in manager.engine.list_plugins():
        if p.id == plugin_id:
            health = p.check_health()
            nodes = p.get_nodes()
            return {
                "id": p.id,
                "name": p.metadata.name,
                "description": p.metadata.description,
                "category": p.metadata.category,
                "version": p.metadata.version,
                "status": health.status.value,
                "total_tools": len([n for n in nodes if n.get("entity_type") == "tool"]),
                "total_nodes": len(nodes),
                "nodes": nodes,
            }
    raise HTTPException(status_code=404, detail=f"Plugin '{plugin_id}' not found")


@router.post("/{plugin_id}/execute/{tool_name}")
async def execute_tool(plugin_id: str, tool_name: str, params: dict = {}):
    """Execute a specific tool on a plugin."""
    manager = PluginManager()
    for p in manager.engine.list_plugins():
        if p.id == plugin_id:
            handler = p.get_node_handler(f"{plugin_id}.{tool_name}")
            if not handler:
                raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found in plugin '{plugin_id}'")
            try:
                result = handler(**params)
                return {"success": True, "result": result}
            except Exception as e:
                logger.error(f"Error executing {plugin_id}.{tool_name}: {e}")
                return {"success": False, "error": str(e)}
    raise HTTPException(status_code=404, detail=f"Plugin '{plugin_id}' not found")
