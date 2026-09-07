"""Main backend — Plugin Server proxy.

The frontend (platform-demo) hits the main backend at
``/api/plugin-server/panels/*``. This module proxies those calls
to the standalone Plugin Server (port 8081) via
``PluginServerClient``.

Endpoints:

  GET  /api/plugin-server/panels                  -> GET /panels
  GET  /api/plugin-server/panels/{panel_id}       -> GET /panels/{panel_id}?mode=...
  POST /api/plugin-server/panels/{panel_id}/render -> POST /panels/{panel_id}/render
  GET  /api/plugin-server/health                  -> GET /health

This keeps the frontend from having to know about port 8081.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException

from app.plugin_server.client import (
    PluginServerError,
    PluginServerUnreachable,
    get_plugin_server_client,
)

logger = logging.getLogger(__name__)
router = APIRouter()


def _client():
    """Get the PluginServerClient singleton.

    Returns None if PLUGIN_SERVER_ENABLED=0 (legacy in-process
    mode). In that case, the routes return 503.
    """
    return get_plugin_server_client()


@router.get("/panels")
async def list_panels() -> dict[str, Any]:
    """List all panel specs (for the UI launcher)."""
    client = _client()
    if client is None:
        raise HTTPException(
            status_code=503,
            detail="Plugin Server is disabled (PLUGIN_SERVER_ENABLED=0)",
        )
    try:
        return client.list_panels()
    except PluginServerUnreachable as e:
        logger.error(f"Plugin Server unreachable: {e}")
        raise HTTPException(status_code=503, detail=str(e))
    except PluginServerError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/panels/{panel_id}")
async def get_panel(panel_id: str, mode: str = "ui") -> dict[str, Any]:
    """Get a panel's spec or rendered output."""
    client = _client()
    if client is None:
        raise HTTPException(
            status_code=503,
            detail="Plugin Server is disabled (PLUGIN_SERVER_ENABLED=0)",
        )
    try:
        return client.get_panel(panel_id, mode=mode)
    except PluginServerUnreachable as e:
        raise HTTPException(status_code=503, detail=str(e))
    except PluginServerError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/panels/{panel_id}/render")
async def render_panel(panel_id: str, body: dict) -> dict[str, Any]:
    """Render a panel with a payload."""
    client = _client()
    if client is None:
        raise HTTPException(
            status_code=503,
            detail="Plugin Server is disabled (PLUGIN_SERVER_ENABLED=0)",
        )
    try:
        return client.render_panel(
            panel_id,
            mode=body.get("mode", "ui"),
            payload=body.get("payload", {}),
        )
    except PluginServerUnreachable as e:
        raise HTTPException(status_code=503, detail=str(e))
    except PluginServerError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/health")
async def plugin_server_health() -> dict[str, Any]:
    """Liveness check of the Plugin Server."""
    client = _client()
    if client is None:
        return {"status": "disabled", "plugin_server_enabled": False}
    if client.health():
        return {"status": "ok", "plugin_server_enabled": True}
    raise HTTPException(status_code=503, detail="Plugin Server not reachable")


__all__ = ["router"]
