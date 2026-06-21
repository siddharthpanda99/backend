"""Memory Blueprints API Routes.

Provides REST endpoints for blueprint CRUD and deployment.
Blueprints are configuration snapshots from MemoryCreatorPage.
"""

import json
import logging
from typing import Optional
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlmodel import Session, select

from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.memory.blueprint_models import (
    BlueprintRecord,
    CompositionRecord,
)

router = APIRouter(tags=["memory-blueprints"])

logger = logging.getLogger(__name__)


class BlueprintCreateRequest(BaseModel):
    id: Optional[str] = None
    name: str
    description: str = ""
    entity_type: str = "memory"
    sections: str = "{}"


class BlueprintDeployRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


from common_lib.modules.memory.blueprints_service import blueprints_service

@router.get("/blueprints")
async def list_blueprints(session: Session = Depends(get_session)):
    """List all saved blueprints."""
    try:
        return blueprints_service.list_blueprints(session)
    except Exception as e:
        logger.error(f"Failed to list blueprints: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/blueprints")
async def create_blueprint(
    request: BlueprintCreateRequest, session: Session = Depends(get_session)
):
    """Create a new blueprint from MemoryCreatorPage."""
    try:
        return blueprints_service.create_blueprint(
            session=session,
            name=request.name,
            description=request.description,
            entity_type=request.entity_type,
            sections=request.sections,
            id=request.id,
        )
    except Exception as e:
        logger.error(f"Failed to create blueprint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/blueprints/{blueprint_id}")
async def get_blueprint(blueprint_id: str, session: Session = Depends(get_session)):
    """Get a specific blueprint by ID."""
    try:
        return blueprints_service.get_blueprint(session, blueprint_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get blueprint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/blueprints/{blueprint_id}")
async def delete_blueprint(blueprint_id: str, session: Session = Depends(get_session)):
    """Delete a blueprint."""
    try:
        blueprints_service.delete_blueprint(session, blueprint_id)
        return {"status": "ok", "message": f"Blueprint {blueprint_id} deleted"}
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to delete blueprint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/blueprints/{blueprint_id}/deploy")
async def deploy_blueprint(
    blueprint_id: str,
    request: BlueprintDeployRequest = BlueprintDeployRequest(),
    session: Session = Depends(get_session),
):
    """Deploy a blueprint → auto-create a composition from its enabled sections."""
    try:
        return blueprints_service.deploy_blueprint(
            session=session,
            blueprint_id=blueprint_id,
            name=request.name,
            description=request.description,
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to deploy blueprint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

