"""Integration Config API Routes — Module config, pipelines, interoperability.

Provides REST endpoints for the Integration Configuration Hub UI:
- /api/v1/integration/config/modules - List/toggle module configs
- /api/v1/integration/config/modules/{module_id} - Get/update module
- /api/v1/integration/config/pipelines - CRUD for pipeline configs
- /api/v1/integration/config/pipelines/{id} - Get/update/delete pipeline
- /api/v1/integration/config/pipelines/{id}/apply - Apply a pipeline
- /api/v1/integration/config/pipelines/{id}/modules - Module links
- /api/v1/integration/config/interoperability - Interoperability matrix
- /api/v1/integration/config/status - Current config status

These routes power the Integration Hub frontend at /integrations.
"""

import logging
import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, Body

from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/config", tags=["integration-config"])


# =============================================================================
# Pydantic Request/Response Models
# =============================================================================


class ModuleResponse(BaseModel):
    id: str
    name: str
    module_type: str
    category: str
    description: Optional[str] = None
    enabled: bool
    icon: str
    color: str
    settings: Dict[str, Any] = {}
    tags: List[str] = []
    depends_on: List[str] = []
    interoperable_with: List[str] = []


class PipelineResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    version: str = "1.0.0"
    status: str = "draft"
    feature_flags: Dict[str, bool] = {}
    bridge_settings: Dict[str, bool] = {}
    interoperability: Dict[str, List[str]] = {}
    module_overrides: Dict[str, Dict[str, Any]] = {}
    metadata_json: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class PipelineCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    module_links: Optional[List[Dict[str, Any]]] = None


class PipelineUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    feature_flags: Optional[Dict[str, bool]] = None
    bridge_settings: Optional[Dict[str, bool]] = None
    interoperability: Optional[Dict[str, List[str]]] = None
    module_overrides: Optional[Dict[str, Dict[str, Any]]] = None
    metadata_json: Optional[Dict[str, Any]] = None


class ModuleLinkResponse(BaseModel):
    id: str
    pipeline_id: str
    module_id: str
    enabled: bool
    order: int
    params: Dict[str, Any] = {}


class ModuleToggleRequest(BaseModel):
    enabled: bool


class ModuleSettingsRequest(BaseModel):
    settings: Dict[str, Any]


class InteroperabilityResponse(BaseModel):
    modules: List[Dict[str, Any]]
    matrix: Dict[str, Dict[str, bool]]


class ApplyResponse(BaseModel):
    success: bool
    pipeline_id: Optional[str] = None
    pipeline_name: Optional[str] = None
    status: Optional[str] = None
    modules_updated: Optional[int] = None
    applied: List[str] = []
    errors: List[str] = []
    error: Optional[str] = None


# =============================================================================
# Helper
# =============================================================================

def _get_service():
    from common_lib.modules.integration.services.config_service import (
        get_integration_config_service,
    )
    return get_integration_config_service()


