"""
App Ecosystem — Blog Article CRUD Routes

/api/v1/ecosystem/apps/{app_id}/blogs — list, create, update, delete, feature
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.app_builder.ecosystem.schemas import (
    BlogArticleCreate, BlogArticleUpdate,
    PaginatedResponse, APIResponse,
)
from common_lib.modules.app_builder.ecosystem.service import EcosystemService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/apps/{app_id}/blogs", tags=["Ecosystem — Blog Articles"])
service = EcosystemService()


@router.get("/", response_model=PaginatedResponse)
async def list_articles(
    app_id: str,
    category: Optional[str] = Query(None),
    featured_only: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_session),
):
    """List blog articles for an app with optional filters."""
    try:
        records, total = service.list_blog_articles(
            db, app_id, category=category, featured_only=featured_only, page=page, page_size=page_size
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
async def create_article(app_id: str, data: BlogArticleCreate, db: Session = Depends(get_session)):
    """Create a new blog article for an app."""
    try:
        record = service.create_blog_article(db, app_id, data)
        return APIResponse(
            status="success",
            message="Article created",
            data=record.model_dump(),
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/{article_id}", response_model=APIResponse)
async def update_article(app_id: str, article_id: str, data: BlogArticleUpdate, db: Session = Depends(get_session)):
    """Update a blog article."""
    try:
        record = service.update_blog_article(db, app_id, article_id, data)
        if not record:
            raise HTTPException(status_code=404, detail="Article not found")
        return APIResponse(status="success", message="Article updated", data=record.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{article_id}", response_model=APIResponse)
async def delete_article(app_id: str, article_id: str, db: Session = Depends(get_session)):
    """Delete a blog article."""
    try:
        success = service.delete_blog_article(db, app_id, article_id)
        if not success:
            raise HTTPException(status_code=404, detail="Article not found")
        return APIResponse(status="success", message="Article deleted")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
