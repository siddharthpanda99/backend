"""Entity Instance API Routes — Unified CRUD for scoped entity instances.

Provides REST endpoints for creating and managing entity instances across
all entity types (tool, node, skill, memory, kb, agent).
"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session

from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.entities.instance_service import get_instance_service

router = APIRouter(prefix="/instances", tags=["entity-instances"])
logger = logging.getLogger(__name__)


# ── Request / Response Models ──────────────────────────────────────


class CreateEntityInstanceRequest(BaseModel):
    entity_type: str
    name: str
    description: str = ""
    filter_criteria: dict = {}
    allowed_ids: list[str] = []
    enabled: bool = True


class UpdateEntityInstanceRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    entity_type: Optional[str] = None
    filter_criteria: Optional[dict] = None
    allowed_ids: Optional[list[str]] = None
    enabled: Optional[bool] = None


class ValidateAccessRequest(BaseModel):
    item_id: str


class SearchInstanceRequest(BaseModel):
    query: str
    entity_type: Optional[str] = None
    limit: int = 10


# ── Instance CRUD Endpoints ───────────────────────────────────────


@router.get("")
async def list_instances(
    entity_type: Optional[str] = Query(None),
    enabled_only: bool = Query(False),
    session: Session = Depends(get_session),
):
    """List entity instances, optionally filtered by type."""
    try:
        service = get_instance_service()
        result = service.list(
            session, entity_type=entity_type, enabled_only=enabled_only
        )
        return {"status": "ok", **result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to list instances: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("")
async def create_instance(
    request: CreateEntityInstanceRequest,
    session: Session = Depends(get_session),
):
    """Create a new entity instance."""
    try:
        service = get_instance_service()
        instance = service.create(
            session=session,
            entity_type=request.entity_type,
            name=request.name,
            description=request.description,
            filter_criteria=request.filter_criteria,
            allowed_ids=request.allowed_ids,
            enabled=request.enabled,
        )
        return {"status": "ok", "instance": instance}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create instance: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{instance_id}")
async def get_instance(
    instance_id: str,
    session: Session = Depends(get_session),
):
    """Get a specific entity instance by ID."""
    try:
        service = get_instance_service()
        instance = service.get(instance_id, session)
        return {"status": "ok", "instance": instance}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get instance: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{instance_id}")
async def update_instance(
    instance_id: str,
    request: UpdateEntityInstanceRequest,
    session: Session = Depends(get_session),
):
    """Update an existing entity instance."""
    try:
        service = get_instance_service()
        kwargs = {k: v for k, v in request.model_dump(exclude_none=True).items()}
        instance = service.update(instance_id, session, **kwargs)
        return {"status": "ok", "instance": instance}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update instance: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{instance_id}")
async def delete_instance(
    instance_id: str,
    session: Session = Depends(get_session),
):
    """Delete an entity instance."""
    try:
        service = get_instance_service()
        service.delete(instance_id, session)
        return {"status": "ok", "message": f"Instance {instance_id} deleted"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to delete instance: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{instance_id}/enable")
async def enable_instance(
    instance_id: str,
    session: Session = Depends(get_session),
):
    """Enable an entity instance."""
    try:
        service = get_instance_service()
        instance = service.set_enabled(instance_id, True, session)
        return {"status": "ok", "instance": instance}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to enable instance: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{instance_id}/disable")
async def disable_instance(
    instance_id: str,
    session: Session = Depends(get_session),
):
    """Disable an entity instance."""
    try:
        service = get_instance_service()
        instance = service.set_enabled(instance_id, False, session)
        return {"status": "ok", "instance": instance}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to disable instance: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{instance_id}/items")
async def get_instance_items(
    instance_id: str,
    session: Session = Depends(get_session),
):
    """Get resolved entity items within this instance's boundary."""
    try:
        service = get_instance_service()
        items = service.get_items(instance_id, session)
        return {"status": "ok", **items}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get instance items: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{instance_id}/validate-access")
async def validate_access(
    instance_id: str,
    request: ValidateAccessRequest,
    session: Session = Depends(get_session),
):
    """Check if a specific item ID is within the instance's boundary."""
    try:
        service = get_instance_service()
        result = service.validate_access(instance_id, request.item_id, session)
        return {"status": "ok", **result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to validate access: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{instance_id}/search")
async def search_instance(
    instance_id: str,
    request: SearchInstanceRequest,
    session: Session = Depends(get_session),
):
    """Search within an instance's allowed boundary.

    Delegates to PlatformRegistryService.search() and filters results
    to only items within the instance's allowed_ids.
    """
    try:
        service = get_instance_service()
        result = await service.search_instance(
            instance_id=instance_id,
            session=session,
            query=request.query,
            entity_type=request.entity_type,
            limit=request.limit,
        )
        return {"status": "ok", **result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to search instance: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/seed-defaults")
async def seed_defaults(
    session: Session = Depends(get_session),
):
    """Seed default 'full-access' instances for all entity types."""
    try:
        service = get_instance_service()
        result = service.seed_defaults(session)
        return {"status": "ok", **result}
    except Exception as e:
        logger.error(f"Failed to seed defaults: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
