"""Workflow Config CRUD API routes.

Provides full REST endpoints for workflow configuration presets:
- List, get, create, update, delete configs
- Comments (threaded)
- Image gallery
"""

import logging
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

from app.core.common_lib_integration import common_memory, sync_entity_to_fs
from app.modules.common.types.index import APIResponse

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


# ─── Config CRUD ────────────────────────────────────────────────────────────


@router.get("/", response_model=APIResponse[List[Dict[str, Any]]])
async def list_workflow_configs(
    workflow_id: Optional[str] = Query(
        None, description="Filter by parent workflow ID"
    ),
    category: Optional[str] = Query(None, description="Filter by category"),
    status: Optional[str] = Query(None, description="Filter by status"),
):
    """List all workflow configs, optionally filtered."""
    try:
        if workflow_id:
            configs = common_memory.get_workflow_configs_by_workflow_id(workflow_id)
        else:
            configs = common_memory.list_workflow_config_definitions()

        if category:
            configs = [c for c in configs if c.get("category") == category]
        if status:
            configs = [c for c in configs if c.get("status") == status]

        return APIResponse(data=configs, message="Workflow configs retrieved")
    except Exception as e:
        logger.error(f"Failed to list workflow configs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{config_id}", response_model=APIResponse[Dict[str, Any]])
