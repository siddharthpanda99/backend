"""Module 25 — Search, Catalog & Data Discovery REST routes.

Thin FastAPI wrappers — all logic delegated to DiscoveryService.
"""
from typing import Optional, Any

from fastapi import APIRouter, HTTPException, Query

from common_lib.modules.db_studio.discovery.schemas import (
    CatalogAssetCreate,
    CatalogAssetOut,
    CatalogAssetUpdate,
    DiscoveryDashboardOut,
    GlossaryTermCreate,
    GlossaryTermOut,
    GlossaryTermUpdate,
    RecommendationOut,
    RelationshipCreate,
    RelationshipOut,
    SearchRequest,
    SearchResponse,
    SearchSuggestionOut,
    TagCreate,
    TagOut,
    TagSummary,
)
from common_lib.modules.db_studio.discovery.service import DiscoveryService

router = APIRouter(prefix="/api/v1", tags=["Discovery"])
svc = DiscoveryService()


# ------------------------------------------------------------------ #
# Search
# ------------------------------------------------------------------ #

@router.post("/search", response_model=SearchResponse)
def search(body: SearchRequest):
    return svc.search(body)


@router.get("/search/suggestions", response_model=list[SearchSuggestionOut])
def search_suggestions(prefix: str = Query(..., max_length=256), limit: int = Query(10, ge=1, le=50)):
    return svc.get_suggestions(prefix, limit)


@router.get("/search/recent", response_model=list[str])
def recent_searches(user_id: str = "anonymous", limit: int = Query(20, ge=1, le=100)):
    return svc.get_recent_searches(user_id, limit)


@router.post("/search/save")
def save_search(name: str = Query(..., max_length=128), query: str = Query(..., max_length=1024)):
    return svc.save_search(name, query)


@router.get("/search/saved")
def list_saved_searches(limit: int = Query(50, ge=1, le=200)):
    return svc.list_saved_searches(limit)


@router.delete("/search/saved/{search_id}")
def delete_saved_search(search_id: str):
    ok = svc.delete_saved_search(search_id)
    if not ok:
        raise HTTPException(404, "Saved search not found")
    return {"ok": True}


# ------------------------------------------------------------------ #
# Index
# ------------------------------------------------------------------ #

@router.post("/index", response_model=SearchResponse)
def index_asset(body: dict):
    from common_lib.modules.db_studio.discovery.schemas import IndexRequest
    req = IndexRequest(**body)
    result = svc.index_asset(req)
    return SearchResponse(results=[result], total=1, limit=1, offset=0)


# ------------------------------------------------------------------ #
# Catalog
# ------------------------------------------------------------------ #

@router.post("/catalog", response_model=CatalogAssetOut, status_code=201)
def create_catalog_asset(body: CatalogAssetCreate):
    return svc.create_catalog_asset(body)


@router.get("/catalog/{asset_id}", response_model=CatalogAssetOut)
def get_catalog_asset(asset_id: str):
    result = svc.get_catalog_asset(asset_id)
    if not result:
        raise HTTPException(404, "Catalog asset not found")
    return result


@router.patch("/catalog/{asset_id}", response_model=CatalogAssetOut)
def update_catalog_asset(asset_id: str, body: CatalogAssetUpdate):
    result = svc.update_catalog_asset(asset_id, body)
    if not result:
        raise HTTPException(404, "Catalog asset not found")
    return result


@router.delete("/catalog/{asset_id}")
def delete_catalog_asset(asset_id: str):
    ok = svc.delete_catalog_asset(asset_id)
    if not ok:
        raise HTTPException(404, "Catalog asset not found")
    return {"ok": True}


