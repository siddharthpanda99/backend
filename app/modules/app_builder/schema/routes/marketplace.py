"""
App Ecosystem — Marketplace Routes

/api/v1/marketplace — Browse, search, categories, featured, trending.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.app_builder.schema import (
    SchemaService, AppListingCreate, AppListingUpdate, AppListingResponse,
    AppListingListResponse, AppListingStatsResponse, CategoryCreate,
    CategoryResponse, APIResponse
)
from common_lib.modules.exceptions import NotFoundError, ConflictError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/marketplace", tags=["App Marketplace"])
service = SchemaService()


# ─── Listings CRUD ──────────────────────────────────────────────

@router.get("/apps", response_model=AppListingListResponse)
async def list_marketplace_apps(
    search: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = Query(None, pattern=r"^(draft|published|archived)$"),
    featured: Optional[bool] = None,
    sort: Optional[str] = Query(None, pattern=r"^(newest|popular|rating|installs)$"),
    offset: int = Query(0, ge=0),
    limit: int = Query(24, ge=1, le=100),
    db: Session = Depends(get_session),
):
    items, total = service.list_listings(
        db, category_slug=category, status=status, search=search,
        featured=featured, sort=sort, offset=offset, limit=limit
    )
    return AppListingListResponse(
        items=[AppListingResponse.model_validate(i) for i in items],
        total=total,
    )


@router.get("/apps/{slug}", response_model=AppListingResponse)
async def get_marketplace_app(slug: str, db: Session = Depends(get_session)):
    listing = service.get_listing_by_slug(db, slug, increment_views=True)
    if not listing:
        raise HTTPException(status_code=404, detail="App not found")
    return AppListingResponse.model_validate(listing)


@router.post("/apps", response_model=AppListingResponse, status_code=201)
async def create_marketplace_listing(data: AppListingCreate, db: Session = Depends(get_session)):
    try:
        record = service.create_listing(db, data)
        logger.info(f"Created marketplace listing '{data.name}' ({data.slug})")
        return AppListingResponse.model_validate(record)
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.put("/apps/{listing_id}", response_model=AppListingResponse)
async def update_marketplace_listing(
    listing_id: str, data: AppListingUpdate, db: Session = Depends(get_session)
):
    listing = service.update_listing(db, listing_id, data)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    return AppListingResponse.model_validate(listing)


@router.delete("/apps/{listing_id}", response_model=APIResponse)
async def delete_marketplace_listing(listing_id: str, db: Session = Depends(get_session)):
    success = service.delete_listing(db, listing_id)
    if not success:
        raise HTTPException(status_code=404, detail="Listing not found")
    return APIResponse(message="Listing deleted")


@router.post("/apps/{listing_id}/install", response_model=APIResponse)
async def record_install(listing_id: str, db: Session = Depends(get_session)):
    listing = service.record_install(db, listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    return APIResponse(message=f"Install recorded (total: {listing.install_count})")


@router.get("/apps/{listing_id}/stats", response_model=AppListingStatsResponse)
async def get_app_stats(listing_id: str, db: Session = Depends(get_session)):
    listing = service.get_listing(db, listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    return AppListingStatsResponse(
        installs_today=listing.install_count // 30,
        installs_week=listing.install_count // 4,
        installs_month=listing.install_count,
        views_today=listing.view_count // 30,
        rating_distribution={"1": 0, "2": 0, "3": 0, "4": 0, "5": 0},
        trending_score=listing.install_count * 0.6 + listing.view_count * 0.4,
    )


# ─── Categories CRUD ────────────────────────────────────────────

@router.get("/categories", response_model=list[CategoryResponse])
async def list_categories_route(db: Session = Depends(get_session)):
    cats = service.list_categories(db)
    return [CategoryResponse.model_validate(c) for c in cats]


@router.post("/categories", response_model=CategoryResponse, status_code=201)
async def create_category(data: CategoryCreate, db: Session = Depends(get_session)):
    try:
        record = service.create_category(db, data)
        return CategoryResponse.model_validate(record)
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.put("/categories/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: str, data: CategoryCreate, db: Session = Depends(get_session)
):
    cat = service.update_category(db, category_id, data)
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    return CategoryResponse.model_validate(cat)


@router.delete("/categories/{category_id}", response_model=APIResponse)
async def delete_category(category_id: str, db: Session = Depends(get_session)):
    success = service.delete_category(db, category_id)
    if not success:
        raise HTTPException(status_code=404, detail="Category not found")
    return APIResponse(message="Category deleted")


# ─── Featured / Trending ────────────────────────────────────────

@router.get("/featured", response_model=list[AppListingResponse])
async def get_featured(db: Session = Depends(get_session)):
    items = service.get_featured_listings(db)
    return [AppListingResponse.model_validate(i) for i in items]


@router.get("/trending", response_model=list[AppListingResponse])
async def get_trending(db: Session = Depends(get_session)):
    items = service.get_trending_listings(db)
    return [AppListingResponse.model_validate(i) for i in items]
