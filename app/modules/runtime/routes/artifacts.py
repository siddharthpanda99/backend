"""Runtime Artifacts Router — GET /runtime/artifacts

Thin FastAPI router that delegates to common_lib.modules.runtime for
artifact registry queries.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/artifacts", tags=["Runtime — Artifacts"])


# ──────────────────────────────────────────────────────────────────
# Service Accessor
# ──────────────────────────────────────────────────────────────────

def _get_runtime_service():
    """Lazy import of RuntimeService."""
    from common_lib.modules.runtime.service import get_runtime_service
    return get_runtime_service()


# ──────────────────────────────────────────────────────────────────
# Route Handlers
# ──────────────────────────────────────────────────────────────────

@router.get("", summary="List Available Artifacts")
async def list_artifacts(
    model_id: Optional[str] = Query(default=None, description="Filter by model ID"),
    adapter_name: Optional[str] = Query(default=None, description="Filter by adapter name"),
) -> dict[str, Any]:
    """List all available artifacts, optionally filtered by model."""
    try:
        service = _get_runtime_service()
        artifacts = service.list_artifacts(model_id=model_id, adapter_name=adapter_name)

        result = []
        for artifact in artifacts:
            if hasattr(artifact, 'to_dict'):
                result.append(artifact.to_dict())
            else:
                result.append(artifact.__dict__)

        return {
            "artifacts": result,
            "count": len(result),
            "filter": {
                "model_id": model_id,
                "adapter_name": adapter_name,
            },
        }

    except Exception as exc:
        logger.error("list_artifacts failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/adapters", summary="List Artifact Adapters")
async def list_artifact_adapters() -> dict[str, Any]:
    """List all registered artifact storage adapters."""
    try:
        from common_lib.modules.runtime.registry import get_artifact_registry
        artifact_registry = get_artifact_registry()

        adapters = artifact_registry.list_adapters() if hasattr(artifact_registry, 'list_adapters') else []

        return {"adapters": adapters, "count": len(adapters)}

    except Exception as exc:
        logger.error("list_artifact_adapters failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/{artifact_id}", summary="Get Artifact Details")
async def get_artifact(
    artifact_id: str,
    adapter_name: Optional[str] = Query(default=None, description="Adapter to use"),
) -> dict[str, Any]:
    """Get detailed information about a specific artifact."""
    try:
        service = _get_runtime_service()
        artifact = service.get_artifact(artifact_id, adapter_name=adapter_name)

        if not artifact:
            raise HTTPException(status_code=404, detail=f"Artifact not found: {artifact_id}")

        if hasattr(artifact, 'to_dict'):
            return artifact.to_dict()
        return artifact.__dict__

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("get_artifact failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=404 if "not found" in str(exc).lower() else 500, detail=str(exc))


@router.get("/{artifact_id}/path", summary="Get Artifact Local Path")
async def get_artifact_path(
    artifact_id: str,
    adapter_name: Optional[str] = Query(default=None, description="Adapter to use"),
) -> dict[str, Any]:
    """Get the local filesystem path for an artifact."""
    try:
        service = _get_runtime_service()
        path = service.get_artifact_path(artifact_id, adapter_name=adapter_name)

        return {
            "artifact_id": artifact_id,
            "path": path,
            "adapter": adapter_name,
        }

    except Exception as exc:
        logger.error("get_artifact_path failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=404 if "not found" in str(exc).lower() else 500, detail=str(exc))


@router.get("/model/{model_id}", summary="Get Model Artifacts")
async def get_model_artifacts(
    model_id: str,
    adapter_name: Optional[str] = Query(default=None, description="Adapter to use"),
) -> dict[str, Any]:
    """Get all artifacts for a specific model."""
    try:
        service = _get_runtime_service()
        artifacts = service.list_artifacts(model_id=model_id, adapter_name=adapter_name)

        result = []
        for artifact in artifacts:
            if hasattr(artifact, 'to_dict'):
                result.append(artifact.to_dict())
            else:
                result.append(artifact.__dict__)

        return {
            "model_id": model_id,
            "artifacts": result,
            "count": len(result),
        }

    except Exception as exc:
        logger.error("get_model_artifacts failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))