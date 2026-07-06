"""
Extraction routes — processor and template config CRUD endpoints.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional, List

from common_lib.modules.dip.extraction.config_store import (
    get_processor_config,
    get_all_processor_configs,
    save_processor_config,
    delete_processor_config,
    get_template_config,
    get_all_template_configs,
    save_template_config,
    delete_template_config,
    list_all_configs,
)

router = APIRouter(prefix="/dip/extraction", tags=["dip/extraction"])


# ── Processor Config ───────────────────────────────────────────

class ProcessorConfigRequest(BaseModel):
    settings: Dict[str, Any]


@router.get("/processors")
async def list_processor_configs():
    """List all stored processor configs."""
    configs = get_all_processor_configs()
    return {"data": list(configs.values()), "count": len(configs)}


@router.get("/processors/{processor_id}/config")
async def get_proc_config(processor_id: str):
    """Get config for a specific processor."""
    config = get_processor_config(processor_id)
    if config is None:
        return {"data": None, "message": "No saved config — using defaults"}
    return {"data": config}


@router.post("/processors/{processor_id}/config")
async def save_proc_config(processor_id: str, payload: ProcessorConfigRequest):
    """Save processor settings."""
    result = save_processor_config(processor_id, payload.settings)
    return {"success": True, "data": result}


@router.delete("/processors/{processor_id}/config")
async def delete_proc_config(processor_id: str):
    """Delete processor config (revert to defaults)."""
    deleted = delete_processor_config(processor_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="No saved config found")
    return {"success": True}


# ── Template Config ────────────────────────────────────────────

class TemplateConfigRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    version: Optional[str] = None
    processor: Optional[str] = None
    outputFormat: Optional[str] = None
    includeMetadata: Optional[bool] = None
    validationEnabled: Optional[bool] = None
    fields: Optional[List[Dict[str, Any]]] = None


@router.get("/templates")
async def list_template_configs():
    """List all stored template configs."""
    configs = get_all_template_configs()
    return {"data": list(configs.values()), "count": len(configs)}


@router.get("/templates/{template_id}")
async def get_tmpl_config(template_id: str):
    """Get config for a specific template."""
    config = get_template_config(template_id)
    if config is None:
        return {"data": None, "message": "No saved config — using defaults"}
    return {"data": config}


@router.post("/templates/{template_id}")
async def save_tmpl_config(template_id: str, payload: TemplateConfigRequest):
    """Save template config."""
    config_data = payload.model_dump(exclude_none=True)
    result = save_template_config(template_id, config_data)
    return {"success": True, "data": result}


@router.delete("/templates/{template_id}")
async def delete_tmpl_config(template_id: str):
    """Delete template config (revert to defaults)."""
    deleted = delete_template_config(template_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="No saved config found")
    return {"success": True}


# ── Overview ───────────────────────────────────────────────────

@router.get("/configs")
async def get_all_extraction_configs():
    """Get summary of all stored extraction configs."""
    return {"data": list_all_configs()}


# ── Metrics (stub) ────────────────────────────────────────────

@router.get("/metrics")
async def get_extraction_metrics():
    """Get extraction pipeline metrics."""
    return {
        "data": {
            "total_processed": 0,
            "avg_latency_ms": 0,
            "error_rate": 0,
            "uptime_hours": 0,
        }
    }


# ── Jobs (stub) ───────────────────────────────────────────────

@router.get("/jobs")
async def get_extraction_jobs():
    """Get recent extraction pipeline jobs."""
    return {"data": []}
