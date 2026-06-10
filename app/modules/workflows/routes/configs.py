"""Workflow Config CRUD API routes.

All logic delegated to common_lib.modules.workflows.config_service.WorkflowConfigService.
"""

import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

from app.core.common_lib_integration import common_memory, sync_entity_to_fs
from app.modules.common.types.index import APIResponse
from common_lib.modules.workflows.config_service import WorkflowConfigService

logger = logging.getLogger(__name__)

router = APIRouter()

# ─── Pydantic Models ───────────────────────────────────────────────────────

class WorkflowConfigCreate(BaseModel):
    name: str
    workflow_id: Optional[str] = None
    version: str = "1.0.0"
    description: str = ""
    category: str = "General"
    tags: List[str] = []
    status: str = "ACTIVE"
    definition: Dict[str, Any] = {}
    field_schema: Dict[str, Any] = {}
    image_gallery: List[Dict[str, Any]] = []
    metadata_json: Dict[str, Any] = {}

class WorkflowConfigUpdate(BaseModel):
    name: Optional[str] = None
    workflow_id: Optional[str] = None
    version: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    status: Optional[str] = None
    definition: Optional[Dict[str, Any]] = None
    field_schema: Optional[Dict[str, Any]] = None
    image_gallery: Optional[List[Dict[str, Any]]] = None
    metadata_json: Optional[Dict[str, Any]] = None

class CommentCreate(BaseModel):
    content: str
    author_id: Optional[str] = None
    author_name: Optional[str] = None
    parent_id: Optional[str] = None

class CommentUpdate(BaseModel):
    content: Optional[str] = None
    is_resolved: Optional[bool] = None

class ImageCreate(BaseModel):
    url: str
    thumbnail_url: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    file_size: Optional[int] = None
    seed: Optional[int] = None
    prompt_used: Optional[str] = None
    negative_prompt_used: Optional[str] = None
    generation_params: Dict[str, Any] = {}

# ─── Service Init ───────────────────────────────────────────────────────────

_svc = WorkflowConfigService(common_memory)
_svc.set_sync_hook(sync_entity_to_fs)

# ─── Config CRUD ────────────────────────────────────────────────────────────

@router.get("/", response_model=APIResponse[List[Dict[str, Any]]])
async def list_workflow_configs(
    workflow_id: Optional[str] = Query(None, description="Filter by parent workflow ID"),
    category: Optional[str] = Query(None, description="Filter by category"),
    status: Optional[str] = Query(None, description="Filter by status"),
):
    try:
        configs = _svc.list_configs(workflow_id=workflow_id, category=category, status=status)
        return APIResponse(data=configs, message="Workflow configs retrieved")
    except Exception as e:
        logger.error(f"Failed to list workflow configs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/by-workflow/{workflow_id}", response_model=APIResponse[List[Dict[str, Any]]])
async def list_workflow_configs_by_workflow(workflow_id: str):
    try:
        configs = _svc.list_configs(workflow_id=workflow_id)
        return APIResponse(data=configs, message=f"Found {len(configs)} configs for workflow '{workflow_id}'")
    except Exception as e:
        logger.error(f"Failed to list configs for workflow {workflow_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{config_id}", response_model=APIResponse[Dict[str, Any]])
