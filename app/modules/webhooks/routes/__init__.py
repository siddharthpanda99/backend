"""
Webhook Manager — Aggregated Router

Combines all sub-routers (endpoints, deliveries, seed)
under the /api/v1/webhooks prefix.
"""

from fastapi import APIRouter
from .endpoints import router as endpoints_router
from .deliveries import router as deliveries_router
from .mappings import router as mappings_router
from .listener import router as listener_router

router = APIRouter()
router.include_router(
    endpoints_router
)  # /endpoints, /endpoints/{id}/enable, /disable, /regenerate-secret
router.include_router(
    deliveries_router
)  # /deliveries, /deliveries/test-send/{id}, /deliveries/clear
router.include_router(mappings_router)  # /event-mappings CRUD
router.include_router(listener_router)  # /in/{slug} inbound listener

__all__ = ["router"]
