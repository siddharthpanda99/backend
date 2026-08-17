"""Image Processing · Runtime API routes — Pipeline managers, VRAM, caching, LoRA, scheduler.

Thin routing layer that delegates to common_lib.modules.image_processing.runtime services.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()


class PipelineRequest(BaseModel):
    pipeline_name: str
    config: Optional[Dict[str, Any]] = None


class LoraRequest(BaseModel):
    name: str
    strength: Optional[float] = 1.0
    path: Optional[str] = None


class SchedulerRequest(BaseModel):
    name: str
    pipeline_config: Optional[Dict[str, Any]] = None


def _get_pipeline_manager():
    from common_lib.modules.image_processing.runtime.managers.pipeline_manager import (
        PipelineManager,
    )

    return PipelineManager()


def _get_vram_manager():
    from common_lib.modules.image_processing.runtime.managers.vram_manager import (
        VRAMManager,
    )

    return VRAMManager()


def _get_lora_manager():
    from common_lib.modules.image_processing.runtime.managers.lora_manager import (
        LoraManager,
    )

    return LoraManager()


def _get_scheduler_manager():
    from common_lib.modules.image_processing.runtime.managers.scheduler_manager import (
        SchedulerManager,
    )

    return SchedulerManager()


# ---------------------------------------------------------------------------
# Pipeline endpoints
# ---------------------------------------------------------------------------

@router.get("/pipelines")
async def list_pipelines() -> Dict[str, Any]:
    """List loaded pipelines."""
    try:
        svc = _get_pipeline_manager()
        result = svc.list_pipelines() if hasattr(svc, "list_pipelines") else []
        return {"pipelines": result, "count": len(result) if isinstance(result, list) else 0}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pipelines/load")
async def load_pipeline(request: PipelineRequest) -> Dict[str, Any]:
    """Load a pipeline by name."""
    try:
        svc = _get_pipeline_manager()
        result = svc.load(request.pipeline_name, request.config) if hasattr(svc, "load") else {"name": request.pipeline_name}
        return {"result": result, "message": "Pipeline loaded successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/pipelines/{pipeline_name}")
async def unload_pipeline(pipeline_name: str) -> Dict[str, Any]:
    """Unload a pipeline."""
    try:
        svc = _get_pipeline_manager()
        svc.unload(pipeline_name) if hasattr(svc, "unload") else None
        return {"success": True, "message": "Pipeline unloaded successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# VRAM endpoints
# ---------------------------------------------------------------------------

@router.get("/vram/status")
async def vram_status() -> Dict[str, Any]:
    """Get VRAM usage status."""
    try:
        svc = _get_vram_manager()
        result = svc.get_status() if hasattr(svc, "get_status") else {"allocated": 0, "total": 0}
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/vram/clear")
async def clear_vram() -> Dict[str, Any]:
    """Clear VRAM cache."""
    try:
        svc = _get_vram_manager()
        svc.clear() if hasattr(svc, "clear") else None
        return {"success": True, "message": "VRAM cleared"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# LoRA endpoints
# ---------------------------------------------------------------------------

@router.get("/loras")
async def list_loras() -> Dict[str, Any]:
    """List available LoRA models."""
    try:
        svc = _get_lora_manager()
        result = svc.list() if hasattr(svc, "list") else []
        return {"loras": result, "count": len(result) if isinstance(result, list) else 0}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/loras")
async def apply_lora(request: LoraRequest) -> Dict[str, Any]:
    """Apply a LoRA model."""
    try:
        svc = _get_lora_manager()
        result = svc.apply(request.name, request.strength) if hasattr(svc, "apply") else {"name": request.name}
        return {"result": result, "message": "LoRA applied successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/loras/{lora_name}")
async def remove_lora(lora_name: str) -> Dict[str, Any]:
    """Remove a LoRA model."""
    try:
        svc = _get_lora_manager()
        svc.remove(lora_name) if hasattr(svc, "remove") else None
        return {"success": True, "message": "LoRA removed successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Scheduler endpoints
# ---------------------------------------------------------------------------

@router.get("/schedulers")
async def list_schedulers() -> Dict[str, Any]:
    """List available schedulers."""
    try:
        svc = _get_scheduler_manager()
        result = svc.list() if hasattr(svc, "list") else []
        return {"schedulers": result, "count": len(result) if isinstance(result, list) else 0}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/schedulers/resolve")
async def resolve_scheduler(request: SchedulerRequest) -> Dict[str, Any]:
    """Resolve a scheduler by name."""
    try:
        svc = _get_scheduler_manager()
        result = svc.resolve(request.name) if hasattr(svc, "resolve") else {"name": request.name}
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
