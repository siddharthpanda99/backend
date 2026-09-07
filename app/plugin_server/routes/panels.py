"""Plugin Server — Panels REST API.

Endpoints:

  GET  /panels                  - List all panel specs (for UI launcher)
  GET  /panels/{panel_id}       - Get a panel's spec + health
  POST /panels/{panel_id}/render - Render a panel (mode + payload)

These power the React UI's "Harness" pages, and also serve as
the API for agents that want to drive the panel programmatically.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

logger = logging.getLogger(__name__)
router = APIRouter()


def _registry(request: Request):
    """Get the PanelRegistry from app.state."""
    return getattr(request.app.state, "components", {}).get("panel_registry")


@router.get("")
async def list_panels(request: Request) -> dict[str, Any]:
    """List all registered panel specs."""
    reg = _registry(request)
    if reg is None:
        return {"panels": []}
    return {
        "panels": reg.list_specs(),
    }


@router.get("/{panel_id}")
async def get_panel(
    request: Request,
    panel_id: str,
    mode: str = Query("ui", description="ui | spec | api"),
) -> dict[str, Any]:
    """Get a panel's full render in the requested mode.

    mode=spec -> static info (id, title, description, schema)
    mode=ui   -> spec + form schema (no execution)
    mode=api  -> execute with empty payload and return result only
    """
    reg = _registry(request)
    if reg is None:
        raise HTTPException(status_code=503, detail="panel registry not initialized")
    panel = reg.get(panel_id)
    if panel is None:
        raise HTTPException(status_code=404, detail=f"panel '{panel_id}' not found")
    try:
        return panel.render(mode=mode)
    except Exception as e:
        logger.exception(f"Panel {panel_id} render(mode={mode}) failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{panel_id}/render")
async def render_panel(
    request: Request,
    panel_id: str,
    body: dict,
) -> dict[str, Any]:
    """Render a panel with a payload.

    Body:
        {
            "mode": "ui" | "api",        (default "ui")
            "payload": {...},            (form data)
        }

    Returns the rendered panel in the chosen mode.
    """
    reg = _registry(request)
    if reg is None:
        raise HTTPException(status_code=503, detail="panel registry not initialized")
    panel = reg.get(panel_id)
    if panel is None:
        raise HTTPException(status_code=404, detail=f"panel '{panel_id}' not found")
    mode = body.get("mode", "ui")
    payload = body.get("payload", {})
    try:
        return panel.render(mode=mode, payload=payload)
    except Exception as e:
        logger.exception(f"Panel {panel_id} render() failed")
        raise HTTPException(status_code=500, detail=str(e))


__all__ = ["router"]
