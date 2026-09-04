"""Model Catalog — thin API router (ai_models).

All logic lives in ``common_lib.modules.ai_models.catalog``
(ModelCatalogService). This module only maps HTTP calls onto the
service and serialises the JSON payloads the ModelCatalogPage React UI
expects:

- ``GET  /api/v1/ai_models/list``        → full snapshot (models + keys)
- ``POST /api/v1/ai_models/refresh``     → live per-key provider probe
- ``POST /api/v1/ai_models/set-default`` → persist default model choice
- ``GET  /api/v1/ai_models/status``      → per-provider status view
- ``GET  /api/v1/ai_models/usage``       → compact per-provider usage overview
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger(__name__)

router = APIRouter()


def _catalog():
    """Lazy ModelCatalogService (no heavy work until first call)."""
    from common_lib.modules.ai_models.catalog import ModelCatalogService

    return ModelCatalogService()


@router.get("/list")
async def model_catalog_list() -> Dict[str, Any]:
    """Return the current model + key catalog snapshot."""
    try:
        return _catalog().snapshot()
    except Exception as exc:  # noqa: BLE001
        logger.error("model_catalog.list failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/refresh")
async def model_catalog_refresh(
    provider: Optional[str] = Query(None, description="Restrict to one provider"),
) -> Dict[str, Any]:
    """Best-effort: probe each configured provider's live /models list.

    Reuses the AI Gateway provider fetchers (via the integration port)
    keyed by the platform's API keys (DB-first, config.ini fallback).
    Populates the process cache so a subsequent ``GET /list`` returns
    ``source=\"api\"`` entries.
    """
    try:
        return _catalog().refresh_status(provider=provider)
    except Exception as exc:  # noqa: BLE001
        logger.error("model_catalog.refresh failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/usage")
async def model_catalog_usage() -> Dict[str, Any]:
    """Return a compact per-provider usage/limits overview.

    Merges the most recent live refresh (OpenRouter-style usage quotas,
    free-tier flags, model counts) with DB-backed key status. Lightweight
    enough for the chat UI to poll while choosing a model/provider.
    """
    try:
        return _catalog().usage_overview()
    except Exception as exc:  # noqa: BLE001
        logger.error("model_catalog.usage failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/pools")
async def model_pools_list() -> Dict[str, Any]:
    """List saved model pools (persistable model collections)."""
    try:
        return _catalog().list_pools()
    except Exception as exc:  # noqa: BLE001
        logger.error("model_pools.list failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/pools")
async def model_pools_create(body: Dict[str, Any]) -> Dict[str, Any]:
    """Create a model pool from live-catalog (provider, model) members."""
    try:
        name = body.get("name") or ""
        members = body.get("members") or []
        return _catalog().create_pool(
            name,
            members=members,
            description=body.get("description") or "",
            strategy=body.get("strategy") or "priority",
            enabled=bool(body.get("enabled", True)),
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("model_pools.create failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.put("/pools/{pool_id}")
async def model_pools_update(
    pool_id: str,
    body: Dict[str, Any],
) -> Dict[str, Any]:
    """Update a pool (name / members / strategy / enabled)."""
    try:
        return _catalog().update_pool(pool_id, body)
    except Exception as exc:  # noqa: BLE001
        logger.error("model_pools.update failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/pools/{pool_id}")
async def model_pools_delete(pool_id: str) -> Dict[str, Any]:
    """Delete a pool."""
    try:
        return _catalog().delete_pool(pool_id)
    except Exception as exc:  # noqa: BLE001
        logger.error("model_pools.delete failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/pools/{pool_id}/select")
async def model_pools_select(
    pool_id: str,
    body: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Rotate a pool → returns the chosen (provider, model) for this request.

    Selection considers live usage (remaining credits / free tier) and
    task complexity when the rotation flags are on, else plain priority.
    """
    try:
        body = body or {}
        return _catalog().select_pool(
            pool_id,
            complexity=str(body.get("complexity") or "medium"),
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("model_pools.select failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/set-default")
async def model_catalog_set_default(
    provider: str = Query(...),
    model_id: str = Query(..., alias="model_id"),
) -> Dict[str, Any]:
    """Persist the user's default model choice (provider + model id)."""
    try:
        return _catalog().set_default_model(provider, model_id)
    except Exception as exc:  # noqa: BLE001
        logger.error("model_catalog.set_default failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/status")
async def model_catalog_provider_status(
    provider: str = Query(..., description="Provider id, e.g. groq"),
) -> Dict[str, Any]:
    """Return the catalog view for a single provider."""
    try:
        return _catalog().provider_status(provider)
    except Exception as exc:  # noqa: BLE001
        logger.error("model_catalog.status failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))
