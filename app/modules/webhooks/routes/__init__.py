"""
Webhook Manager — Aggregated Router

Combines all sub-routers (endpoints, deliveries, seed)
under the /api/v1/webhooks prefix.
"""

from fastapi import APIRouter
from .endpoints import router as endpoints_router
from .deliveries import router as deliveries_router

router = APIRouter()
router.include_router(endpoints_router)    # /endpoints, /endpoints/{id}/enable, /disable, /regenerate-secret
router.include_router(deliveries_router)   # /deliveries, /deliveries/test-send/{id}, /deliveries/clear

__all__ = ["router"]
