"""
Self-Learning Config Store — API Routes.

Single table with category discriminator:
  'full'        → instance bundle (name, desc, tags, variant, all configs)
  'qualityLog'  → quality log config
  'autoEvolve'  → strategy evolver config
  'scorer'      → scorer config
  'failure'     → failure analyzer config
  'reasoner'    → meta reasoner config
  'belief'      → belief reviser config
  'conflict'    → conflict resolver config
  'branching'   → evolution branching config
  'pruner'      → knowledge pruner config
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field

from sqlmodel import Session

from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.data_storage.database.repository import NotFoundError
from common_lib.modules.knowledge_engine.services.instance_config_service import (
    CATEGORIES,
    InstanceConfigService,
)

logger = logging.getLogger(__name__)

router = APIRouter()

_instance_svc = InstanceConfigService()


# ── Request Schemas ─────────────────────────────────────────


class ConfigWriteRequest(BaseModel):
    config_data: dict[str, Any] = Field(
        ..., description="Config data for this category"
    )


class InstanceCreateRequest(BaseModel):
    name: str = Field(..., description="Instance name", min_length=1)
    description: str = Field("", description="Instance description")
    tags: list[str] = Field(default_factory=list)
    variant: str = Field("v1", description="UI variant (v1-v5)")
    configs: dict[str, Any] = Field(
        default_factory=dict,
        description="Per-component configs keyed by category",
    )


class InstanceUpdateRequest(BaseModel):
    name: Optional[str] = Field(None)
    description: Optional[str] = Field(None)
    tags: Optional[list[str]] = Field(None)
    variant: Optional[str] = Field(None)
    configs: Optional[dict[str, Any]] = Field(None)


class CategoryConfigCreateRequest(BaseModel):
    category: str = Field(..., description="Config category")
    config_data: dict[str, Any] = Field(..., description="Config data")
    name: str = Field(
        ..., description="Friendly name of this config preset", min_length=1
    )
    description: str = Field("", description="Description")


class CategoryConfigUpdateRequest(BaseModel):
    config_data: dict[str, Any] = Field(..., description="Config data")
    name: Optional[str] = Field(None)
    description: Optional[str] = Field(None)


# ── Category-filtered Config List ──────────────────────────────
# GET /learning/configs?category=scorer  →  all scorer configs
# GET /learning/configs                  →  all configs (optionally by instance_id)


@router.get("/learning/configs")
async def list_configs(
    category: Optional[str] = Query(None, description="Filter by config category"),
    instance_id: Optional[str] = Query(None, description="Filter by instance_id"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """List config rows with optional category/instance_id filters.

    UI uses this to show per-component config lists (e.g. ?category=scorer).
    """
    try:
        data = _instance_svc.list_configs(
            session,
            category=category,
            instance_id=instance_id,
            offset=offset,
            limit=limit,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    return {
        "success": True,
        "data": data,
        "message": f"Found {data['total']} configs",
    }


@router.post("/learning/configs", status_code=201)
async def create_category_config(
    request: CategoryConfigCreateRequest,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Create an individual component configuration with a parent instance bundle."""
    try:
        if request.category not in CATEGORIES or request.category == "full":
            raise HTTPException(400, f"Invalid category: {request.category}")

        result = _instance_svc.create_category_config(
            session,
            category=request.category,
            config_data=request.config_data,
            name=request.name,
            description=request.description,
        )

        return {
            "success": True,
            "data": result,
            "message": f"Config for '{request.category}' created",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to create category config")
        raise HTTPException(
            status_code=500, detail=f"Failed to create config: {str(e)}"
        )


@router.put("/learning/configs/{config_id}")
async def update_category_config(
    config_id: int,
    request: CategoryConfigUpdateRequest,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Update a specific component configuration and its parent instance details."""
    try:
        result = _instance_svc.update_category_config(
            session,
            config_id=config_id,
            config_data=request.config_data,
            name=request.name,
            description=request.description,
        )

        return {
            "success": True,
            "data": result,
            "message": "Config updated",
        }
    except NotFoundError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        logger.exception("Failed to update config")
        raise HTTPException(
            status_code=500, detail=f"Failed to update config: {str(e)}"
        )


@router.delete("/learning/configs/{config_id}")
async def delete_category_config(
    config_id: int,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Delete a specific component config and its parent instance bundle."""
    try:
        result = _instance_svc.delete_category_config(session, config_id=config_id)

        return {
            "success": True,
            "data": result,
            "message": "Config deleted successfully",
        }
    except NotFoundError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        logger.exception("Failed to delete config")
        raise HTTPException(
            status_code=500, detail=f"Failed to delete config: {str(e)}"
        )


# ── Instance CRUD ─────────────────────────────────────────
# These endpoints operate on the bundle of rows sharing an instance_id.


@router.get("/learning/instances")
async def list_instances(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """List all instance bundles (rows where category='full')."""
    try:
        data = _instance_svc.list_instances(session, offset=offset, limit=limit)
    except Exception as e:
        logger.exception("Failed to list instances")
        raise HTTPException(500, detail=f"Failed to list instances: {str(e)}")

    return {
        "success": True,
        "data": data,
        "message": f"Found {data['total']} instances",
    }


@router.post("/learning/instances", status_code=201)
async def create_instance(
    request: InstanceCreateRequest,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Create a full instance bundle with component configs."""
    try:
        result = _instance_svc.create_instance(
            session,
            name=request.name,
            description=request.description,
            tags=request.tags,
            variant=request.variant,
            configs=request.configs,
        )

        return {
            "success": True,
            "data": result,
            "message": f"Instance '{request.name}' created",
        }
    except Exception as e:
        logger.exception("Failed to create instance")
        raise HTTPException(
            status_code=500, detail=f"Failed to create instance: {str(e)}"
        )


@router.get("/learning/instances/{instance_id}")
async def get_instance(
    instance_id: str = Path(..., description="Instance identifier"),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Get a full instance bundle by instance_id."""
    result = _instance_svc.get_instance(session, instance_id)

    if result is None:
        raise HTTPException(404, f"Instance {instance_id} not found")

    return {
        "success": True,
        "data": result,
        "message": "Instance retrieved",
    }


@router.put("/learning/instances/{instance_id}")
async def update_instance(
    request: InstanceUpdateRequest,
    instance_id: str = Path(..., description="Instance to update"),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Update an instance bundle — replaces component rows."""
    try:
        result = _instance_svc.update_instance(
            session,
            instance_id=instance_id,
            name=request.name,
            description=request.description,
            tags=request.tags,
            variant=request.variant,
            configs=request.configs,
        )

        return {
            "success": True,
            "data": result,
            "message": "Instance updated",
        }
    except NotFoundError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        logger.exception("Failed to update instance")
        raise HTTPException(
            status_code=500, detail=f"Failed to update instance: {str(e)}"
        )


@router.delete("/learning/instances/{instance_id}")
async def delete_instance(
    instance_id: str = Path(..., description="Instance to delete"),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Delete all config rows for an instance."""
    try:
        _instance_svc.delete_instance(session, instance_id)

        return {
            "success": True,
            "data": {"id": instance_id},
            "message": f"Instance {instance_id} deleted",
        }
    except NotFoundError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        logger.exception("Failed to delete instance")
        raise HTTPException(
            status_code=500, detail=f"Failed to delete instance: {str(e)}"
        )
