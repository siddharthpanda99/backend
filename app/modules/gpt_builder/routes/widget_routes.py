"""GPT Builder — Widget Routes.

Widget type listing and preview endpoints, registered under
/gpt-builder/widgets to match the spec's expected /api/v1/widgets pattern.
"""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.get("/", response_model=List[Dict[str, Any]])
async def list_widget_types():
    """List all available widget types with their metadata."""
    from common_lib.modules.gpt_builder.widget_dispatch import WIDGET_REGISTRY, WidgetCategory
    return [
        {
            "type": wtype,
            "category": meta["category"].value if isinstance(meta["category"], WidgetCategory) else str(meta["category"]),
            "description": meta["description"],
            "required_props": meta["required_props"],
            "optional_props": meta["optional_props"],
            "max_children": meta["max_children"],
        }
        for wtype, meta in WIDGET_REGISTRY.items()
    ]


@router.post("/preview", response_model=Dict[str, Any])
async def preview_widget(widget: Dict[str, Any]):
    """Preview a widget with sample data."""
    from common_lib.modules.gpt_builder.widget_dispatch import (
        validate_widget, _apply_defaults, WIDGET_REGISTRY
    )

    if not widget.get("type"):
        raise HTTPException(status_code=400, detail="Missing 'type' in widget")

    valid, errors = validate_widget(widget)
    if not valid:
        raise HTTPException(status_code=400, detail=f"Invalid widget: {'; '.join(errors)}")

    resolved = _apply_defaults(widget)
    preview_text = f"Preview of {resolved['type']}: {resolved.get('title', 'Untitled')}"

    return {
        "widget": resolved,
        "rendered_preview": preview_text,
    }
