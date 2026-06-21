"""
App Ecosystem — Review CRUD Routes

/api/v1/ecosystem/apps/{app_id}/reviews — list, create, update, delete, mark helpful
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.app_builder.ecosystem.schemas import (
    ReviewCreate, ReviewUpdate, ReviewSchema,
    PaginatedResponse, APIResponse,
)
from common_lib.modules.app_builder.ecosystem.service import EcosystemService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/apps/{app_id}/reviews", tags=["Ecosystem — Reviews"])
service = EcosystemService()


@router.get("/", response_model=PaginatedResponse)
async def list_reviews(
    app_id: str,
    min_rating: Optional[int] = Query(None, ge=1, le=5),
    sort_by: str = Query("recent", pattern="^(recent|rating|helpful)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_session),
):
    """List reviews for an app with sorting and rating filter."""
    try:
        records, total = service.list_reviews(
            db, app_id, min_rating=min_rating, sort_by=sort_by, page=page, page_size=page_size
        )
        return PaginatedResponse(
            items=records,
            total=total,
            page=page,
            page_size=page_size,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/stats", response_model=APIResponse)
async def get_review_stats(app_id: str, db: Session = Depends(get_session)):
    """Get aggregated review statistics for an app."""
    try:
        stats = service.get_review_stats(db, app_id)
        return APIResponse(status="success", data=stats)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/", response_model=APIResponse, status_code=201)
async def create_review(app_id: str, data: ReviewCreate, db: Session = Depends(get_session)):
    """Submit a new review for an app."""
    try:
        record = service.create_review(db, app_id, data)
        return APIResponse(
            status="success",
            message="Review submitted",
            data=record.model_dump(),
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{review_id}/helpful", response_model=APIResponse)
async def mark_helpful(app_id: str, review_id: str, db: Session = Depends(get_session)):
    """Mark a review as helpful."""
    try:
        helpful = service.mark_review_helpful(db, app_id, review_id)
        if helpful is None:
            raise HTTPException(status_code=404, detail="Review not found")
        return APIResponse(status="success", data={"helpful": helpful}, message="Marked as helpful")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{review_id}", response_model=APIResponse)
async def delete_review(app_id: str, review_id: str, db: Session = Depends(get_session)):
    """Delete a review."""
    try:
        success = service.delete_review(db, app_id, review_id)
        if not success:
            raise HTTPException(status_code=404, detail="Review not found")
        return APIResponse(status="success", message="Review deleted")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
