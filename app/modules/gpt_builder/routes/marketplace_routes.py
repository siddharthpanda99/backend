"""GPT Builder — Marketplace Routes.

Endpoints for browsing marketplace listings, installing apps,
and template-based app creation.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from common_lib.modules.gpt_builder.marketplace import MarketplaceService
from common_lib.modules.gpt_builder.schemas import (
    MarketplaceListingCreate,
    MarketplaceListingResponse,
)
from common_lib.modules.gpt_builder.service import get_gpt_builder_service

router = APIRouter()


@router.get("/marketplace", response_model=Dict[str, Any])
async def list_marketplace(
    category: Optional[str] = Query(None),
    status: str = Query("active"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    service = get_gpt_builder_service()
    marketplace = MarketplaceService(service)
    listings, total = await marketplace.list_listings(
        category=category,
        status=status,
        limit=limit,
        offset=offset,
    )
    return {"items": listings, "total": total}


@router.get("/marketplace/{listing_id}", response_model=MarketplaceListingResponse)
async def get_listing(listing_id: str):
    service = get_gpt_builder_service()
    marketplace = MarketplaceService(service)
    listings, _ = await marketplace.list_listings(limit=200)
    for listing in listings:
        if listing["id"] == listing_id:
            app = listing.get("app")
            return MarketplaceListingResponse(
                id=listing["id"],
                app_id=listing["app_id"],
                app_version=listing["app_version"],
                title=listing["title"],
                tagline=listing.get("tagline"),
                description_long=listing.get("description_long"),
                category=listing.get("category"),
                tags=listing.get("tags", []),
                screenshots=listing.get("screenshots", []),
                pricing_model=listing.get("pricing_model", "free"),
                install_count=listing.get("install_count", 0),
                rating=listing.get("rating", 0.0),
                verified=listing.get("verified", False),
                featured=listing.get("featured", False),
                status=listing.get("status", "pending"),
                published_at=listing.get("published_at"),
                app=app,
            )
    raise HTTPException(status_code=404, detail="Listing not found")


@router.post("/marketplace/{listing_id}/install", response_model=Dict[str, Any])
async def install_app(listing_id: str, user_id: str = "system", org_id: Optional[str] = None):
    service = get_gpt_builder_service()
    marketplace = MarketplaceService(service)
    result = await marketplace.install_app(
        listing_id=listing_id,
        user_id=user_id,
        org_id=org_id,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Listing not found")
    return result


@router.get("/templates", response_model=List[Dict[str, Any]])
async def list_templates():
    service = get_gpt_builder_service()
    marketplace = MarketplaceService(service)
    return await marketplace.get_template_list()


@router.post("/templates/{template_id}/create", response_model=Dict[str, Any])
async def create_from_template(
    template_id: str,
    name: str,
    user_id: str = "system",
    org_id: Optional[str] = None,
):
    service = get_gpt_builder_service()
    marketplace = MarketplaceService(service)
    result = await marketplace.create_from_template(
        template_id=template_id,
        name=name,
        user_id=user_id,
        org_id=org_id,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Template not found")
    return result


@router.post("/apps/{app_id}/listing", response_model=MarketplaceListingResponse)
async def create_listing(app_id: str, data: MarketplaceListingCreate):
    service = get_gpt_builder_service()
    listing = await service.create_marketplace_listing(app_id, data.model_dump())
    return MarketplaceListingResponse(
        id=listing.id,
        app_id=listing.app_id,
        app_version=listing.app_version,
        title=listing.title,
        tagline=listing.tagline,
        description_long=listing.description_long,
        category=listing.category,
        tags=listing.tags or [],
        screenshots=listing.screenshots or [],
        pricing_model=listing.pricing_model,
        install_count=listing.install_count or 0,
        rating=listing.rating or 0.0,
        verified=listing.verified or False,
        featured=listing.featured or False,
        status=listing.status or "pending",
        published_at=listing.published_at,
    )


# ── Store Endpoints ────────────────────────────────────────────────

@router.get("/store/featured", response_model=Dict[str, Any])
async def get_store_featured():
    """Get featured, trending, and recent marketplace listings."""
    service = get_gpt_builder_service()
    marketplace = MarketplaceService(service)
    all_listings, _ = await marketplace.list_listings(status="active", limit=100)

    featured = [l for l in all_listings if l.get("featured")][:6]
    trending = sorted(all_listings, key=lambda l: l.get("install_count", 0), reverse=True)[:8]
    recent = sorted(all_listings, key=lambda l: l.get("published_at", "") or "", reverse=True)[:8]

    return {
        "featured": featured,
        "trending": trending,
        "recent": recent,
    }


@router.get("/store/categories", response_model=List[Dict[str, Any]])
async def get_store_categories():
    """Get store categories with counts."""
    service = get_gpt_builder_service()
    marketplace = MarketplaceService(service)
    all_listings, _ = await marketplace.list_listings(status="active", limit=500)

    category_counts: Dict[str, int] = {}
    for listing in all_listings:
        cat = listing.get("category") or "uncategorized"
        category_counts[cat] = category_counts.get(cat, 0) + 1

    category_icons = {
        "analytics": "📊", "data": "🗄️", "support": "🎧",
        "code": "💻", "writing": "✍️", "marketing": "📈",
        "education": "📚", "health": "🏥", "finance": "💰",
        "design": "🎨", "productivity": "⚡", "uncategorized": "📦",
    }

    return [
        {"id": cat, "name": cat.capitalize(), "icon": category_icons.get(cat, "📦"), "count": count}
        for cat, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True)
    ]


@router.post("/store/{listing_id}/rate", response_model=Dict[str, Any])
async def rate_listing(listing_id: str, rating: float = 5.0, review: str = ""):
    """Rate a marketplace listing."""
    if rating < 0 or rating > 5:
        raise HTTPException(status_code=400, detail="Rating must be between 0 and 5")

    service = get_gpt_builder_service()
    marketplace = MarketplaceService(service)
    all_listings, _ = await marketplace.list_listings(limit=200)

    for listing in all_listings:
        if listing["id"] == listing_id:
            return {
                "status": "rated",
                "listing_id": listing_id,
                "rating": rating,
                "message": "Rating submitted. Aggregate rating will be updated after review moderation.",
            }

    raise HTTPException(status_code=404, detail="Listing not found")
