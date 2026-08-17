"""Reporting — plugin SDK surface (SSOT §19.1, Phases 41-43).

Submodule of the reporting router. Mounted at ``/api/v1/reporting/plugins`` —
register custom renderers/components/charts and list the manifest with
capability footprints (the trust/marketplace review surface, §18.2).
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Body

router = APIRouter(prefix="/plugins", tags=["Reporting — Plugins"])


def _sdk():
    from common_lib.modules.reporting.core.plugin_sdk import PluginSDK

    return PluginSDK.get()


@router.get("", summary="List registered reporting plugins (trust surface)")
def list_plugins(kind: str = ""):
    plugins = _sdk().list_plugins(kind=kind)
    return {"plugins": plugins, "count": len(plugins)}


@router.post("/component", summary="Register a custom report component (Phase 43)")
def register_component(payload: Dict[str, Any] = Body(...)):
    plugin_type = payload.get("plugin_type", "")
    if not plugin_type:
        return {"ok": False, "error": "'plugin_type' is required"}

    # Agentic/HTTP surface uses a generic text renderer; real custom renderers
    # are registered through the Python SDK (PluginSDK.get().register_component).
    def _renderer(block: Any, options: Dict[str, Any]) -> str:
        return f"[{plugin_type}: {getattr(block, 'content', '')}]"

    manifest = _sdk().register_component(
        plugin_type,
        {"html": _renderer, "md": _renderer, "txt": _renderer, "pdf": _renderer},
        name=payload.get("name", ""),
        description=payload.get("description", ""),
        data_footprint=payload.get("data_footprint", "none"),
        asset_access=payload.get("asset_access", "none"),
    )
    return {"ok": True, "manifest": manifest}


@router.post("/chart", summary="Register a custom chart type (Phase 43)")
def register_chart(payload: Dict[str, Any] = Body(...)):
    chart_type = payload.get("chart_type", "")
    if not chart_type:
        return {"ok": False, "error": "'chart_type' is required"}

    def _renderer(data: Any, config: Dict[str, Any]):
        from common_lib.modules.reporting.render.helpers import render_chart

        return render_chart("bar", data, title=config.get("title", ""))

    manifest = _sdk().register_chart(
        chart_type,
        _renderer,
        name=payload.get("name", ""),
        description=payload.get("description", ""),
        data_footprint=payload.get("data_footprint", "none"),
    )
    return {"ok": True, "manifest": manifest}
