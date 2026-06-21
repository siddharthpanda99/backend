"""
Feature Picker — Feature Definition CRUD

Endpoints:
  GET    /                — List custom feature definitions (search, pagination)
  GET    /{id}            — Get single feature definition
  POST   /                — Create a new custom feature definition
  PUT    /{id}            — Update a feature definition
  DELETE /{id}            — Delete a feature definition
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.app_builder.features.schemas import (
    FeatureDefinitionCreate,
    FeatureDefinitionUpdate,
    FeatureDefinitionResponse,
    FeatureDefinitionListResponse,
    APIResponse,
)
from common_lib.modules.app_builder.features.service import FeatureService

logger = logging.getLogger(__name__)
router = APIRouter()
service = FeatureService()


@router.get("/", response_model=FeatureDefinitionListResponse)
async def list_features(
    search: Optional[str] = Query(None, max_length=256),
    category: Optional[str] = Query(None, max_length=64),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_session),
):
    """
    List all custom feature definitions.
    Supports search by name/description, filter by category, and pagination.
    """
    items, total = service.list_features(db, search=search, category=category, offset=offset, limit=limit)
    return FeatureDefinitionListResponse(items=items, total=total)


@router.get("/{id}", response_model=FeatureDefinitionResponse)
async def get_feature(id: str, db: Session = Depends(get_session)):
    """Get a single custom feature definition by ID."""
    record = service.get_feature(db, id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Feature '{id}' not found")
    return record


@router.post("/", response_model=FeatureDefinitionResponse, status_code=201)
async def create_feature(data: FeatureDefinitionCreate, db: Session = Depends(get_session)):
    """Create a new custom feature definition."""
    record = service.create_feature(db, data)
    logger.info("Created feature definition: %s (%s)", record.name, record.id)
    return record


@router.put("/{id}", response_model=FeatureDefinitionResponse)
async def update_feature(id: str, data: FeatureDefinitionUpdate, db: Session = Depends(get_session)):
    """Update an existing feature definition (partial update)."""
    record = service.update_feature(db, id, data)
    if not record:
        raise HTTPException(status_code=404, detail=f"Feature '{id}' not found")
    logger.info("Updated feature definition: %s (%s)", record.name, record.id)
    return record


@router.delete("/{id}", response_model=APIResponse)
async def delete_feature(id: str, db: Session = Depends(get_session)):
    """Delete a custom feature definition."""
    record = service.delete_feature(db, id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Feature '{id}' not found")
    logger.info("Deleted feature definition: %s (%s)", record.name, id)
    return APIResponse(success=True, data={"id": id}, message=f"Feature '{record.name}' deleted")