@router.get("/catalog", response_model=dict)
def list_catalog_assets(
    asset_type: Optional[str] = None,
    classification: Optional[str] = None,
    lifecycle_state: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    items, total = svc.list_catalog_assets(
        asset_type=asset_type,
        classification=classification,
        lifecycle_state=lifecycle_state,
        limit=limit,
        offset=offset,
    )
    return {"items": items, "total": total, "limit": limit, "offset": offset}


# ------------------------------------------------------------------ #
# Glossary
# ------------------------------------------------------------------ #

@router.post("/glossary", response_model=GlossaryTermOut, status_code=201)
def create_glossary_term(body: GlossaryTermCreate):
    return svc.create_glossary_term(body)


@router.get("/glossary/{term_id}", response_model=GlossaryTermOut)
def get_glossary_term(term_id: str):
    result = svc.get_glossary_term(term_id)
    if not result:
        raise HTTPException(404, "Glossary term not found")
    return result


@router.patch("/glossary/{term_id}", response_model=GlossaryTermOut)
def update_glossary_term(term_id: str, body: GlossaryTermUpdate):
    result = svc.update_glossary_term(term_id, body)
    if not result:
        raise HTTPException(404, "Glossary term not found")
    return result


@router.delete("/glossary/{term_id}")
def delete_glossary_term(term_id: str):
    ok = svc.delete_glossary_term(term_id)
    if not ok:
        raise HTTPException(404, "Glossary term not found")
    return {"ok": True}


@router.get("/glossary", response_model=dict)
def list_glossary_terms(
    domain: Optional[str] = None,
    approval_status: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    items, total = svc.list_glossary_terms(
        domain=domain,
        approval_status=approval_status,
        limit=limit,
        offset=offset,
    )
    return {"items": items, "total": total, "limit": limit, "offset": offset}


# ------------------------------------------------------------------ #
# Tags
# ------------------------------------------------------------------ #

@router.post("/tags", response_model=TagOut, status_code=201)
def add_tag(body: TagCreate):
    return svc.add_tag(body)


@router.delete("/tags/{tag_name}/{asset_type}/{asset_id}")
def remove_tag(tag_name: str, asset_type: str, asset_id: str):
    ok = svc.remove_tag(tag_name, asset_type, asset_id)
    if not ok:
        raise HTTPException(404, "Tag not found")
    return {"ok": True}


@router.get("/tags/{asset_type}/{asset_id}", response_model=list[TagOut])
def get_tags_for_asset(asset_type: str, asset_id: str):
    return svc.get_tags_for_asset(asset_type, asset_id)


@router.get("/tags/popular", response_model=list[TagSummary])
def popular_tags(limit: int = Query(20, ge=1, le=100)):
    return svc.get_popular_tags(limit)


# ------------------------------------------------------------------ #
# Relationships
# ------------------------------------------------------------------ #

@router.post("/relationships", response_model=RelationshipOut, status_code=201)
def create_relationship(body: RelationshipCreate):
    return svc.create_relationship(body)


@router.get("/relationships/{asset_type}/{asset_id}", response_model=list)
def get_relationships(asset_type: str, asset_id: str):
    return svc.get_relationships(asset_type, asset_id)


@router.delete("/relationships/{rel_id}")
def delete_relationship(rel_id: str):
    ok = svc.delete_relationship(rel_id)
    if not ok:
        raise HTTPException(404, "Relationship not found")
    return {"ok": True}


# ------------------------------------------------------------------ #
# Recommendations
# ------------------------------------------------------------------ #

@router.post("/recommendations/generate", response_model=list[RecommendationOut])
def generate_recommendations(user_id: str, limit: int = Query(5, ge=1, le=50)):
    return svc.generate_recommendations(user_id, limit)


@router.patch("/recommendations/{rec_id}/viewed")
def mark_recommendation_viewed(rec_id: str):
    ok = svc.mark_recommendation_viewed(rec_id)
    if not ok:
        raise HTTPException(404, "Recommendation not found")
    return {"ok": True}


@router.get("/recommendations/{user_id}", response_model=list[RecommendationOut])
def list_recommendations(user_id: str, limit: int = Query(20, ge=1, le=100)):
    return svc.list_recommendations(user_id, limit)


# ------------------------------------------------------------------ #
# Dashboard
# ------------------------------------------------------------------ #

@router.get("/discovery/dashboard", response_model=DiscoveryDashboardOut)
def discovery_dashboard():
    return svc.get_dashboard()


# ------------------------------------------------------------------ #
# Seed
# ------------------------------------------------------------------ #

@router.post("/discovery/seed")
def seed_discovery():
    count = svc.seed_defaults()
    return {"seeded": count}
