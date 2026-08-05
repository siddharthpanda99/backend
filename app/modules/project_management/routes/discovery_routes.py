"""Product Discovery, Ideas, Feedback & Roadmap REST Routes — Domain 11."""
import logging
from typing import Optional
from fastapi import APIRouter, Query, HTTPException

from app.modules.auth.dependencies import require_permission
from common_lib.modules.project_management.schemas import (
    ProductIdeaCreate, ProductIdeaUpdate,
    FeatureRequestCreate, FeatureRequestUpdate,
    CustomerFeedbackCreate,
    RoadmapItemCreate, RoadmapItemUpdate,
    PrioritizationScoreCreate, MarketResearchCreate,
)
from common_lib.modules.project_management.discovery.service import DiscoveryService

logger = logging.getLogger(__name__)
router = APIRouter()


# --- Product Ideas ---
@router.post("/ideas", tags=["PM Discovery"])
async def create_idea(data: ProductIdeaCreate, _perm: None = require_permission("idea.create", "*", "idea")):
    return DiscoveryService.create_idea(data)


@router.get("/ideas/{idea_id}", tags=["PM Discovery"])
async def get_idea(idea_id: str, _perm: None = require_permission("idea.read", "*", "idea")):
    idea = DiscoveryService.get_idea(idea_id)
    if not idea:
        raise HTTPException(status_code=404, detail="Idea not found")
    return idea


@router.get("/ideas", tags=["PM Discovery"])
async def list_ideas(_perm: None = require_permission("idea.read", "*", "idea"),
    status: Optional[str] = None,
    priority: Optional[str] = None,
    tags: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return DiscoveryService.list_ideas(status=status, priority=priority, tags=tags, limit=limit, offset=offset)


@router.patch("/ideas/{idea_id}", tags=["PM Discovery"])
async def update_idea(idea_id: str, data: ProductIdeaUpdate, _perm: None = require_permission("idea.update", "*", "idea")):
    idea = DiscoveryService.update_idea(idea_id, data)
    if not idea:
        raise HTTPException(status_code=404, detail="Idea not found")
    return idea


@router.delete("/ideas/{idea_id}", tags=["PM Discovery"])
async def delete_idea(idea_id: str, _perm: None = require_permission("idea.delete", "*", "idea")):
    if not DiscoveryService.delete_idea(idea_id):
        raise HTTPException(status_code=404, detail="Idea not found")
    return {"ok": True}


@router.post("/ideas/{idea_id}/vote", tags=["PM Discovery"])
async def vote_idea(idea_id: str, _perm: None = require_permission("idea.update", "*", "idea")):
    idea = DiscoveryService.vote_idea(idea_id)
    if not idea:
        raise HTTPException(status_code=404, detail="Idea not found")
    return idea


# --- Feature Requests ---
@router.post("/feature-requests", tags=["PM Discovery"])
async def create_feature_request(data: FeatureRequestCreate, _perm: None = require_permission("feature_request.create", "*", "feature_request")):
    return DiscoveryService.create_feature_request(data)


@router.get("/feature-requests", tags=["PM Discovery"])
async def list_feature_requests(_perm: None = require_permission("feature_request.read", "*", "feature_request"),
    status: Optional[str] = None,
    source: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return DiscoveryService.list_feature_requests(status=status, source=source, limit=limit, offset=offset)


@router.patch("/feature-requests/{fr_id}", tags=["PM Discovery"])
async def update_feature_request(fr_id: str, data: FeatureRequestUpdate, _perm: None = require_permission("feature_request.update", "*", "feature_request")):
    fr = DiscoveryService.update_feature_request(fr_id, data)
    if not fr:
        raise HTTPException(status_code=404, detail="Feature request not found")
    return fr


# --- Customer Feedback ---
@router.post("/feedback", tags=["PM Discovery"])
async def create_feedback(data: CustomerFeedbackCreate, _perm: None = require_permission("feedback.create", "*", "feedback")):
    return DiscoveryService.create_feedback(data)


@router.get("/feedback", tags=["PM Discovery"])
async def list_feedback(_perm: None = require_permission("feedback.read", "*", "feedback"),
    feedback_type: Optional[str] = None,
    sentiment: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return DiscoveryService.list_feedback(feedback_type=feedback_type, sentiment=sentiment, limit=limit, offset=offset)


# --- Roadmap ---
@router.post("/roadmap-items", tags=["PM Discovery"])
async def create_roadmap_item(data: RoadmapItemCreate, _perm: None = require_permission("roadmap.create", "*", "roadmap")):
    return DiscoveryService.create_roadmap_item(data)


@router.get("/roadmap-items", tags=["PM Discovery"])
async def list_roadmap_items(_perm: None = require_permission("roadmap.read", "*", "roadmap"),
    horizon: Optional[str] = None,
    status: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    return DiscoveryService.list_roadmap_items(horizon=horizon, status=status, category=category, limit=limit, offset=offset)


@router.patch("/roadmap-items/{item_id}", tags=["PM Discovery"])
async def update_roadmap_item(item_id: str, data: RoadmapItemUpdate, _perm: None = require_permission("roadmap.update", "*", "roadmap")):
    item = DiscoveryService.update_roadmap_item(item_id, data)
    if not item:
        raise HTTPException(status_code=404, detail="Roadmap item not found")
    return item


@router.delete("/roadmap-items/{item_id}", tags=["PM Discovery"])
async def delete_roadmap_item(item_id: str, _perm: None = require_permission("roadmap.delete", "*", "roadmap")):
    if not DiscoveryService.delete_roadmap_item(item_id):
        raise HTTPException(status_code=404, detail="Roadmap item not found")
    return {"ok": True}


# --- Prioritization ---
@router.post("/prioritization-scores", tags=["PM Discovery"])
async def create_prioritization_score(data: PrioritizationScoreCreate, _perm: None = require_permission("prioritization.create", "*", "prioritization")):
    return DiscoveryService.create_prioritization_score(data)


# --- Market Research ---
@router.post("/research", tags=["PM Discovery"])
async def create_research(data: MarketResearchCreate, _perm: None = require_permission("research.create", "*", "research")):
    return DiscoveryService.create_research(data)


@router.get("/research", tags=["PM Discovery"])
async def list_research(_perm: None = require_permission("research.read", "*", "research"),
    research_type: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return DiscoveryService.list_research(research_type=research_type, limit=limit, offset=offset)


# --- Discovery Analytics ---
@router.get("/discovery/analytics", tags=["PM Discovery"])
async def get_discovery_analytics(_perm: None = require_permission("analytics.read", "*", "analytics")):
    return DiscoveryService.get_discovery_analytics()
