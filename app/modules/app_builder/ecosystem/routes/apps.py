"""
App Ecosystem — App CRUD Routes

/api/v1/ecosystem/apps — list, create, get, update, delete apps
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.app_builder.ecosystem.schemas import (
    AppInfoCreate, AppInfoUpdate, AppInfoSchema,
    AppListResponse, APIResponse,
)
from common_lib.modules.app_builder.ecosystem.service import EcosystemService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/apps", tags=["Ecosystem — Apps"])
service = EcosystemService()


@router.get("/", response_model=AppListResponse)
async def list_apps(
    category: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_session),
):
    """List all registered ecosystem apps with optional filters."""
    apps, total, active, draft = service.list_apps(
        db, category=category, status=status, search=search, page=page, page_size=page_size
    )
    return AppListResponse(
        apps=apps,
        total=total,
        active=active,
        draft=draft,
    )


@router.get("/{app_id}", response_model=AppInfoSchema)
async def get_app(app_id: str, db: Session = Depends(get_session)):
    """Get a single app by ID."""
    app = service.get_app(db, app_id)
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found")
    return app


@router.post("/", response_model=APIResponse, status_code=201)
async def create_app(data: AppInfoCreate, db: Session = Depends(get_session)):
    """Register a new app in the ecosystem."""
    try:
        app = service.create_app(db, data)
        return APIResponse(
            status="success",
            message=f"App '{app.name}' created",
            data=app.model_dump(),
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.put("/{app_id}", response_model=APIResponse)
async def update_app(app_id: str, data: AppInfoUpdate, db: Session = Depends(get_session)):
    """Update an existing app's metadata or stats."""
    app = service.update_app(db, app_id, data)
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found")
    return APIResponse(
        status="success",
        message=f"App '{app.name}' updated",
        data=app.model_dump(),
    )


@router.delete("/{app_id}", response_model=APIResponse)
async def delete_app(app_id: str, db: Session = Depends(get_session)):
    """Delete an app and all its ecosystem data."""
    success = service.delete_app(db, app_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found")
    return APIResponse(status="success", message=f"App '{app_id}' deleted")
