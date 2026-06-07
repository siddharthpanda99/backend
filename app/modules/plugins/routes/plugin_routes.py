"""CRUD routes for plugin instances and module links.

/api/v1/plugins/instances — manage deployed plugin instances
/api/v1/plugins/links — manage many-to-many links to agents, workflows, etc.
"""

import uuid
import logging
from typing import Optional, List, Any, Dict
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from sqlmodel import select, func

from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.plugins.models import (
    PluginInstanceRecord,
    PluginModuleLinkRecord,
)
from common_lib.modules.plugins.schemas import (
    PluginInstanceCreate,
    PluginInstanceUpdate,
    PluginInstanceResponse,
    PluginModuleLinkCreate,
    PluginModuleLinkUpdate,
    PluginModuleLinkResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/plugins", tags=["Plugins"])


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
        stmt = select(PluginInstanceRecord)

        if plugin_type:
            stmt = stmt.where(PluginInstanceRecord.plugin_type == plugin_type)
        if status:
            stmt = stmt.where(PluginInstanceRecord.status == status)
        if connector_id:
            stmt = stmt.where(PluginInstanceRecord.connector_id == connector_id)
        if search:
            pattern = f"%{search}%"
            stmt = stmt.where(
                PluginInstanceRecord.name.ilike(pattern)
                | PluginInstanceRecord.description.ilike(pattern)
            )

        results = (
            session.execute(
                stmt.order_by(PluginInstanceRecord.name).offset(offset).limit(limit)
            )
            .scalars()
            .all()
        )

        return [PluginInstanceResponse.model_validate(r) for r in results]


@router.get("/instances/{instance_id}", response_model=PluginInstanceResponse)
async def get_plugin_instance(instance_id: str):
    with next(get_session()) as session:
        record = session.get(PluginInstanceRecord, instance_id)
        if not record:
            raise HTTPException(
                status_code=404, detail=f"Plugin instance '{instance_id}' not found"
            )
        return PluginInstanceResponse.model_validate(record)


@router.post("/instances", response_model=PluginInstanceResponse, status_code=201)
async def create_plugin_instance(data: PluginInstanceCreate):
    instance_id = str(uuid.uuid4())
    record = PluginInstanceRecord(
        id=instance_id,
        name=data.name,
        plugin_type=data.plugin_type,
        description=data.description,
        version=data.version or "1.0.0",
        connector_id=data.connector_id,
        connection_id=data.connection_id,
        config_json=data.config_json,
        metadata_json=data.metadata_json,
    )
    with next(get_session()) as session:
        session.add(record)
        session.commit()
        session.refresh(record)
        return PluginInstanceResponse.model_validate(record)


@router.put("/instances/{instance_id}", response_model=PluginInstanceResponse)
async def update_plugin_instance(instance_id: str, data: PluginInstanceUpdate):
    with next(get_session()) as session:
        record = session.get(PluginInstanceRecord, instance_id)
        if not record:
            raise HTTPException(
                status_code=404, detail=f"Plugin instance '{instance_id}' not found"
            )

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(record, field, value)
        record.updated_at = datetime.utcnow()

        session.add(record)
        session.commit()
        session.refresh(record)
        return PluginInstanceResponse.model_validate(record)


@router.delete("/instances/{instance_id}")
async def delete_plugin_instance(instance_id: str):
    with next(get_session()) as session:
        record = session.get(PluginInstanceRecord, instance_id)
        if not record:
            raise HTTPException(
                status_code=404, detail=f"Plugin instance '{instance_id}' not found"
            )

        # Cascade delete all module links
        session.execute(
            select(PluginModuleLinkRecord).where(
                PluginModuleLinkRecord.plugin_instance_id == instance_id
            )
        )
        session.delete(record)
        session.commit()
        return {
            "status": "success",
            "message": f"Plugin instance '{instance_id}' deleted",
        }


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
        stmt = select(PluginModuleLinkRecord)

        if plugin_instance_id:
            stmt = stmt.where(
                PluginModuleLinkRecord.plugin_instance_id == plugin_instance_id
            )
        if module_type:
            stmt = stmt.where(PluginModuleLinkRecord.module_type == module_type)
        if module_id:
            stmt = stmt.where(PluginModuleLinkRecord.module_id == module_id)
        if status:
            stmt = stmt.where(PluginModuleLinkRecord.status == status)

        results = session.execute(stmt.offset(offset).limit(limit)).scalars().all()
        return [PluginModuleLinkResponse.model_validate(r) for r in results]


@router.get("/links/{link_id}", response_model=PluginModuleLinkResponse)
async def get_plugin_link(link_id: str):
    with next(get_session()) as session:
        record = session.get(PluginModuleLinkRecord, link_id)
        if not record:
            raise HTTPException(
                status_code=404, detail=f"Plugin link '{link_id}' not found"
            )
        return PluginModuleLinkResponse.model_validate(record)


@router.post("/links", response_model=PluginModuleLinkResponse, status_code=201)
async def create_plugin_link(data: PluginModuleLinkCreate):
    link_id = str(uuid.uuid4())
    with next(get_session()) as session:
        # Verify plugin instance exists
        instance = session.get(PluginInstanceRecord, data.plugin_instance_id)
        if not instance:
            raise HTTPException(
                status_code=404,
                detail=f"Plugin instance '{data.plugin_instance_id}' not found",
            )

        record = PluginModuleLinkRecord(
            id=link_id,
            plugin_instance_id=data.plugin_instance_id,
            module_type=data.module_type,
            module_id=data.module_id,
            link_config=data.link_config,
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        return PluginModuleLinkResponse.model_validate(record)


@router.put("/links/{link_id}", response_model=PluginModuleLinkResponse)
async def update_plugin_link(link_id: str, data: PluginModuleLinkUpdate):
    with next(get_session()) as session:
        record = session.get(PluginModuleLinkRecord, link_id)
        if not record:
            raise HTTPException(
                status_code=404, detail=f"Plugin link '{link_id}' not found"
            )

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(record, field, value)

        session.add(record)
        session.commit()
        session.refresh(record)
        return PluginModuleLinkResponse.model_validate(record)


@router.delete("/links/{link_id}")
async def delete_plugin_link(link_id: str):
    with next(get_session()) as session:
        record = session.get(PluginModuleLinkRecord, link_id)
        if not record:
            raise HTTPException(
                status_code=404, detail=f"Plugin link '{link_id}' not found"
            )

        session.delete(record)
        session.commit()
        return {
            "status": "success",
            "message": f"Plugin link '{link_id}' deleted",
        }
