"""CRUD routes for connector definitions.

/api/v1/connectors/ — manage connector blueprints (GitHub, Jira, etc.)
All logic delegated to common_lib.modules.connectors.service.ConnectorService.
"""

import logging
from typing import Optional, List, Any, Dict

from fastapi import APIRouter, Query

from common_lib.modules.plugins.connectors.schemas import (
    ConnectorCreate,
    ConnectorUpdate,
    ConnectorResponse,
    ConnectorListResponse,
)
from common_lib.modules.plugins.connectors.service import ConnectorService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/connectors", tags=["Connectors"])


@router.get("/", response_model=ConnectorListResponse)
async def list_connectors(
    search: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    return ConnectorService.list_connectors(
        search=search, category=category, status=status, tag=tag,
        offset=offset, limit=limit,
    )


@router.get("/{connector_id}", response_model=ConnectorResponse)
async def get_connector(connector_id: str):
    return ConnectorService.get_connector(connector_id)


@router.post("/", response_model=ConnectorResponse, status_code=201)
async def create_connector(data: ConnectorCreate):
    return ConnectorService.create_connector(data)


@router.put("/{connector_id}", response_model=ConnectorResponse)
async def update_connector(connector_id: str, data: ConnectorUpdate):
    return ConnectorService.update_connector(connector_id, data)


@router.delete("/{connector_id}")
async def delete_connector(connector_id: str):
    return ConnectorService.delete_connector(connector_id)


@router.get("/{connector_id}/tools", response_model=List[Dict[str, Any]])
async def list_connector_tools(connector_id: str):
    return ConnectorService.list_connector_tools(connector_id)


@router.post("/{connector_id}/sync-registry")
async def sync_connector_to_registry(connector_id: str):
    return ConnectorService.sync_connector_to_registry(connector_id)