def _serialize_pipeline(p: Any) -> Dict[str, Any]:
    return {
        "id": p.id,
        "name": p.name,
        "description": p.description,
        "version": p.version,
        "status": p.status,
        "feature_flags": p.feature_flags,
        "bridge_settings": p.bridge_settings,
        "interoperability": p.interoperability,
        "module_overrides": p.module_overrides,
        "metadata_json": p.metadata_json,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


def _serialize_module(m: Any) -> Dict[str, Any]:
    return {
        "id": m.id,
        "name": m.name,
        "module_type": m.module_type,
        "category": m.category,
        "description": m.description,
        "enabled": m.enabled,
        "icon": m.icon,
        "color": m.color,
        "settings": m.settings,
        "tags": m.tags,
        "depends_on": m.depends_on,
        "interoperable_with": m.interoperable_with,
    }


# =============================================================================
# Module Config Endpoints
# =============================================================================


@router.get("/modules", response_model=List[ModuleResponse])
async def list_modules(category: Optional[str] = Query(None)):
    """List all registered module configs, optionally filtered by category."""
    try:
        svc = _get_service()
        modules = svc.list_registered_modules(category=category)
        return [_serialize_module(m) for m in modules]
    except Exception as e:
        logger.error("List modules failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/modules/{module_id}", response_model=ModuleResponse)
async def get_module(module_id: str):
    """Get a single module config."""
    try:
        svc = _get_service()
        module = svc.get_module(module_id)
        if module is None:
            raise HTTPException(status_code=404, detail=f"Module not found: {module_id}")
        return _serialize_module(module)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Get module failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/modules/{module_id}/toggle", response_model=ModuleResponse)
async def toggle_module(module_id: str, request: ModuleToggleRequest):
    """Enable or disable a module."""
    try:
        svc = _get_service()
        module = svc.toggle_module(module_id, request.enabled)
        if module is None:
            raise HTTPException(status_code=404, detail=f"Module not found: {module_id}")
        return _serialize_module(module)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Toggle module failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/modules/{module_id}/settings", response_model=ModuleResponse)
async def update_module_settings(module_id: str, request: ModuleSettingsRequest):
    """Update module-specific settings."""
    try:
        svc = _get_service()
        module = svc.update_module_settings(module_id, request.settings)
        if module is None:
            raise HTTPException(status_code=404, detail=f"Module not found: {module_id}")
        return _serialize_module(module)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Update module settings failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/modules/{module_id}/interoperability", response_model=ModuleResponse)
async def update_module_interoperability(
    module_id: str,
    interoperable_with: List[str] = Body(..., embed=True),
):
    """Update which modules a module can interoperate with."""
    try:
        svc = _get_service()
        module = svc.update_interoperability(module_id, interoperable_with)
        if module is None:
            raise HTTPException(status_code=404, detail=f"Module not found: {module_id}")
        return _serialize_module(module)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Update interoperability failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Pipeline Config Endpoints
# =============================================================================


@router.get("/pipelines", response_model=List[PipelineResponse])
async def list_pipelines(status: Optional[str] = Query(None)):
    """List all saved pipeline configs."""
    try:
        svc = _get_service()
        pipelines = svc.list_pipelines(status=status)
        return [_serialize_pipeline(p) for p in pipelines]
    except Exception as e:
        logger.error("List pipelines failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pipelines", response_model=PipelineResponse, status_code=201)
async def create_pipeline(request: PipelineCreateRequest):
    """Create a new pipeline config."""
    try:
        svc = _get_service()
        pipeline = svc.create_pipeline(
            name=request.name,
            description=request.description,
            module_links=request.module_links,
        )
        return _serialize_pipeline(pipeline)
    except Exception as e:
        logger.error("Create pipeline failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pipelines/{pipeline_id}", response_model=PipelineResponse)
async def get_pipeline(pipeline_id: str):
    """Get a single pipeline config."""
    try:
        svc = _get_service()
        pipeline = svc.get_pipeline(pipeline_id)
        if pipeline is None:
            raise HTTPException(status_code=404, detail=f"Pipeline not found: {pipeline_id}")
        return _serialize_pipeline(pipeline)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Get pipeline failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/pipelines/{pipeline_id}", response_model=PipelineResponse)
async def update_pipeline(pipeline_id: str, request: PipelineUpdateRequest):
    """Update a pipeline config."""
    try:
        svc = _get_service()
        updates = {k: v for k, v in request.dict(exclude_none=True).items()}
        pipeline = svc.update_pipeline(pipeline_id, updates)
        if pipeline is None:
            raise HTTPException(status_code=404, detail=f"Pipeline not found: {pipeline_id}")
        return _serialize_pipeline(pipeline)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Update pipeline failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/pipelines/{pipeline_id}")
async def delete_pipeline(pipeline_id: str):
    """Delete a pipeline config."""
    try:
        svc = _get_service()
        deleted = svc.delete_pipeline(pipeline_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Pipeline not found: {pipeline_id}")
        return {"status": "ok", "message": f"Pipeline {pipeline_id} deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Delete pipeline failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pipelines/{pipeline_id}/apply", response_model=ApplyResponse)
async def apply_pipeline(pipeline_id: str):
    """Apply a pipeline config — activate it and update runtime behaviour."""
    try:
        svc = _get_service()
        result = svc.apply_pipeline(pipeline_id)
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error", "Apply failed"))
        return ApplyResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Apply pipeline failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Pipeline Module Links
# =============================================================================


@router.get("/pipelines/{pipeline_id}/modules", response_model=List[ModuleLinkResponse])
async def get_pipeline_module_links(pipeline_id: str):
    """Get all module links for a pipeline."""
    try:
        svc = _get_service()
        links = svc.get_pipeline_module_links(pipeline_id)
        return [
            {
                "id": l.id,
                "pipeline_id": l.pipeline_id,
                "module_id": l.module_id,
                "enabled": l.enabled,
                "order": l.order,
                "params": l.params,
            }
            for l in links
        ]
    except Exception as e:
        logger.error("Get pipeline module links failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pipelines/{pipeline_id}/modules", response_model=ModuleLinkResponse, status_code=201)
async def add_module_to_pipeline(
    pipeline_id: str,
    body: Dict[str, Any] = Body(...),
):
    """Add a module to a pipeline."""
    try:
        svc = _get_service()
        link = svc.add_module_to_pipeline(
            pipeline_id=pipeline_id,
            module_id=body["module_id"],
            order=body.get("order", 0),
            enabled=body.get("enabled", True),
            params=body.get("params"),
        )
        return {
            "id": link.id,
            "pipeline_id": link.pipeline_id,
            "module_id": link.module_id,
            "enabled": link.enabled,
            "order": link.order,
            "params": link.params,
        }
    except Exception as e:
        logger.error("Add module to pipeline failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/pipelines/{pipeline_id}/modules/{link_id}")
async def remove_module_from_pipeline(pipeline_id: str, link_id: str):
    """Remove a module from a pipeline."""
    try:
        svc = _get_service()
        deleted = svc.remove_module_from_pipeline(link_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Link not found: {link_id}")
        return {"status": "ok", "message": "Module removed from pipeline"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Remove module from pipeline failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Interoperability
# =============================================================================


@router.get("/interoperability", response_model=InteroperabilityResponse)
async def get_interoperability_matrix():
    """Get the full interoperability matrix."""
    try:
        svc = _get_service()
        return svc.get_interoperability_matrix()
    except Exception as e:
        logger.error("Get interoperability matrix failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Status
# =============================================================================


@router.get("/status")
async def get_config_status():
    """Get a snapshot of the current integration configuration status."""
    try:
        svc = _get_service()
        return svc.get_config_status()
    except Exception as e:
        logger.error("Get config status failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/seed")
async def seed_default_modules():
    """Seed the default module definitions into the database."""
    try:
        svc = _get_service()
        count = svc.seed_default_modules()
        return {"status": "ok", "message": f"Seeded {count} modules", "count": count}
    except Exception as e:
        logger.error("Seed modules failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
