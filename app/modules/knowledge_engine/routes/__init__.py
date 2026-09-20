"""
Knowledge Engine Routes Package.

Thin router layer delegating to common_lib services.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.modules.knowledge_engine.routes.entities import router as entities_router
from app.modules.knowledge_engine.routes.claims import router as claims_router
from app.modules.knowledge_engine.routes.relationships import (
    router as relationships_router,
)
from app.modules.knowledge_engine.routes.evidence import router as evidence_router
from app.modules.knowledge_engine.routes.commits import router as commits_router
from app.modules.knowledge_engine.routes.branches import router as branches_router
from app.modules.knowledge_engine.routes.snapshots import router as snapshots_router
from app.modules.knowledge_engine.routes.provenance import router as provenance_router
from app.modules.knowledge_engine.routes.reconcile import router as reconcile_router
from app.modules.knowledge_engine.routes.retrieve import router as retrieve_router
from app.modules.knowledge_engine.routes.search import router as search_router

router = APIRouter(tags=["Knowledge Engine"])

# Include all sub-routers
router.include_router(entities_router)
router.include_router(claims_router)
router.include_router(relationships_router)
router.include_router(evidence_router)
router.include_router(commits_router)
router.include_router(branches_router)
router.include_router(snapshots_router)
router.include_router(provenance_router)
router.include_router(reconcile_router)
router.include_router(retrieve_router)
router.include_router(search_router)


__all__ = ["router"]