async def get_workflow_config(config_id: str):
    """Get a single workflow config by ID."""
    try:
        config = common_memory.get_workflow_config_definition(config_id)
        if not config:
            raise HTTPException(
                status_code=404, detail=f"Config '{config_id}' not found"
            )
        return APIResponse(data=config, message="Workflow config retrieved")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get workflow config {config_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/", response_model=APIResponse[Dict[str, Any]])
async def create_workflow_config(data: WorkflowConfigCreate):
    """Create a new workflow config."""
    try:
        config_id = data.name.lower().replace(" ", "_") or str(uuid.uuid4())[:8]

        # Check for duplicate
        existing = common_memory.get_workflow_config_definition(config_id)
        if existing:
            config_id = f"{config_id}_{uuid.uuid4().hex[:6]}"

        success = common_memory.save_workflow_config_definition(
            config_id=config_id,
            name=data.name,
            definition=data.definition,
            version=data.version,
            description=data.description,
            category=data.category,
            tags=data.tags,
            status=data.status,
            workflow_id=data.workflow_id,
            field_schema=data.field_schema,
            image_gallery=data.image_gallery,
            metadata_json=data.metadata_json,
            artifacts={
                "import_source": "api",
                "created_at": datetime.utcnow().isoformat(),
            },
        )

        if not success:
            raise HTTPException(status_code=500, detail="Failed to create config")

        # Sync to filesystem
        sync_entity_to_fs("workflow_config", config_id)

        config = common_memory.get_workflow_config_definition(config_id)
        return APIResponse(
            data=config, message="Workflow config created", status_code=201
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create workflow config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{config_id}", response_model=APIResponse[Dict[str, Any]])
async def update_workflow_config(config_id: str, data: WorkflowConfigUpdate):
    """Update an existing workflow config."""
    try:
        existing = common_memory.get_workflow_config_definition(config_id)
        if not existing:
            raise HTTPException(
                status_code=404, detail=f"Config '{config_id}' not found"
            )

        # Merge updates
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if value is not None:
                existing[key] = value

        success = common_memory.save_workflow_config_definition(
            config_id=config_id,
            name=existing.get("name"),
            definition=existing.get("definition", {}),
            version=existing.get("version", "1.0.0"),
            description=existing.get("description", ""),
            category=existing.get("category", "General"),
            tags=existing.get("tags", []),
            status=existing.get("status", "ACTIVE"),
            workflow_id=existing.get("workflow_id"),
            field_schema=existing.get("field_schema", {}),
            image_gallery=existing.get("image_gallery", []),
            metadata_json=existing.get("metadata_json", {}),
            artifacts=existing.get("artifacts", {}),
        )

        if not success:
            raise HTTPException(status_code=500, detail="Failed to update config")

        sync_entity_to_fs("workflow_config", config_id)

        config = common_memory.get_workflow_config_definition(config_id)
        return APIResponse(data=config, message="Workflow config updated")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update workflow config {config_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{config_id}", response_model=APIResponse[Dict[str, Any]])
async def delete_workflow_config(config_id: str):
    """Delete a workflow config."""
    try:
        existing = common_memory.get_workflow_config_definition(config_id)
        if not existing:
            raise HTTPException(
                status_code=404, detail=f"Config '{config_id}' not found"
            )

        success = common_memory.delete_workflow_config_definition(config_id)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete config")

        return APIResponse(data={"id": config_id}, message="Workflow config deleted")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete workflow config {config_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─── Comments ───────────────────────────────────────────────────────────────


@router.get("/{config_id}/comments", response_model=APIResponse[List[Dict[str, Any]]])
async def list_comments(config_id: str):
    """List all comments for a config."""
    try:
        config = common_memory.get_workflow_config_definition(config_id)
        if not config:
            raise HTTPException(
                status_code=404, detail=f"Config '{config_id}' not found"
            )

        comments = config.get("metadata_json", {}).get("comments", [])
        # Filter out deleted
        comments = [c for c in comments if not c.get("is_deleted", False)]
        return APIResponse(data=comments, message="Comments retrieved")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list comments for config {config_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{config_id}/comments", response_model=APIResponse[Dict[str, Any]])
async def create_comment(config_id: str, data: CommentCreate):
    """Add a comment to a config."""
    try:
        config = common_memory.get_workflow_config_definition(config_id)
        if not config:
            raise HTTPException(
                status_code=404, detail=f"Config '{config_id}' not found"
            )

        comment = {
            "id": str(uuid.uuid4()),
            "config_id": config_id,
            "parent_id": data.parent_id,
            "author_id": data.author_id,
            "author_name": data.author_name or "Anonymous",
            "content": data.content,
            "reactions": {},
            "is_resolved": False,
            "is_deleted": False,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }

        metadata = config.get("metadata_json", {})
        comments = metadata.get("comments", [])
        comments.append(comment)
        metadata["comments"] = comments

        common_memory.save_workflow_config_definition(
            config_id=config_id,
            name=config.get("name"),
            definition=config.get("definition", {}),
            version=config.get("version", "1.0.0"),
            description=config.get("description", ""),
            category=config.get("category", "General"),
            tags=config.get("tags", []),
            status=config.get("status", "ACTIVE"),
            workflow_id=config.get("workflow_id"),
            field_schema=config.get("field_schema", {}),
            image_gallery=config.get("image_gallery", []),
            metadata_json=metadata,
            artifacts=config.get("artifacts", {}),
        )

        return APIResponse(data=comment, message="Comment added", status_code=201)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add comment to config {config_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put(
    "/{config_id}/comments/{comment_id}", response_model=APIResponse[Dict[str, Any]]
)
async def update_comment(config_id: str, comment_id: str, data: CommentUpdate):
    """Update a comment."""
    try:
        config = common_memory.get_workflow_config_definition(config_id)
        if not config:
            raise HTTPException(
                status_code=404, detail=f"Config '{config_id}' not found"
            )

        metadata = config.get("metadata_json", {})
        comments = metadata.get("comments", [])
        target = None
        for c in comments:
            if c["id"] == comment_id:
                target = c
                break

        if not target:
            raise HTTPException(
                status_code=404, detail=f"Comment '{comment_id}' not found"
            )

        if data.content is not None:
            target["content"] = data.content
        if data.is_resolved is not None:
            target["is_resolved"] = data.is_resolved
        target["updated_at"] = datetime.utcnow().isoformat()

        metadata["comments"] = comments
        common_memory.save_workflow_config_definition(
            config_id=config_id,
            name=config.get("name"),
            definition=config.get("definition", {}),
            version=config.get("version", "1.0.0"),
            description=config.get("description", ""),
            category=config.get("category", "General"),
            tags=config.get("tags", []),
            status=config.get("status", "ACTIVE"),
            workflow_id=config.get("workflow_id"),
            field_schema=config.get("field_schema", {}),
            image_gallery=config.get("image_gallery", []),
            metadata_json=metadata,
            artifacts=config.get("artifacts", {}),
        )

        return APIResponse(data=target, message="Comment updated")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update comment {comment_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/{config_id}/comments/{comment_id}", response_model=APIResponse[Dict[str, Any]]
)
async def delete_comment(config_id: str, comment_id: str):
    """Soft-delete a comment."""
    try:
        config = common_memory.get_workflow_config_definition(config_id)
        if not config:
            raise HTTPException(
                status_code=404, detail=f"Config '{config_id}' not found"
            )

        metadata = config.get("metadata_json", {})
        comments = metadata.get("comments", [])
        for c in comments:
            if c["id"] == comment_id:
                c["is_deleted"] = True
                c["updated_at"] = datetime.utcnow().isoformat()
                break

        metadata["comments"] = comments
        common_memory.save_workflow_config_definition(
            config_id=config_id,
            name=config.get("name"),
            definition=config.get("definition", {}),
            version=config.get("version", "1.0.0"),
            description=config.get("description", ""),
            category=config.get("category", "General"),
            tags=config.get("tags", []),
            status=config.get("status", "ACTIVE"),
            workflow_id=config.get("workflow_id"),
            field_schema=config.get("field_schema", {}),
            image_gallery=config.get("image_gallery", []),
            metadata_json=metadata,
            artifacts=config.get("artifacts", {}),
        )

        return APIResponse(data={"id": comment_id}, message="Comment deleted")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete comment {comment_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─── Image Gallery ──────────────────────────────────────────────────────────


@router.get("/{config_id}/images", response_model=APIResponse[List[Dict[str, Any]]])
async def list_images(config_id: str):
    """List all images for a config."""
    try:
        config = common_memory.get_workflow_config_definition(config_id)
        if not config:
            raise HTTPException(
                status_code=404, detail=f"Config '{config_id}' not found"
            )

        images = config.get("image_gallery", [])
        return APIResponse(data=images, message="Images retrieved")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list images for config {config_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{config_id}/images", response_model=APIResponse[Dict[str, Any]])
async def add_image(config_id: str, data: ImageCreate):
    """Add an image to a config's gallery."""
    try:
        config = common_memory.get_workflow_config_definition(config_id)
        if not config:
            raise HTTPException(
                status_code=404, detail=f"Config '{config_id}' not found"
            )

        image = {
            "id": str(uuid.uuid4()),
            "url": data.url,
            "thumbnail_url": data.thumbnail_url,
            "width": data.width,
            "height": data.height,
            "file_size": data.file_size,
            "seed": data.seed,
            "prompt_used": data.prompt_used,
            "negative_prompt_used": data.negative_prompt_used,
            "generation_params": data.generation_params,
            "likes": 0,
            "is_featured": False,
            "created_at": datetime.utcnow().isoformat(),
        }

        gallery = config.get("image_gallery", [])
        gallery.append(image)

        common_memory.save_workflow_config_definition(
            config_id=config_id,
            name=config.get("name"),
            definition=config.get("definition", {}),
            version=config.get("version", "1.0.0"),
            description=config.get("description", ""),
            category=config.get("category", "General"),
            tags=config.get("tags", []),
            status=config.get("status", "ACTIVE"),
            workflow_id=config.get("workflow_id"),
            field_schema=config.get("field_schema", {}),
            image_gallery=gallery,
            metadata_json=config.get("metadata_json", {}),
            artifacts=config.get("artifacts", {}),
        )

        return APIResponse(data=image, message="Image added", status_code=201)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add image to config {config_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/{config_id}/images/{image_id}", response_model=APIResponse[Dict[str, Any]]
)
async def delete_image(config_id: str, image_id: str):
    """Remove an image from a config's gallery."""
    try:
        config = common_memory.get_workflow_config_definition(config_id)
        if not config:
            raise HTTPException(
                status_code=404, detail=f"Config '{config_id}' not found"
            )

        gallery = config.get("image_gallery", [])
        gallery = [img for img in gallery if img.get("id") != image_id]

        common_memory.save_workflow_config_definition(
            config_id=config_id,
            name=config.get("name"),
            definition=config.get("definition", {}),
            version=config.get("version", "1.0.0"),
            description=config.get("description", ""),
            category=config.get("category", "General"),
            tags=config.get("tags", []),
            status=config.get("status", "ACTIVE"),
            workflow_id=config.get("workflow_id"),
            field_schema=config.get("field_schema", {}),
            image_gallery=gallery,
            metadata_json=config.get("metadata_json", {}),
            artifacts=config.get("artifacts", {}),
        )

        return APIResponse(data={"id": image_id}, message="Image deleted")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete image {image_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─── Stats ──────────────────────────────────────────────────────────────────


@router.get("/stats", response_model=APIResponse[Dict[str, Any]])
async def get_config_stats():
    """Get workflow config statistics."""
    try:
        configs = common_memory.list_workflow_config_definitions()
        categories = {}
        statuses = {}
        workflow_counts = {}

        for c in configs:
            cat = c.get("category", "General")
            categories[cat] = categories.get(cat, 0) + 1
            status = c.get("status", "ACTIVE")
            statuses[status] = statuses.get(status, 0) + 1
            wf_id = c.get("workflow_id")
            if wf_id:
                workflow_counts[wf_id] = workflow_counts.get(wf_id, 0) + 1

        stats = {
            "total": len(configs),
            "categories": categories,
            "statuses": statuses,
            "configs_per_workflow": workflow_counts,
        }
        return APIResponse(data=stats, message="Config statistics retrieved")
    except Exception as e:
        logger.error(f"Failed to get config stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))
