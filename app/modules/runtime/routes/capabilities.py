"""Runtime Capabilities Router — GET /runtime/capabilities

Thin FastAPI router that delegates to common_lib.modules.runtime for
hardware and runtime capability queries.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/capabilities", tags=["Runtime — Capabilities"])


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

@router.get("", summary="Get Hardware + Runtime Capabilities")
async def get_capabilities(
    force_refresh: bool = Query(default=False, description="Force hardware re-discovery"),
) -> dict[str, Any]:
    """Get combined hardware and runtime capabilities.

    Returns:
    - Hardware profile (CPU, GPU, accelerators)
    - Registered runtimes with their capabilities
    - Registered backends
    - Available device pools
    - Total/free VRAM and RAM
    """
    try:
        service = _get_runtime_service()

        # Discover hardware
        hardware = service.discover_hardware(force_refresh=force_refresh)
        hardware_summary = service.get_hardware_summary()

        # Get registered runtimes
        runtimes = service.list_runtimes()
        runtimes_info = []
        for rt in runtimes:
            runtimes_info.append({
                "name": rt.name if hasattr(rt, 'name') else str(rt),
                "version": rt.version if hasattr(rt, 'version') else "unknown",
                "supported_devices": rt.supported_devices if hasattr(rt, 'supported_devices') else [],
                "supported_formats": rt.supported_formats if hasattr(rt, 'supported_formats') else [],
                "supported_quantization": rt.supported_quantization if hasattr(rt, 'supported_quantization') else [],
            })

        # Get registered backends
        backends = service.list_backends()
        backends_info = []
        for be in backends:
            backends_info.append({
                "name": be.name if hasattr(be, 'name') else str(be),
                "version": be.version if hasattr(be, 'version') else "unknown",
                "capabilities": be.capabilities if hasattr(be, 'capabilities') else {},
            })

        # Get artifact adapters
        from common_lib.modules.runtime.registry import get_artifact_registry
        artifact_registry = get_artifact_registry()
        adapters = artifact_registry.list_adapters() if hasattr(artifact_registry, 'list_adapters') else []

        return {
            "hardware": hardware_summary,
            "hardware_detail": hardware.to_dict() if hasattr(hardware, 'to_dict') else {},
            "runtimes": runtimes_info,
            "backends": backends_info,
            "artifact_adapters": adapters,
            "total_vram_gb": service.get_total_vram_gb(),
            "free_vram_gb": service.get_free_vram_gb(),
            "device_count": len(hardware.devices) if hasattr(hardware, 'devices') else 0,
        }

    except Exception as exc:
        logger.error("get_capabilities failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/hardware", summary="Get Hardware Capabilities")
async def get_hardware_capabilities(
    force_refresh: bool = Query(default=False, description="Force hardware re-discovery"),
) -> dict[str, Any]:
    """Get detailed hardware capabilities."""
    try:
        service = _get_runtime_service()
        hardware = service.discover_hardware(force_refresh=force_refresh)

        return {
            "summary": service.get_hardware_summary(),
            "detail": hardware.to_dict() if hasattr(hardware, 'to_dict') else {},
        }

    except Exception as exc:
        logger.error("get_hardware_capabilities failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/runtimes", summary="Get Registered Runtime Capabilities")
async def get_runtime_capabilities() -> dict[str, Any]:
    """Get capabilities of all registered runtimes."""
    try:
        service = _get_runtime_service()
        runtimes = service.list_runtimes()

        result = []
        for rt in runtimes:
            result.append({
                "name": rt.name if hasattr(rt, 'name') else str(rt),
                "version": rt.version if hasattr(rt, 'version') else "unknown",
                "supported_devices": rt.supported_devices if hasattr(rt, 'supported_devices') else [],
                "supported_formats": rt.supported_formats if hasattr(rt, 'supported_formats') else [],
                "supported_quantization": rt.supported_quantization if hasattr(rt, 'supported_quantization') else [],
                "can_load_model": hasattr(rt, 'can_load_model'),
                "estimate_memory": hasattr(rt, 'estimate_memory'),
                "estimate_latency": hasattr(rt, 'estimate_latency'),
            })

        return {"runtimes": result, "count": len(result)}

    except Exception as exc:
        logger.error("get_runtime_capabilities failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/backends", summary="Get Registered Backend Capabilities")
async def get_backend_capabilities() -> dict[str, Any]:
    """Get capabilities of all registered inference backends."""
    try:
        service = _get_runtime_service()
        backends = service.list_backends()

        result = []
        for be in backends:
            result.append({
                "name": be.name if hasattr(be, 'name') else str(be),
                "version": be.version if hasattr(be, 'version') else "unknown",
                "capabilities": be.capabilities if hasattr(be, 'capabilities') else {},
            })

        return {"backends": result, "count": len(result)}

    except Exception as exc:
        logger.error("get_backend_capabilities failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/models/{model_id}", summary="Get Model Capabilities")
async def get_model_capabilities(
    model_id: str,
) -> dict[str, Any]:
    """Get capabilities for a specific model."""
    try:
        service = _get_runtime_service()
        model = service.get_model(model_id)

        # Get runtime that can load this model
        runtimes = service.list_runtimes()
        compatible_runtimes = []
        for rt in runtimes:
            if hasattr(rt, 'can_load_model'):
                from common_lib.modules.runtime.core.plan import ExecutionConfig
                config = ExecutionConfig()
                if rt.can_load_model(model, config):
                    compatible_runtimes.append(rt.name if hasattr(rt, 'name') else str(rt))

        return {
            "model_id": model.id,
            "name": model.name,
            "provider": model.provider,
            "modalities": [m.value for m in model.modalities.modalities],
            "tasks": [t.value for t in model.modalities.tasks],
            "capabilities": [c.value for c in model.modalities.capabilities],
            "parameters": model.parameters,
            "quantization": model.quantization,
            "min_vram_gb": model.min_vram_gb,
            "recommended_vram_gb": model.recommended_vram_gb,
            "max_model_len": model.max_model_len,
            "context_window": model.context_window,
            "is_local": model.is_local,
            "status": model.status.value,
            "compatible_runtimes": compatible_runtimes,
        }

    except Exception as exc:
        logger.error("get_model_capabilities failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=404 if "not found" in str(exc).lower() else 500, detail=str(exc))