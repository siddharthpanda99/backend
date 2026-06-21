"""
Feature Picker — App-Feature Assignment CRUD

Endpoints:
  GET    /app/{app_id}                  — List assigned features for an app
  POST   /app/{app_id}                  — Assign a feature to an app
  PUT    /app/{app_id}/{feature_id}     — Update an assignment
  DELETE /app/{app_id}/{feature_id}     — Remove an assignment
  POST   /app/{app_id}/bulk             — Bulk assign features to an app
"""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.app_builder.features.schemas import (
    AppFeatureAssignmentCreate,
    AppFeatureAssignmentUpdate,
    AppFeatureAssignmentResponse,
    AppFeatureAssignmentListResponse,
    APIResponse,
)
from common_lib.modules.app_builder.features.service import FeatureService
from common_lib.modules.exceptions import BadRequestError, ConflictError

logger = logging.getLogger(__name__)
router = APIRouter()
service = FeatureService()


@router.get("/app/{app_id}", response_model=AppFeatureAssignmentListResponse)
async def list_app_features(app_id: str, db: Session = Depends(get_session)):
    """List all features assigned to a specific app."""
    items, total = service.list_app_features(db, app_id)
    return AppFeatureAssignmentListResponse(items=items, total=total)


@router.post("/app/{app_id}", response_model=AppFeatureAssignmentResponse, status_code=201)
async def assign_feature(app_id: str, data: AppFeatureAssignmentCreate, db: Session = Depends(get_session)):
    """Assign a feature to an app."""
    try:
        record = service.assign_feature(db, app_id, data)
        logger.info("Assigned feature %s:%s to app %s", data.feature_source, data.feature_id, app_id)
        return record
    except BadRequestError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.put("/app/{app_id}/{assignment_id}", response_model=AppFeatureAssignmentResponse)
async def update_assignment(app_id: str, assignment_id: str, data: AppFeatureAssignmentUpdate, db: Session = Depends(get_session)):
    """Update a feature assignment (toggle enabled, reorder, override config)."""
    record = service.update_assignment(db, app_id, assignment_id, data)
    if not record:
        raise HTTPException(status_code=404, detail=f"Assignment '{assignment_id}' not found for app '{app_id}'")
    return record


@router.delete("/app/{app_id}/{assignment_id}", response_model=APIResponse)
async def remove_assignment(app_id: str, assignment_id: str, db: Session = Depends(get_session)):
    """Remove a feature assignment from an app."""
    success = service.remove_assignment(db, app_id, assignment_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Assignment '{assignment_id}' not found for app '{app_id}'")
    logger.info("Removed feature assignment %s from app %s", assignment_id, app_id)
    return APIResponse(success=True, data={"id": assignment_id}, message="Feature assignment removed")


@router.post("/app/{app_id}/bulk", response_model=AppFeatureAssignmentListResponse, status_code=201)
async def bulk_assign_features(app_id: str, data: List[AppFeatureAssignmentCreate], db: Session = Depends(get_session)):
    """
    Bulk assign features to an app.
    Replaces all existing assignments for the app with the provided list.
    """
    items, total = service.bulk_assign_features(db, app_id, data)
    logger.info("Bulk assigned %d features to app %s", len(items), app_id)
    return AppFeatureAssignmentListResponse(items=items, total=total)
