"""Security Module — Aggregated Router.

Combines all security sub-routers under /api/v1/security prefix.
"""

from fastapi import APIRouter
from .security_routes import router as security_router

router = APIRouter()
router.include_router(security_router)

__all__ = ["router"]
