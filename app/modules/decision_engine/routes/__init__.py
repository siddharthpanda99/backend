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
    context,
    engine,
    intent,
    registry,
    health,
)

# No prefix here on purpose: ROUTER_DEFINITIONS in app/core/routers.py mounts
# this router with prefix="/decision-engine" (under /api/v1). Declaring the
# prefix on the router as well produced a doubled path
# (/api/v1/decision-engine/decision-engine/...) so every decision-engine
# endpoint 404'd in the running app. Sibling routers follow the same rule:
# the mount point owns the prefix.
router = APIRouter(tags=["Decision Engine"])

# Include all sub-routers
router.include_router(ingest.router)
router.include_router(ground.router)
router.include_router(decide.router)
router.include_router(plan.router)
router.include_router(models.router)
router.include_router(thresholds.router)
router.include_router(provenance.router)
router.include_router(context.router)
router.include_router(engine.router)
router.include_router(intent.router)
router.include_router(registry.router)
router.include_router(health.router)

__all__ = ["router"]
