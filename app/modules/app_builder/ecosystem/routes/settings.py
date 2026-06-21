"""
App Ecosystem — App Settings Routes

/api/v1/ecosystem/apps/{app_id}/settings — get and update app settings
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.app_builder.ecosystem.schemas import (
    AppSettingsUpdate, APIResponse,
)
from common_lib.modules.app_builder.ecosystem.service import EcosystemService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/apps/{app_id}/settings", tags=["Ecosystem — App Settings"])
service = EcosystemService()


@router.get("/", response_model=APIResponse)
async def get_app_settings(app_id: str, db: Session = Depends(get_session)):
    """Get settings for an app. Creates default settings if none exist."""
    try:
        settings = service.get_app_settings(db, app_id)
        return APIResponse(
            status="success",
            data=settings.model_dump(),
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/", response_model=APIResponse)
async def update_app_settings(app_id: str, data: AppSettingsUpdate, db: Session = Depends(get_session)):
    """Update settings for an app."""
    try:
        settings = service.update_app_settings(db, app_id, data)
        return APIResponse(
            status="success",
            message="Settings updated",
            data=settings.model_dump(),
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
