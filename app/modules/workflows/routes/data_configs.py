"""
Data Config CRUD API — Manage YAML data-config files.

Endpoints:
    GET    /api/v1/data-configs/              — List all configs (optional workflow_id filter)
    GET    /api/v1/data-configs/{id}          — Get a single config with full YAML content
    POST   /api/v1/data-configs/              — Create a new config
    PUT    /api/v1/data-configs/{id}          — Update a config (fields or full YAML content)
    DELETE /api/v1/data-configs/{id}          — Delete a config
    GET    /api/v1/data-configs/workflows     — List available workflow YAMLs
"""
import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_service():
    from common_lib.modules.workflows.data_config.service import DataConfigService
    return DataConfigService()


# ── Request Models ──────────────────────────────────────────────

class CreateConfigRequest(BaseModel):
    name: str
    workflow_id: str = ""
    description: str = ""
    data_config: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    category: str = ""
    directory: str = ""


class UpdateConfigFieldsRequest(BaseModel):
    name: Optional[str] = None
    workflow_id: Optional[str] = None
    description: Optional[str] = None
    data_config: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


class UpdateConfigContentRequest(BaseModel):
    content: str = Field(..., description="Full YAML content to overwrite the file")


# ── Endpoints ───────────────────────────────────────────────────

@router.get("/")
def list_configs(
    workflow_id: Optional[str] = None,
    category: Optional[str] = None,
):
    """List all data-config YAML files."""
    svc = _get_service()
    configs = svc.list_configs(workflow_id=workflow_id, category=category)
    return {"data": configs, "total": len(configs)}


@router.get("/workflows")
def list_workflows():
    """List available workflow YAMLs for linking."""
    svc = _get_service()
    workflows = svc.list_workflows()
    return {"data": workflows, "total": len(workflows)}


@router.get("/{config_id:path}")
def get_config(config_id: str):
    """Get a single config with full YAML content."""
    svc = _get_service()
    config = svc.get_config(config_id)
    if not config:
        raise HTTPException(status_code=404, detail=f"Config not found: {config_id}")
    return {"data": config}


@router.post("/")
def create_config(req: CreateConfigRequest):
    """Create a new data-config YAML file."""
    svc = _get_service()
    try:
        result = svc.create_config(
            name=req.name,
            workflow_id=req.workflow_id,
            description=req.description,
            data_config=req.data_config,
            metadata=req.metadata,
            category=req.category,
            directory=req.directory,
        )
        return {"data": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{config_id:path}")
def update_config(config_id: str, req: UpdateConfigFieldsRequest):
    """Update a config by fields."""
    svc = _get_service()
    try:
        result = svc.update_config(
            config_id=config_id,
            name=req.name,
            workflow_id=req.workflow_id,
            description=req.description,
            data_config=req.data_config,
            metadata=req.metadata,
        )
        if not result:
            raise HTTPException(status_code=404, detail=f"Config not found: {config_id}")
        return {"data": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{config_id:path}/content")
def update_config_content(config_id: str, req: UpdateConfigContentRequest):
    """Update a config by overwriting its full YAML content."""
    svc = _get_service()
    try:
        result = svc.update_config(config_id=config_id, content=req.content)
        if not result:
            raise HTTPException(status_code=404, detail=f"Config not found: {config_id}")
        return {"data": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{config_id:path}")
def delete_config(config_id: str):
    """Delete a data-config YAML file."""
    svc = _get_service()
    deleted = svc.delete_config(config_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Config not found: {config_id}")
    return {"data": {"id": config_id, "deleted": True}}
