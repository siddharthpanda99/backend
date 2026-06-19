"""CRUD routes for plugin instances and module links.

Thin wrappers delegating to PluginInstanceService in common_lib.
"""

import logging
from typing import Optional, List, Any, Dict

from fastapi import APIRouter, HTTPException, Query

from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.data_storage.database.repository import NotFoundError
from common_lib.modules.plugins.schemas import (
    PluginInstanceCreate,
    PluginInstanceUpdate,
    PluginInstanceResponse,
    PluginModuleLinkCreate,
    PluginModuleLinkUpdate,
    PluginModuleLinkResponse,
)
from common_lib.modules.plugins.services.plugin_service import PluginInstanceService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/plugins", tags=["Plugins"])
_svc = PluginInstanceService()


# =============================================================================
# Plugin Instances CRUD
# =============================================================================


@router.get("/instances", response_model=List[PluginInstanceResponse])
async def list_plugin_instances(
    plugin_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    connector_id: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    with next(get_session()) as session:
        results = _svc.list_instances(
            session,
            plugin_type=plugin_type,
            status=status,
            connector_id=connector_id,
            search=search,
            offset=offset,
            limit=limit,
        )
        return [PluginInstanceResponse.model_validate(r) for r in results]


@router.get("/instances/{instance_id}", response_model=PluginInstanceResponse)
async def get_plugin_instance(instance_id: str):
    with next(get_session()) as session:
        try:
            record = _svc.get_instance(session, instance_id)
            return PluginInstanceResponse.model_validate(record)
        except NotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))


@router.post("/instances", response_model=PluginInstanceResponse, status_code=201)
async def create_plugin_instance(data: PluginInstanceCreate):
    with next(get_session()) as session:
        record = _svc.create_instance(session, data)
        return PluginInstanceResponse.model_validate(record)


@router.put("/instances/{instance_id}", response_model=PluginInstanceResponse)
async def update_plugin_instance(instance_id: str, data: PluginInstanceUpdate):
    with next(get_session()) as session:
        try:
            record = _svc.update_instance(session, instance_id, data)
            return PluginInstanceResponse.model_validate(record)
        except NotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))


@router.delete("/instances/{instance_id}")
async def delete_plugin_instance(instance_id: str):
    with next(get_session()) as session:
        try:
            _svc.delete_instance(session, instance_id)
            return {
                "status": "success",
                "message": f"Plugin instance '{instance_id}' deleted",
            }
        except NotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))


# =============================================================================
# Plugin Module Links CRUD (many-to-many linker)
# =============================================================================


@router.get("/links", response_model=List[PluginModuleLinkResponse])
async def list_plugin_links(
    plugin_instance_id: Optional[str] = Query(None),
    module_type: Optional[str] = Query(None),
    module_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    with next(get_session()) as session:
        results = _svc.list_links(
            session,
            plugin_instance_id=plugin_instance_id,
            module_type=module_type,
            module_id=module_id,
            status=status,
            offset=offset,
            limit=limit,
        )
        return [PluginModuleLinkResponse.model_validate(r) for r in results]


@router.get("/links/{link_id}", response_model=PluginModuleLinkResponse)
async def get_plugin_link(link_id: str):
    with next(get_session()) as session:
        try:
            record = _svc.get_link(session, link_id)
            return PluginModuleLinkResponse.model_validate(record)
        except NotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))


@router.post("/links", response_model=PluginModuleLinkResponse, status_code=201)
async def create_plugin_link(data: PluginModuleLinkCreate):
    with next(get_session()) as session:
        try:
            record = _svc.create_link(session, data)
            return PluginModuleLinkResponse.model_validate(record)
        except NotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))


@router.put("/links/{link_id}", response_model=PluginModuleLinkResponse)
async def update_plugin_link(link_id: str, data: PluginModuleLinkUpdate):
    with next(get_session()) as session:
        try:
            record = _svc.update_link(session, link_id, data)
            return PluginModuleLinkResponse.model_validate(record)
        except NotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))


@router.delete("/links/{link_id}")
async def delete_plugin_link(link_id: str):
    with next(get_session()) as session:
        try:
            _svc.delete_link(session, link_id)
            return {"status": "success", "message": f"Plugin link '{link_id}' deleted"}
        except NotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))
