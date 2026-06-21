"""
App Ecosystem — Social Post CRUD Routes

/api/v1/ecosystem/apps/{app_id}/social — list, create, like, pin, delete
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.app_builder.ecosystem.schemas import (
    SocialPostCreate, SocialPostUpdate,
    PaginatedResponse, APIResponse,
)
from common_lib.modules.app_builder.ecosystem.service import EcosystemService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/apps/{app_id}/social", tags=["Ecosystem — Social Posts"])
service = EcosystemService()


@router.get("/", response_model=PaginatedResponse)
async def list_posts(
    app_id: str,
    pinned_first: bool = Query(True),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_session),
):
    """List social posts for an app."""
    try:
        records, total = service.list_social_posts(
            db, app_id, pinned_first=pinned_first, page=page, page_size=page_size
        )
        return PaginatedResponse(
            items=records,
            total=total,
            page=page,
            page_size=page_size,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/", response_model=APIResponse, status_code=201)
async def create_post(app_id: str, data: SocialPostCreate, db: Session = Depends(get_session)):
    """Create a new social post for an app."""
    try:
        record = service.create_social_post(db, app_id, data)
        return APIResponse(
            status="success",
            message="Post created",
            data=record.model_dump(),
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{post_id}/like", response_model=APIResponse)
async def like_post(app_id: str, post_id: str, db: Session = Depends(get_session)):
    """Increment the like count on a post."""
    try:
        likes = service.like_social_post(db, app_id, post_id)
        if likes is None:
            raise HTTPException(status_code=404, detail="Post not found")
        return APIResponse(status="success", data={"likes": likes}, message="Post liked")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/{post_id}", response_model=APIResponse)
async def update_post(app_id: str, post_id: str, data: SocialPostUpdate, db: Session = Depends(get_session)):
    """Update a post (content, tags, pinned status)."""
    try:
        record = service.update_social_post(db, app_id, post_id, data)
        if not record:
            raise HTTPException(status_code=404, detail="Post not found")
        return APIResponse(status="success", message="Post updated", data=record.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{post_id}", response_model=APIResponse)
async def delete_post(app_id: str, post_id: str, db: Session = Depends(get_session)):
    """Delete a social post."""
    try:
        success = service.delete_social_post(db, app_id, post_id)
        if not success:
            raise HTTPException(status_code=404, detail="Post not found")
        return APIResponse(status="success", message="Post deleted")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
