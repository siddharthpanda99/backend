"""Reporting — markdown editing round-trip.

Submodule of the reporting router. Mounted at ``/api/v1/reporting/edit``.
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Body, HTTPException

from app.modules.reporting.routes.common import _editing

router = APIRouter(prefix="/edit", tags=["Reporting — Editing"])


@router.post("/render", summary="Parse edited markdown and re-render")
def edit_render(payload: Dict[str, Any] = Body(...)):
    markdown = payload.get("markdown", "")
    if not markdown:
        raise HTTPException(status_code=400, detail="'markdown' is required")
    formats = payload.get("formats", ["md"])
    return _editing().edit_and_render(markdown, formats, payload.get("options"))
