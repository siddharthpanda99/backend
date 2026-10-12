"""Model-loader lifecycle routes — thin routers delegating to common_lib (RAG-P1-004).

``GET /model-loader/status``, ``GET /model-loader/jobs/{job_id}`` and
``GET /model-instances/{instance_id}`` stay visible while the flag is OFF;
``POST /models/{id}/inspect``, ``POST /models/{id}/load`` and
``DELETE /model-instances/{id}`` answer 404 while OFF (G9).
G1: no business logic here. G6: no tables.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Model Loader"])

_FLAG = "model_loader.lifecycle.enabled"


def _require_flag() -> None:
    try:
        from common_lib.modules.model_loader.lifecycle.flags import is_enabled
    except ImportError:
        raise HTTPException(status_code=404, detail="Model-loader lifecycle unavailable")
    if is_enabled(_FLAG):
        return
    raise HTTPException(
        status_code=404,
        detail=(
            "Model-loader lifecycle is gated behind the feature flag "
            f"'{_FLAG}', which is currently OFF. Enable "
            "MODEL_LOADER_LIFECYCLE_ENABLED=true and restart."
        ),
    )


def _service():
    from common_lib.modules.model_loader.lifecycle.service import (
        get_lifecycle_service,
    )

    return get_lifecycle_service()


def _guarded(fn, *args, **kwargs):
    _require_flag()
    try:
        return fn(*args, **kwargs)
    except Exception as exc:
        from common_lib.modules.model_loader.lifecycle.service import (
            FlagDisabledError,
            ScopeViolationError,
        )

        if isinstance(exc, FlagDisabledError):
            raise HTTPException(status_code=404, detail=str(exc))
        if isinstance(exc, ScopeViolationError):
            raise HTTPException(status_code=403, detail=str(exc))
        if isinstance(exc, KeyError):
            raise HTTPException(status_code=404, detail=str(exc))
        if isinstance(exc, ValueError):
            raise HTTPException(status_code=422, detail=str(exc))
        raise


@router.get("/model-loader/status")
async def loader_status() -> Dict[str, Any]:
    """Lifecycle-manager status, caches and policy (visible while OFF)."""
    return _service().status()


@router.get("/model-loader/schemas")
async def loader_schemas() -> Dict[str, Any]:
    """Publish JSON Schemas for lifecycle contracts (visible while OFF)."""
    return _service().publish_schemas()


class InspectBody(BaseModel):
    source_uri: Optional[str] = Field(default=None)
    pinned_revision: Optional[str] = Field(default=None)
    options: Dict[str, Any] = Field(default_factory=dict)
    scope: str = Field(default="tenant:default")


@router.post("/models/{model_id}/inspect")
async def inspect_model(model_id: str, body: InspectBody) -> Dict[str, Any]:
    """Inspect artifacts/metadata without loading weights (404 while OFF)."""
    return _guarded(
        _service().inspect_model,
        {"model_id": model_id, **body.model_dump()},
    )


class LoadBody(BaseModel):
    pinned_revision: str = Field(default="latest")
    checksum: str = Field(default="")
    backend: str = Field(default="transformers")
    backend_version: str = Field(default="unknown")
    precision: str = Field(default="fp16")
    placement: str = Field(default="cpu")
    options: Dict[str, Any] = Field(default_factory=dict)
    scope: str = Field(default="tenant:default")
    warm_pool: bool = Field(default=False)
    ttl_s: float = Field(default=0.0, ge=0.0)


@router.post("/models/{model_id}/load")
async def load_model(model_id: str, body: LoadBody) -> Dict[str, Any]:
    """Submit an asynchronous load job (404 while OFF; dedup-aware)."""
    return _guarded(
        _service().submit_load,
        {"model_id": model_id, **body.model_dump()},
    )


@router.get("/model-loader/jobs/{job_id}")
async def loader_job(job_id: str) -> Dict[str, Any]:
    """Load job progress and diagnostics (visible while OFF)."""
    found = _service().get_job(job_id)
    if found is None:
        raise HTTPException(status_code=404, detail=f"Unknown load job {job_id!r}")
    return found


@router.get("/model-instances/{instance_id}")
async def instance_status(
    instance_id: str,
    scope: Optional[str] = Query(default=None),
) -> Dict[str, Any]:
    """Lifecycle/runtime status of one instance (visible while OFF, scope-checked)."""
    try:
        found = _service().get_instance(instance_id, scope=scope)
    except Exception as exc:
        from common_lib.modules.model_loader.lifecycle.service import (
            ScopeViolationError,
        )

        if isinstance(exc, ScopeViolationError):
            raise HTTPException(status_code=403, detail=str(exc))
        raise
    if found is None:
        raise HTTPException(status_code=404, detail=f"Unknown instance {instance_id!r}")
    return found


@router.delete("/model-instances/{instance_id}")
async def unload_instance(
    instance_id: str,
    scope: Optional[str] = Query(default=None),
    force: bool = Query(default=False),
) -> Dict[str, Any]:
    """Drain and unload an instance (404 while OFF, scope-checked)."""
    return _guarded(
        _service().unload_instance, instance_id, scope=scope, force=force
    )
