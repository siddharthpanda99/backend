"""Plugin Server routes — tool plugins (BaseToolPlugin subclasses)."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response, status

logger = logging.getLogger(__name__)
router = APIRouter()


def _mgr(request: Request):
    """Pull the tool manager from app.state (set in lifespan)."""
    mgr = getattr(request.app.state, "components", {}).get("tool_manager")
    if mgr is None:
        raise HTTPException(
            status_code=503, detail="Tool plugin manager not initialized"
        )
    return mgr


@router.get("")
async def list_plugins(
    request: Request,
    category: str | None = None,
    search: str | None = None,
) -> dict[str, Any]:
    """List all loaded tool plugins."""
    mgr = _mgr(request)
    plugins = mgr.engine.list_plugins()
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
async def list_categories(request: Request) -> dict[str, Any]:
    """List all available tool plugin categories."""
    mgr = _mgr(request)
    plugins = mgr.engine.list_plugins()
    categories = sorted({p.metadata.category for p in plugins if p.metadata.category})
    return {"categories": categories}


@router.get("/{plugin_id}")
async def get_plugin(request: Request, plugin_id: str) -> dict[str, Any]:
    """Get detailed info about a single tool plugin."""
    mgr = _mgr(request)
    for p in mgr.engine.list_plugins():
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
                "total_tools": sum(1 for n in nodes if n.get("entity_type") == "tool"),
                "total_nodes": len(nodes),
                "nodes": nodes,
            }
    raise HTTPException(status_code=404, detail=f"Plugin '{plugin_id}' not found")


@router.get("/{plugin_id}/tools")
async def list_plugin_tools(request: Request, plugin_id: str) -> dict[str, Any]:
    """List a plugin's tools with their @node metadata."""
    mgr = _mgr(request)
    for p in mgr.engine.list_plugins():
        if p.id == plugin_id:
            return {"plugin_id": plugin_id, "tools": p.get_nodes()}
    raise HTTPException(status_code=404, detail=f"Plugin '{plugin_id}' not found")


@router.post("/{plugin_id}/safe-reload")
async def safe_reload_plugin(
    request: Request, plugin_id: str, response: Response
) -> dict[str, Any]:
    """Hot-reload a single plugin with drain -> swap -> warm."""
    from common_lib.modules.plugins.engine.safe_reload import SafeReloadError

    mgr = _mgr(request)
    try:
        reload_id = mgr.safe_reload_plugin(plugin_id)
        return {"success": True, "plugin_id": plugin_id, "reload_id": reload_id}
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Plugin '{plugin_id}' not found")
    except SafeReloadError as e:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "success": False,
            "error": str(e),
            "detail": "plugin is already reloading",
        }


@router.post("/reload")
async def reload_all(request: Request) -> dict[str, Any]:
    """Naive reload of ALL tool plugins (no drain)."""
    mgr = _mgr(request)
    n = mgr.reload()
    return {"success": True, "plugins_loaded": n}
