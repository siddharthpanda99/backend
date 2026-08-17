"""Reporting — assets, brand kits, audit trail + generated-document archive.

Submodule of the reporting router. Mounted at ``/api/v1/reporting`` with the
``/assets``, ``/brand-kits``, ``/audit`` and ``/documents`` endpoints.
"""

from __future__ import annotations

import base64
from typing import Any, Dict

from fastapi import APIRouter, Body, HTTPException, Query

from app.modules.reporting.routes.common import _assets, _audit, _brand_kits, _docs

router = APIRouter(tags=["Reporting — Assets & Audit"])


# ---------------------------------------------------------------------------
# Assets
# ---------------------------------------------------------------------------


@router.post("/assets", summary="Upload an asset")
def upload_asset(payload: Dict[str, Any] = Body(...)):
    name = payload.get("name", "")
    content_b64 = payload.get("content_b64", "")
    if not name or not content_b64:
        raise HTTPException(
            status_code=400, detail="'name' and 'content_b64' are required"
        )
    asset = _assets().put(
        name,
        base64.b64decode(content_b64),
        asset_type=payload.get("asset_type", "image"),
        tags=payload.get("tags"),
        metadata=payload.get("metadata"),
    )
    return {
        "id": asset["id"],
        "asset": {k: asset[k] for k in ("id", "name", "asset_type", "version")},
    }


@router.get("/assets", summary="List assets")
def list_assets(
    asset_type: str = Query(""),
    tag: str = Query(""),
):
    return {"assets": _assets().list(asset_type=asset_type, tag=tag)}


@router.get("/assets/{asset_id}", summary="Get an asset")
def get_asset(asset_id: str):
    asset = _assets().get(asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail=f"Asset not found: {asset_id}")
    return asset


# ---------------------------------------------------------------------------
# Brand kits
# ---------------------------------------------------------------------------


@router.post("/brand-kits", summary="Create a Brand Kit")
def create_brand_kit(payload: Dict[str, Any] = Body(...)):
    name = payload.get("name", "")
    if not name:
        raise HTTPException(status_code=400, detail="'name' is required")
    kit = _brand_kits().create(
        name,
        theme_ref=payload.get("theme_ref", "default"),
        logos=payload.get("logos"),
        fonts=payload.get("fonts"),
        palette=payload.get("palette"),
        description=payload.get("description", ""),
    )
    return kit


@router.get("/brand-kits", summary="List Brand Kits")
def list_brand_kits():
    return {"kits": _brand_kits().list()}


@router.post("/brand-kits/{kit_id}/register-theme", summary="Register a kit's theme")
def register_kit_theme(kit_id: str):
    return _brand_kits().register_theme_from_kit(kit_id)


# ---------------------------------------------------------------------------
# Audit trail
# ---------------------------------------------------------------------------


@router.get("/audit", summary="Query the audit trail")
def query_audit(
    action: str = Query(""),
    entity_id: str = Query(""),
    actor: str = Query(""),
    limit: int = Query(200),
):
    return {
        "events": _audit().list(
            action=action, entity_id=entity_id, actor=actor, limit=limit
        )
    }


# ---------------------------------------------------------------------------
# Generated-document archive
# ---------------------------------------------------------------------------


@router.get("/documents", summary="List archived generated documents")
def list_documents(template_id: str = Query(""), limit: int = Query(100)):
    return {"documents": _docs().list(template_id=template_id, limit=limit)}


@router.get("/documents/{doc_id}/{fmt}", summary="Download an archived output")
def download_document(doc_id: str, fmt: str):
    content = _docs().get_output_bytes(doc_id, fmt)
    if content is None:
        raise HTTPException(status_code=404, detail=f"No {fmt} output for {doc_id}")
    return {"content": base64.b64encode(content).decode(), "encoding": "base64"}
