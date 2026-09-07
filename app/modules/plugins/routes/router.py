"""Plugin Routes — Plugin discovery, listing, and execution API."""

from fastapi import APIRouter, HTTPException
from typing import Optional
import logging

from common_lib.modules.plugins.manager import get_plugin_manager
from common_lib.modules.plugins.schemas import PluginResponse, PluginDetailResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/plugins", tags=["plugins"])


@router.get("")
async def list_plugins(
    category: Optional[str] = None,
    search: Optional[str] = None,
):
    """List all available plugins."""
    manager = get_plugin_manager()  # process-wide singleton, auto-starts
    plugins = manager.engine.list_plugins()

    results = []
    for p in plugins:
        health = p.check_health()
        results.append(
            {
                "id": p.id,
                "name": p.metadata.name,
                "description": p.metadata.description,
                "category": p.metadata.category,
                "version": p.metadata.version,
                "status": health.status.value,
                "total_tools": p.total_tools,
                "total_nodes": p.total_nodes,
            }
        )

    if category:
        results = [r for r in results if r["category"] == category]
    if search:
        q = search.lower()
        results = [
            r
            for r in results
            if q in r["name"].lower() or q in (r.get("description") or "").lower()
        ]

    return {"plugins": results}


@router.get("/categories")
async def list_categories():
    """List all available plugin categories."""
    manager = get_plugin_manager()
    plugins = manager.engine.list_plugins()
    categories = set()
    for p in plugins:
        if p.metadata.category:
            categories.add(p.metadata.category)
    return {"categories": sorted(categories)}


@router.get("/{plugin_id}")
async def get_plugin(plugin_id: str):
    """Get detailed info about a specific plugin."""
    manager = get_plugin_manager()
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
                "total_tools": len(
                    [n for n in nodes if n.get("entity_type") == "tool"]
                ),
                "total_nodes": len(nodes),
                "nodes": nodes,
            }
    raise HTTPException(status_code=404, detail=f"Plugin '{plugin_id}' not found")


@router.post("/{plugin_id}/execute/{tool_name}")
async def execute_tool(plugin_id: str, tool_name: str, params: dict = {}):
    """Execute a specific tool on a plugin."""
    manager = get_plugin_manager()
    for p in manager.engine.list_plugins():
        if p.id == plugin_id:
            handler = p.get_node_handler(f"{plugin_id}.{tool_name}")
            if not handler:
                raise HTTPException(
                    status_code=404,
                    detail=f"Tool '{tool_name}' not found in plugin '{plugin_id}'",
                )
            try:
                result = handler(**params)
                return {"success": True, "result": result}
            except Exception as e:
                logger.error(f"Error executing {plugin_id}.{tool_name}: {e}")
                return {"success": False, "error": str(e)}
    raise HTTPException(status_code=404, detail=f"Plugin '{plugin_id}' not found")


@router.post("/{plugin_id}/safe-reload")
async def safe_reload_plugin(plugin_id: str):
    """Hot-reload a single plugin using the SafeReload protocol.

    Drains in-flight calls (up to drain_timeout_sec), swaps the
    instance atomically, and resumes. Returns the reload id.
    """
    from fastapi.responses import JSONResponse
    from common_lib.modules.plugins.engine.safe_reload import SafeReloadError

    manager = get_plugin_manager()
    try:
        reload_id = manager.safe_reload_plugin(plugin_id)
        return {"success": True, "plugin_id": plugin_id, "reload_id": reload_id}
    except KeyError:
        raise HTTPException(
            status_code=404, detail=f"Plugin '{plugin_id}' not found"
        )
    except SafeReloadError as e:
        return JSONResponse(
            status_code=503,
            content={
                "success": False,
                "error": str(e),
                "detail": "plugin is already reloading; retry shortly",
            },
            headers={"Retry-After": "5"},
        )
    except Exception as e:
        logger.error(f"Error reloading {plugin_id}: {e}")
        return {"success": False, "error": str(e)}


@router.post("/reload")
async def safe_reload_all():
    """Hot-reload ALL plugins (naive, clears in-flight state).

    This is the "I'm in dev and nothing matters" endpoint. It
    re-runs discover_and_load() which clears all slots. For
    per-plugin graceful reload, use POST /plugins/{id}/safe-reload.
    """
    manager = get_plugin_manager()
    n = manager.reload()
    return {"success": True, "plugins_loaded": n}
