"""Reporting — template marketplace (browse/suggest/publish/install/rate).

Submodule of the reporting router. Mounted at ``/api/v1/reporting/marketplace``.
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Body, HTTPException, Query

from app.modules.reporting.routes.common import _marketplace

router = APIRouter(prefix="/marketplace", tags=["Reporting — Marketplace"])


@router.get("", summary="Browse report marketplace")
def marketplace_list(
    category: str = Query(""),
    status: str = Query(""),
):
    return {"items": _marketplace().list(category=category, status=status)}


@router.post("/suggest", summary="Suggest a template to the marketplace")
def marketplace_suggest(payload: Dict[str, Any] = Body(...)):
    return _marketplace().suggest(
        title=payload.get("title", ""),
        description=payload.get("description", ""),
        category=payload.get("category", "general"),
        definition=payload.get("definition"),
        author=payload.get("author", "user"),
        dependencies=payload.get("dependencies"),
        capability_footprint=payload.get("capability_footprint"),
    )


@router.post("/{item_id}/publish", summary="Publish a marketplace item")
def marketplace_publish(item_id: str):
    return _marketplace().publish(item_id)


@router.post("/{item_id}/install", summary="Install a marketplace item as a template")
def marketplace_install(item_id: str):
    result = _marketplace().install(item_id)
    if not result.get("ok", True):
        raise HTTPException(status_code=400, detail=result)
    return result


@router.post("/{item_id}/rate", summary="Rate a marketplace item")
def marketplace_rate(item_id: str, payload: Dict[str, Any] = Body(...)):
    return _marketplace().rate(
        item_id, payload.get("rating", 5.0), payload.get("review", "")
    )
