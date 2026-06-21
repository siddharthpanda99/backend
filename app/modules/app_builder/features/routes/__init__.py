"""
Feature Picker — Routes Aggregator
"""

from fastapi import APIRouter
from app.modules.app_builder.features.routes.features import router as features_router
from app.modules.app_builder.features.routes.assignments import router as assignments_router
from app.modules.app_builder.features.routes.catalog import router as catalog_router

router = APIRouter()
router.include_router(features_router)
router.include_router(assignments_router)
router.include_router(catalog_router)

__all__ = ["router"]
