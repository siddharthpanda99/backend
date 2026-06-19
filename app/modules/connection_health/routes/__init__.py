"""
Connection Health — Aggregated Router
"""

from fastapi import APIRouter
from .health import router as health_router

router = APIRouter()
router.include_router(health_router)  # /connection-health, /connection-health/{id}, /refresh, /settings

__all__ = ["router"]
