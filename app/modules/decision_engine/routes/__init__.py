"""Decision Engine API Routes - Thin router layer."""

from fastapi import APIRouter

from app.modules.decision_engine.routes import (
    ingest,
    ground,
    decide,
    plan,
    models,
    thresholds,
    provenance,
)

router = APIRouter(prefix="/decision-engine", tags=["Decision Engine"])

# Include all sub-routers
router.include_router(ingest.router)
router.include_router(ground.router)
router.include_router(decide.router)
router.include_router(plan.router)
router.include_router(models.router)
router.include_router(thresholds.router)
router.include_router(provenance.router)

__all__ = ["router"]
