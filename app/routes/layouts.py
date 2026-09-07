"""Main backend — Layout Preset REST API.

Endpoints:
  GET  /api/v1/layouts                  list all (built-in + custom)
  GET  /api/v1/layouts/{id}            get one
  POST /api/v1/layouts                  create custom
  PUT  /api/v1/layouts/{id}            update custom
  DELETE /api/v1/layouts/{id}          delete custom (built-ins protected)
  POST /api/v1/layouts/{id}/apply      apply (returns the preset; UI/CLI
                                       use it to render their surface)
  POST /api/v1/layouts/render-cli      render a preset as a CLI string
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from common_lib.modules.layout import (
    BUILTIN_PRESETS,
    LayoutPreset,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/layouts", tags=["layouts"])


# ── In-memory user layout registry ─────────────────────────────
# In production this would be a DB-backed per-user table. For now
# it's a process-level dict keyed by user_id. (TODO: persist to
# data_storage.)
_USER_LAYOUTS: dict[str, dict[str, LayoutPreset]] = {}


def _get_user_layouts(user_id: str) -> dict[str, LayoutPreset]:
    if user_id not in _USER_LAYOUTS:
        _USER_LAYOUTS[user_id] = {}
    return _USER_LAYOUTS[user_id]


# ── Request/response models ────────────────────────────────────


class CreateLayoutRequest(BaseModel):
    id: str | None = Field(None, description="Optional id; auto-generated if missing")
    name: str
    description: str = ""
    category: str = "general"
    icon: str | None = None
    tabs: list[dict[str, Any]] = Field(default_factory=list)
    dock_tree: dict[str, Any] | None = None
    theme: dict[str, Any] = Field(default_factory=dict)


class UpdateLayoutRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    category: str | None = None
    icon: str | None = None
    tabs: list[dict[str, Any]] | None = None
    dock_tree: dict[str, Any] | None = None
    theme: dict[str, Any] | None = None


class RenderCliRequest(BaseModel):
    layout_id: str
    width: int | None = None
    height: int | None = None


# ── Helper ─────────────────────────────────────────────────────


def _current_user_id() -> str:
    """Stub: in production this reads the JWT. For now, return a
    constant so dev/test work without auth."""
    return "default-user"


def _is_builtin(preset_id: str) -> bool:
    return any(p.id == preset_id for p in BUILTIN_PRESETS)


def _all_visible(user_id: str) -> list[LayoutPreset]:
    """Built-ins + user's custom layouts."""
    out = list(BUILTIN_PRESETS)
    out.extend(_get_user_layouts(user_id).values())
    return out


# ── Endpoints ──────────────────────────────────────────────────


@router.get("")
async def list_layouts(category: str | None = None) -> dict[str, Any]:
    """List all visible layout presets (built-in + custom)."""
    user_id = _current_user_id()
    presets = _all_visible(user_id)
    if category:
        presets = [p for p in presets if p.category == category]
    return {
        "presets": [p.model_dump() for p in presets],
        "categories": sorted({p.category for p in _all_visible(user_id)}),
    }


@router.get("/{layout_id}")
async def get_layout(layout_id: str) -> dict[str, Any]:
    user_id = _current_user_id()
    # Built-ins first
    for p in BUILTIN_PRESETS:
        if p.id == layout_id:
            return p.model_dump()
    # Then user
    user_layouts = _get_user_layouts(user_id)
    if layout_id in user_layouts:
        return user_layouts[layout_id].model_dump()
    raise HTTPException(status_code=404, detail=f"layout '{layout_id}' not found")


@router.post("")
async def create_layout(body: CreateLayoutRequest) -> dict[str, Any]:
    user_id = _current_user_id()
    new_id = body.id or f"layout-{uuid.uuid4().hex[:8]}"
    if _is_builtin(new_id):
        raise HTTPException(
            status_code=409,
            detail=f"'{new_id}' is a built-in layout id; pick another",
        )
    user_layouts = _get_user_layouts(user_id)
    if new_id in user_layouts:
        raise HTTPException(status_code=409, detail=f"layout '{new_id}' already exists")
    preset = LayoutPreset(
        id=new_id,
        name=body.name,
        description=body.description,
        category=body.category,
        icon=body.icon,
        tabs=body.tabs,
        dock_tree=body.dock_tree,
        theme=body.theme,
        is_built_in=False,
        created_at=datetime.utcnow().isoformat(),
        updated_at=datetime.utcnow().isoformat(),
        author=user_id,
    )
    user_layouts[new_id] = preset
    return preset.model_dump()


@router.put("/{layout_id}")
async def update_layout(layout_id: str, body: UpdateLayoutRequest) -> dict[str, Any]:
    if _is_builtin(layout_id):
        raise HTTPException(
            status_code=403,
            detail=f"'{layout_id}' is a built-in layout; cannot edit. Clone it first.",
        )
    user_id = _current_user_id()
    user_layouts = _get_user_layouts(user_id)
    if layout_id not in user_layouts:
        raise HTTPException(status_code=404, detail=f"layout '{layout_id}' not found")
    existing = user_layouts[layout_id]
    data = existing.model_dump()
    for k, v in body.model_dump(exclude_unset=True).items():
        if v is not None:
            data[k] = v
    data["updated_at"] = datetime.utcnow().isoformat()
    user_layouts[layout_id] = LayoutPreset(**data)
    return user_layouts[layout_id].model_dump()


@router.delete("/{layout_id}")
async def delete_layout(layout_id: str) -> dict[str, Any]:
    if _is_builtin(layout_id):
        raise HTTPException(
            status_code=403, detail=f"'{layout_id}' is a built-in; cannot delete"
        )
    user_id = _current_user_id()
    user_layouts = _get_user_layouts(user_id)
    if layout_id not in user_layouts:
        raise HTTPException(status_code=404, detail=f"layout '{layout_id}' not found")
    del user_layouts[layout_id]
    return {"ok": True, "layout_id": layout_id}


@router.post("/{layout_id}/apply")
async def apply_layout(layout_id: str) -> dict[str, Any]:
    """Apply a layout preset. Returns the preset for the caller to use.

    The actual rendering happens on the caller side (the chat UI
    uses DockLayout; the CLI uses the rich renderer). This endpoint
    just returns the preset data the caller needs.
    """
    return await get_layout(layout_id)


@router.post("/render-cli")
async def render_cli(body: RenderCliRequest) -> dict[str, Any]:
    """Render a preset as a Rich CLI string. Used by the CLI tool.

    The CLI calls this endpoint with the layout id, gets back a
    rendered string, and prints it. This is what proves UI and CLI
    share the same layout data.
    """
    from common_lib.modules.layout.cli_renderer import render_layout_preset

    user_id = _current_user_id()
    preset: LayoutPreset | None = None
    for p in BUILTIN_PRESETS:
        if p.id == body.layout_id:
            preset = p
            break
    if preset is None:
        user_layouts = _get_user_layouts(user_id)
        preset = user_layouts.get(body.layout_id)
    if preset is None:
        raise HTTPException(
            status_code=404, detail=f"layout '{body.layout_id}' not found"
        )

    rendered = render_layout_preset(preset, width=body.width, height=body.height)
    return {
        "layout_id": preset.id,
        "name": preset.name,
        "rendered": rendered,
    }


__all__ = ["router"]
