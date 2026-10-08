"""Runtime Runtimes Router — GET /runtime/runtimes

Thin FastAPI router that delegates to common_lib.modules.runtime for
registered runtime queries.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/runtimes", tags=["Runtime — Runtimes"])


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

@router.get("", summary="List Registered Runtimes")
async def list_runtimes(
    enabled_only: bool = Query(default=True, description="Only enabled runtimes"),
) -> dict[str, Any]:
    """List all registered execution runtimes."""
    try:
        service = _get_runtime_service()
        runtimes = service.list_runtimes(enabled_only=enabled_only)

        result = []
        for rt in runtimes:
            info = {
                "name": rt.name if hasattr(rt, 'name') else str(rt),
                "version": rt.version if hasattr(rt, 'version') else "unknown",
                "enabled": True,
                "supported_devices": rt.supported_devices if hasattr(rt, 'supported_devices') else [],
                "supported_formats": rt.supported_formats if hasattr(rt, 'supported_formats') else [],
                "supported_quantization": rt.supported_quantization if hasattr(rt, 'supported_quantization') else [],
            }
            result.append(info)

        return {"runtimes": result, "count": len(result)}

    except Exception as exc:
        logger.error("list_runtimes failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/{runtime_name}", summary="Get Runtime Details")
async def get_runtime(runtime_name: str) -> dict[str, Any]:
    """Get detailed information about a specific runtime."""
    try:
        service = _get_runtime_service()
        runtime = service.get_runtime(runtime_name)

        if not runtime:
            raise HTTPException(status_code=404, detail=f"Runtime not found: {runtime_name}")

        return {
            "name": runtime.name if hasattr(runtime, 'name') else str(runtime),
            "version": runtime.version if hasattr(runtime, 'version') else "unknown",
            "supported_devices": runtime.supported_devices if hasattr(runtime, 'supported_devices') else [],
            "supported_formats": runtime.supported_formats if hasattr(runtime, 'supported_formats') else [],
            "supported_quantization": runtime.supported_quantization if hasattr(runtime, 'supported_quantization') else [],
            "methods": {
                "can_load_model": hasattr(runtime, 'can_load_model'),
                "estimate_memory": hasattr(runtime, 'estimate_memory'),
                "estimate_latency": hasattr(runtime, 'estimate_latency'),
                "load_model": hasattr(runtime, 'load_model'),
                "load_model_async": hasattr(runtime, 'load_model_async'),
                "unload_model": hasattr(runtime, 'unload_model'),
                "unload_model_async": hasattr(runtime, 'unload_model_async'),
                "infer": hasattr(runtime, 'infer'),
                "infer_async": hasattr(runtime, 'infer_async'),
                "stream_infer": hasattr(runtime, 'stream_infer'),
                "execute_plan": hasattr(runtime, 'execute_plan'),
                "execute_plan_async": hasattr(runtime, 'execute_plan_async'),
                "validate_plan": hasattr(runtime, 'validate_plan'),
                "get_default_config": hasattr(runtime, 'get_default_config'),
                "optimize_config": hasattr(runtime, 'optimize_config'),
            },
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("get_runtime failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/{runtime_name}/capabilities", summary="Get Runtime Capabilities")
async def get_runtime_capabilities(runtime_name: str) -> dict[str, Any]:
    """Get detailed capabilities of a runtime."""
    try:
        service = _get_runtime_service()
        runtime = service.get_runtime(runtime_name)

        if not runtime:
            raise HTTPException(status_code=404, detail=f"Runtime not found: {runtime_name}")

        return {
            "runtime": runtime_name,
            "version": runtime.version if hasattr(runtime, 'version') else "unknown",
            "supported_devices": runtime.supported_devices if hasattr(runtime, 'supported_devices') else [],
            "supported_formats": runtime.supported_formats if hasattr(runtime, 'supported_formats') else [],
            "supported_quantization": runtime.supported_quantization if hasattr(runtime, 'supported_quantization') else [],
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("get_runtime_capabilities failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))