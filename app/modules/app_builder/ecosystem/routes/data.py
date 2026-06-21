"""
App Ecosystem — Data Source CRUD Routes

/api/v1/ecosystem/apps/{app_id}/data — list, create, update, delete, connect/disconnect
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.app_builder.ecosystem.schemas import (
    DataSourceCreate, DataSourceUpdate,
    APIResponse,
)
from common_lib.modules.app_builder.ecosystem.service import EcosystemService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/apps/{app_id}/data", tags=["Ecosystem — Data Sources"])
service = EcosystemService()


@router.get("/", response_model=APIResponse)
async def list_data_sources(app_id: str, db: Session = Depends(get_session)):
    """List all data sources for an app."""
    try:
        sources = service.list_data_sources(db, app_id)
        return APIResponse(
            status="success",
            data={"sources": sources},
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/", response_model=APIResponse, status_code=201)
async def create_data_source(app_id: str, data: DataSourceCreate, db: Session = Depends(get_session)):
    """Register a new data source for an app."""
    try:
        record = service.create_data_source(db, app_id, data)
        return APIResponse(
            status="success",
            message="Data source created",
            data=record.model_dump(),
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/{source_id}", response_model=APIResponse)
async def update_data_source(app_id: str, source_id: str, data: DataSourceUpdate, db: Session = Depends(get_session)):
    """Update a data source."""
    try:
        record = service.update_data_source(db, app_id, source_id, data)
        if not record:
            raise HTTPException(status_code=404, detail="Data source not found")
        return APIResponse(status="success", message="Data source updated", data=record.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{source_id}/connect", response_model=APIResponse)
async def connect_data_source(app_id: str, source_id: str, db: Session = Depends(get_session)):
    """Simulate connecting a data source."""
    try:
        record = service.connect_data_source(db, app_id, source_id)
        if not record:
            raise HTTPException(status_code=404, detail="Data source not found")
        return APIResponse(status="success", message="Data source connected", data=record.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{source_id}/disconnect", response_model=APIResponse)
async def disconnect_data_source(app_id: str, source_id: str, db: Session = Depends(get_session)):
    """Simulate disconnecting a data source."""
    try:
        record = service.disconnect_data_source(db, app_id, source_id)
        if not record:
            raise HTTPException(status_code=404, detail="Data source not found")
        return APIResponse(status="success", message="Data source disconnected", data=record.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{source_id}", response_model=APIResponse)
async def delete_data_source(app_id: str, source_id: str, db: Session = Depends(get_session)):
    """Delete a data source."""
    try:
        success = service.delete_data_source(db, app_id, source_id)
        if not success:
            raise HTTPException(status_code=404, detail="Data source not found")
        return APIResponse(status="success", message="Data source deleted")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
