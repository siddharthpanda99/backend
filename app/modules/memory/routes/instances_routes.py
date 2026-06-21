"""Memory Instance API Routes.

Provides REST endpoints for Memory Instance lifecycle management
and capability-filtered scoped search.
"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session

from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.memory.blocks_service import get_instance_service

router = APIRouter(tags=["memory-instances"])
logger = logging.getLogger(__name__)


# ── Request / Response Models ──────────────────────────────────────


class CreateInstanceRequest(BaseModel):
    name: str
    description: str = ""
    composition_id: str = ""
    block_ids: list[str] = []
    capability_filter: list[str] = []
    config_overrides: dict[str, dict] = {}


class UpdateInstanceRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    enabled: Optional[bool] = None
    capability_filter: Optional[list[str]] = None
    config_overrides: Optional[dict[str, dict]] = None
    block_ids: Optional[list[str]] = None


class SearchInstanceRequest(BaseModel):
    query: str
    limit: int = 10


# ── Instance CRUD Endpoints ───────────────────────────────────────


@router.get("/instances")
async def list_instances(
    enabled_only: bool = Query(False),
    session: Session = Depends(get_session),
):
    """List all memory instances."""
    try:
        service = get_instance_service()
        result = service.list_instances(session, enabled_only=enabled_only)
        return {"status": "ok", **result}
    except Exception as e:
        logger.error(f"Failed to list instances: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/instances")
async def create_instance(
    request: CreateInstanceRequest,
    session: Session = Depends(get_session),
):
    """Create a new memory instance."""
    try:
        service = get_instance_service()
        instance = service.create_instance(
            session=session,
            name=request.name,
            description=request.description,
            composition_id=request.composition_id,
            block_ids=request.block_ids,
            capability_filter=request.capability_filter,
            config_overrides=request.config_overrides,
        )
        return {"status": "ok", "instance": instance}
    except Exception as e:
        logger.error(f"Failed to create instance: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/instances/{instance_id}")
async def get_instance(
    instance_id: str,
    session: Session = Depends(get_session),
):
    """Get a specific memory instance by ID."""
    try:
        service = get_instance_service()
        instance = service.get_instance(instance_id, session)
        return {"status": "ok", "instance": instance}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get instance: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/instances/{instance_id}")
async def update_instance(
    instance_id: str,
    request: UpdateInstanceRequest,
    session: Session = Depends(get_session),
):
    """Update an existing memory instance."""
    try:
        service = get_instance_service()
        kwargs = {k: v for k, v in request.model_dump(exclude_none=True).items()}
        instance = service.update_instance(instance_id, session, **kwargs)
        return {"status": "ok", "instance": instance}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update instance: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/instances/{instance_id}")
async def delete_instance(
    instance_id: str,
    session: Session = Depends(get_session),
):
    """Delete a memory instance."""
    try:
        service = get_instance_service()
        service.delete_instance(instance_id, session)
        return {"status": "ok", "message": f"Instance {instance_id} deleted"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to delete instance: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/instances/{instance_id}/deploy")
async def deploy_instance(
    instance_id: str,
    session: Session = Depends(get_session),
):
    """Deploy (activate) a memory instance."""
    try:
        service = get_instance_service()
        instance = service.deploy_instance(instance_id, session)
        return {"status": "ok", "instance": instance}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to deploy instance: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/instances/{instance_id}/search")
async def search_instance(
    instance_id: str,
    request: SearchInstanceRequest,
    session: Session = Depends(get_session),
):
    """Search within an instance's allowed capabilities only."""
    try:
        service = get_instance_service()
        result = service.search_instance(
            instance_id,
            session,
            query_text=request.query,
            limit=request.limit,
        )
        return {"status": "ok", **result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to search instance: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ── Capabilities Endpoints ─────────────────────────────────────────


@router.get("/capabilities")
async def list_capabilities():
    """List all available memory capabilities across all blocks."""
    try:
        service = get_instance_service()
        result = service.list_all_capabilities()
        return {"status": "ok", **result}
    except Exception as e:
        logger.error(f"Failed to list capabilities: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/capabilities/search")
async def search_capabilities(
    query: str = Query(..., min_length=1),
):
    """Search capabilities by name, block name, or category."""
    try:
        service = get_instance_service()
        result = service.search_capabilities(query)
        return {"status": "ok", **result}
    except Exception as e:
        logger.error(f"Failed to search capabilities: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