async def get_workflow_config(config_id: str):
    try:
        config = _svc.get_config(config_id)
        if not config:
            raise HTTPException(status_code=404, detail=f"Config '{config_id}' not found")
        return APIResponse(data=config, message="Workflow config retrieved")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get workflow config {config_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/", response_model=APIResponse[Dict[str, Any]])
async def create_workflow_config(data: WorkflowConfigCreate):
    try:
        config = _svc.create_config(
            name=data.name, workflow_id=data.workflow_id, version=data.version,
            description=data.description, category=data.category, tags=data.tags,
            status=data.status, definition=data.definition, field_schema=data.field_schema,
            image_gallery=data.image_gallery, metadata_json=data.metadata_json,
        )
        _svc._sync_to_fs(config.get("id", ""))
        return APIResponse(data=config, message="Workflow config created", status_code=201)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create workflow config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{config_id}", response_model=APIResponse[Dict[str, Any]])
async def update_workflow_config(config_id: str, data: WorkflowConfigUpdate):
    try:
        config = _svc.update_config(config_id, data.model_dump(exclude_unset=True))
        _svc._sync_to_fs(config_id)
        return APIResponse(data=config, message="Workflow config updated")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update workflow config {config_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{config_id}", response_model=APIResponse[Dict[str, Any]])
async def delete_workflow_config(config_id: str):
    try:
        _svc.delete_config(config_id)
        return APIResponse(data={"id": config_id}, message="Workflow config deleted")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete workflow config {config_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─── Auto-generate configs ─────────────────────────────────────────────────


@router.post("/workflows/{workflow_id}/generate-configs", response_model=APIResponse[List[Dict[str, Any]]])
async def generate_workflow_configs(
    workflow_id: str,
    prompt_source: str = Query("random", description="Source of prompts: 'random', 'prompthero', or 'database'"),
    prompthero_model: str = Query("sd15", description="Model slug for prompthero scraping"),
):
    try:
        configs = _svc.generate_configs(workflow_id, prompt_source=prompt_source, prompthero_model=prompthero_model)
        for c in configs:
            _svc._sync_to_fs(c.get("id", ""))
        return APIResponse(
            data=configs,
            message=f"Generated {len(configs)} config variants for workflow '{workflow_id}'",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate configs for workflow {workflow_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─── Seed / Bulk Generate ─────────────────────────────────────────────────


@router.post("/seed", response_model=APIResponse[Dict[str, Any]])
async def seed_all_workflow_configs(
    priority: str = Query("sd15", description="Priority workflow type: 'sd15', 'audio', 'all'"),
    force: bool = Query(False, description="Re-generate configs even if they already exist"),
):
    try:
        results = _svc.seed_all_configs(priority=priority, force=force, sync_hook=sync_entity_to_fs)
        return APIResponse(
            data=results,
            message=f"Seeded {results['imported_yaml']} YAML + {results['auto_generated']} auto-generated configs",
        )
    except Exception as e:
        logger.error(f"Failed to seed configs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─── Comments ───────────────────────────────────────────────────────────────


@router.get("/{config_id}/comments", response_model=APIResponse[List[Dict[str, Any]]])
async def list_comments(config_id: str):
    try:
        comments = _svc.list_comments(config_id)
        return APIResponse(data=comments, message="Comments retrieved")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to list comments for config {config_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{config_id}/comments", response_model=APIResponse[Dict[str, Any]])
async def create_comment(config_id: str, data: CommentCreate):
    try:
        comment = _svc.add_comment(
            config_id, content=data.content, author_id=data.author_id,
            author_name=data.author_name, parent_id=data.parent_id,
        )
        return APIResponse(data=comment, message="Comment added", status_code=201)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to add comment to config {config_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{config_id}/comments/{comment_id}", response_model=APIResponse[Dict[str, Any]])
async def update_comment(config_id: str, comment_id: str, data: CommentUpdate):
    try:
        target = _svc.update_comment(config_id, comment_id, content=data.content, is_resolved=data.is_resolved)
        return APIResponse(data=target, message="Comment updated")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update comment {comment_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{config_id}/comments/{comment_id}", response_model=APIResponse[Dict[str, Any]])
async def delete_comment(config_id: str, comment_id: str):
    try:
        _svc.delete_comment(config_id, comment_id)
        return APIResponse(data={"id": comment_id}, message="Comment deleted")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to delete comment {comment_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─── Image Gallery ──────────────────────────────────────────────────────────


@router.get("/{config_id}/images", response_model=APIResponse[List[Dict[str, Any]]])
async def list_images(config_id: str):
    try:
        config = _svc.get_config(config_id)
        if not config:
            raise HTTPException(status_code=404, detail=f"Config '{config_id}' not found")
        return APIResponse(data=config.get("image_gallery", []), message="Images retrieved")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list images for config {config_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{config_id}/images", response_model=APIResponse[Dict[str, Any]])
async def add_image(config_id: str, data: ImageCreate):
    try:
        image = _svc.add_image(config_id, data.model_dump())
        return APIResponse(data=image, message="Image added", status_code=201)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to add image to config {config_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{config_id}/images/{image_id}", response_model=APIResponse[Dict[str, Any]])
async def delete_image(config_id: str, image_id: str):
    try:
        _svc.delete_image(config_id, image_id)
        return APIResponse(data={"id": image_id}, message="Image deleted")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to delete image {image_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─── Stats ──────────────────────────────────────────────────────────────────


@router.get("/stats", response_model=APIResponse[Dict[str, Any]])
async def get_config_stats():
    try:
        stats = _svc.get_stats()
        return APIResponse(data=stats, message="Config statistics retrieved")
    except Exception as e:
        logger.error(f"Failed to get config stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))
