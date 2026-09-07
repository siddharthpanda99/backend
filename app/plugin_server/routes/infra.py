"""Plugin Server routes — infrastructure plugins (PluginLoader, 39 services)."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response, status

logger = logging.getLogger(__name__)
router = APIRouter()


def _loader(request: Request):
    """Pull the infrastructure plugin loader from app.state."""
    return getattr(request.app.state, "components", {}).get("infra_loader")


@router.get("/plugins")
async def list_infra_plugins(request: Request) -> dict[str, Any]:
    """List all loaded infrastructure plugins."""
    loader = _loader(request)
    if loader is None:
        return {"plugins": [], "error": "infrastructure plugin loader not initialized"}
    return {
        "plugins": [
            {
                "id": pid,
                "class": type(loaded.instance).__name__,
                "provides": loaded.definition.provides,
            }
            for pid, loaded in loader._plugins.items()
        ]
    }


@router.get("/plugins/{plugin_id}")
async def get_infra_plugin(request: Request, plugin_id: str) -> dict[str, Any]:
    """Get a single infrastructure plugin by ID."""
    loader = _loader(request)
    if loader is None:
        raise HTTPException(
            status_code=503, detail="infrastructure plugin loader not initialized"
        )
    loaded = loader._plugins.get(plugin_id)
    if loaded is None:
        raise HTTPException(
            status_code=404, detail=f"Infrastructure plugin '{plugin_id}' not found"
        )
    return {
        "id": plugin_id,
        "class": type(loaded.instance).__name__,
        "definition": {
            "provides": loaded.definition.provides,
            "priority": loaded.definition.priority,
            "enabled": loaded.definition.enabled,
        },
    }


@router.get("/services")
async def list_services(request: Request) -> dict[str, Any]:
    """List services registered in the plugin context."""
    components = getattr(request.app.state, "components", {})
    ctx = components.get("infra_ctx")
    if ctx is None:
        return {"services": []}
    return {"services": list(ctx.keys())}


@router.post("/plugins/{plugin_id}/safe-reload")
async def safe_reload_infra_plugin(
    request: Request, plugin_id: str, response: Response
) -> dict[str, Any]:
    """Safe-reload an infrastructure plugin (drain -> swap -> warm)."""
    from common_lib.modules.plugins.engine.safe_reload import SafeReloadError

    loader = _loader(request)
    if loader is None:
        raise HTTPException(
            status_code=503, detail="infrastructure plugin loader not initialized"
        )
    try:
        ok = loader.safe_reload_plugin(plugin_id)
        if not ok:
            raise HTTPException(
                status_code=404, detail=f"Infrastructure plugin '{plugin_id}' not found"
            )
        return {"success": True, "plugin_id": plugin_id}
    except SafeReloadError as e:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "success": False,
            "error": str(e),
            "detail": "plugin is already reloading",
        }
