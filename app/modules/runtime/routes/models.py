"""Runtime Models Lifecycle Router — POST /runtime/models/{id}/prepare|load|unload

Thin FastAPI router that delegates to common_lib.modules.runtime for
model lifecycle management.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Body, HTTPException, Path, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/models", tags=["Runtime — Models"])


# ──────────────────────────────────────────────────────────────────
# Service Accessor
# ──────────────────────────────────────────────────────────────────

def _get_runtime_service():
    """Lazy import of RuntimeService."""
    from common_lib.modules.runtime.service import get_runtime_service
    return get_runtime_service()


def _get_lifecycle_manager():
    """Get the lifecycle manager."""
    from common_lib.modules.runtime.lifecycle.manager import LifecycleManager, LifecycleManagerConfig
    return LifecycleManager(LifecycleManagerConfig())


# ──────────────────────────────────────────────────────────────────
# Request / Response Schemas
# ──────────────────────────────────────────────────────────────────

class PrepareRequest(BaseModel):
    """Request to prepare a model (download/verify)."""

    force_download: bool = Field(default=False, description="Force re-download if already present")
    verify_checksum: bool = Field(default=True, description="Verify checksum after download")


class LoadRequest(BaseModel):
    """Request to load a model into memory."""

    config: Optional[dict[str, Any]] = Field(default=None, description="Execution configuration")
    warmup: bool = Field(default=True, description="Run warmup after loading")
    device_id: Optional[str] = Field(default=None, description="Specific device to load on")
    device_pool: Optional[str] = Field(default=None, description="Device pool to use")


class UnloadRequest(BaseModel):
    """Request to unload a model."""

    force: bool = Field(default=False, description="Force unload even if executing")


class ModelLifecycleResponse(BaseModel):
    """Response for model lifecycle operations."""

    model_id: str
    status: str
    message: str
    details: Optional[dict[str, Any]] = None


# ──────────────────────────────────────────────────────────────────
# Route Handlers
# ──────────────────────────────────────────────────────────────────

@router.get("", summary="List All Models")
async def list_models(
    task: Optional[str] = Query(default=None, description="Filter by task"),
    provider: Optional[str] = Query(default=None, description="Filter by provider"),
    modality: Optional[str] = Query(default=None, description="Filter by modality"),
    local_only: bool = Query(default=False, description="Only local models"),
) -> dict[str, Any]:
    """List all registered models with optional filters."""
    try:
        service = _get_runtime_service()
        models = service.list_models(
            task=task,
            provider=provider,
            modality=modality,
            local_only=local_only,
        )

        result = []
        for model in models:
            if hasattr(model, 'to_dict'):
                result.append(model.to_dict())
            else:
                result.append(model.__dict__)

        return {"models": result, "count": len(result)}

    except Exception as exc:
        logger.error("list_models failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/{model_id}", summary="Get Model Details")
async def get_model(model_id: str = Path(..., description="Model identifier")) -> dict[str, Any]:
    """Get detailed information about a model."""
    try:
        service = _get_runtime_service()
        model = service.get_model(model_id)

        if hasattr(model, 'to_dict'):
            return model.to_dict()
        return model.__dict__

    except Exception as exc:
        logger.error("get_model failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=404 if "not found" in str(exc).lower() else 500, detail=str(exc))


@router.post("/{model_id}/prepare", response_model=ModelLifecycleResponse, summary="Prepare Model")
async def prepare_model(
    model_id: str = Path(..., description="Model identifier"),
    request: PrepareRequest = Body(default=PrepareRequest()),
) -> ModelLifecycleResponse:
    """Prepare a model for execution (download, verify, make ready).

    Transitions: DISCOVERED → VALIDATED → DOWNLOADING → PREPARING → READY
    """
    try:
        service = _get_runtime_service()
        lifecycle = _get_lifecycle_manager()

        # Get or register model
        try:
            model = service.get_model(model_id)
        except Exception as e:
            raise HTTPException(status_code=404, detail=f"Model not found: {model_id}") from e

        # Register with lifecycle manager if not already
        lifecycle.register_model(model)

        # Validate
        validated = lifecycle.validate_model(model_id)
        if not validated:
            lifecycle_state = lifecycle.get_lifecycle(model_id)
            error = lifecycle_state.last_error if lifecycle_state else "Validation failed"
            return ModelLifecycleResponse(
                model_id=model_id,
                status="failed",
                message=f"Validation failed: {error}",
                details={"stage": "validate"},
            )

        # Download if not local
        if not model.is_local or request.force_download:
            from common_lib.modules.runtime.lifecycle.manager import ModelState
            current_state = lifecycle.get_model_state(model_id)
            if current_state in ["validated", "discovered"]:
                downloaded = lifecycle.download_model(model_id)
                if not downloaded:
                    lifecycle_state = lifecycle.get_lifecycle(model_id)
                    error = lifecycle_state.last_error if lifecycle_state else "Download failed"
                    return ModelLifecycleResponse(
                        model_id=model_id,
                        status="failed",
                        message=f"Download failed: {error}",
                        details={"stage": "download"},
                    )

        return ModelLifecycleResponse(
            model_id=model_id,
            status="ready",
            message="Model prepared successfully",
            details={
                "model_id": model_id,
                "is_local": model.is_local,
                "status": model.status.value,
            },
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("prepare_model failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/{model_id}/load", response_model=ModelLifecycleResponse, summary="Load Model")
async def load_model(
    model_id: str = Path(..., description="Model identifier"),
    request: LoadRequest = Body(default=LoadRequest()),
) -> ModelLifecycleResponse:
    """Load a model into memory for execution.

    Transitions: READY → LOADING → LOADED → WARMING → WARM
    """
    try:
        service = _get_runtime_service()
        lifecycle = _get_lifecycle_manager()

        # Get or register model
        try:
            model = service.get_model(model_id)
        except Exception as e:
            raise HTTPException(status_code=404, detail=f"Model not found: {model_id}") from e

        # Register with lifecycle manager if not already
        lifecycle.register_model(model)

        # Build load request
        from common_lib.modules.runtime.lifecycle.manager import ModelLoadRequest as LifeCycleLoadRequest
        load_request = LifeCycleLoadRequest(
            model_id=model_id,
            model=model,
            config=request.config,
            warmup=request.warmup,
            device_id=request.device_id,
        )

        # Load the model
        result = lifecycle.load_model(load_request)

        if result.status == "loaded":
            return ModelLifecycleResponse(
                model_id=model_id,
                status="loaded",
                message="Model loaded successfully",
                details={
                    "instance_id": result.instance_id,
                    "device_id": result.device_id,
                    "backend_id": result.backend_id,
                    "runtime_id": result.runtime_id,
                    "load_time_seconds": result.load_time_seconds,
                    "memory_used_gb": result.memory_used_gb,
                },
            )
        else:
            return ModelLifecycleResponse(
                model_id=model_id,
                status="failed",
                message=f"Load failed: {result.error}",
                details={
                    "error": result.error,
                    "warnings": result.warnings,
                },
            )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("load_model failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/{model_id}/unload", response_model=ModelLifecycleResponse, summary="Unload Model")
async def unload_model(
    model_id: str = Path(..., description="Model identifier"),
    request: UnloadRequest = Body(default=UnloadRequest()),
) -> ModelLifecycleResponse:
    """Unload a model from memory.

    Transitions: WARM/IDLE/LOADED → EVICTING → UNLOADED
    """
    try:
        lifecycle = _get_lifecycle_manager()

        success = lifecycle.unload_model(model_id, force=request.force)

        if success:
            return ModelLifecycleResponse(
                model_id=model_id,
                status="unloaded",
                message="Model unloaded successfully",
            )
        else:
            lifecycle_state = lifecycle.get_lifecycle(model_id)
            current_state = lifecycle.get_model_state(model_id)
            error = lifecycle_state.last_error if lifecycle_state else "Unload failed"
            return ModelLifecycleResponse(
                model_id=model_id,
                status="failed",
                message=f"Unload failed: {error}",
                details={"current_state": current_state},
            )

    except Exception as exc:
        logger.error("unload_model failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/{model_id}/state", summary="Get Model Lifecycle State")
async def get_model_state(model_id: str = Path(..., description="Model identifier")) -> dict[str, Any]:
    """Get the current lifecycle state of a model."""
    try:
        lifecycle = _get_lifecycle_manager()

        state = lifecycle.get_model_state(model_id)
        lifecycle_obj = lifecycle.get_lifecycle(model_id)

        result = {
            "model_id": model_id,
            "state": state,
        }

        if lifecycle_obj:
            result["details"] = lifecycle_obj.to_dict()

        return result

    except Exception as exc:
        logger.error("get_model_state failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/{model_id}/idle", response_model=ModelLifecycleResponse, summary="Idle Model")
async def idle_model(model_id: str = Path(..., description="Model identifier")) -> ModelLifecycleResponse:
    """Move a model to IDLE state (WARM/LOADED → IDLE)."""
    try:
        lifecycle = _get_lifecycle_manager()

        success = lifecycle.idle_model(model_id)

        if success:
            return ModelLifecycleResponse(
                model_id=model_id,
                status="idle",
                message="Model moved to IDLE state",
            )
        else:
            return ModelLifecycleResponse(
                model_id=model_id,
                status="failed",
                message="Model not in WARM or LOADED state",
            )

    except Exception as exc:
        logger.error("idle_model failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/seed", response_model=ModelLifecycleResponse, summary="Seed Default Models")
async def seed_default_models() -> ModelLifecycleResponse:
    """Seed default models from YAML registries."""
    try:
        service = _get_runtime_service()
        service.seed_default_models()

        return ModelLifecycleResponse(
            model_id="all",
            status="seeded",
            message="Default models seeded successfully",
        )

    except Exception as exc:
        logger.error("seed_default_models failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/verify", response_model=ModelLifecycleResponse, summary="Verify All Models")
async def verify_all_models() -> ModelLifecycleResponse:
    """Verify all registered models and update their local status."""
    try:
        service = _get_runtime_service()
        models = service.verify_all_models()

        return ModelLifecycleResponse(
            model_id="all",
            status="verified",
            message=f"Verified {len(models)} models",
            details={"models": [m.to_dict() for m in models]},
        )

    except Exception as exc:
        logger.error("verify_all_models failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))