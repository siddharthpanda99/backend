"""
App Ecosystem — Aggregated Router
"""

from fastapi import APIRouter
from app.modules.app_builder.ecosystem.routes.apps import router as apps_router
from app.modules.app_builder.ecosystem.routes.social import router as social_router
from app.modules.app_builder.ecosystem.routes.blogs import router as blogs_router
from app.modules.app_builder.ecosystem.routes.reviews import router as reviews_router
from app.modules.app_builder.ecosystem.routes.walkthroughs import router as walkthroughs_router
from app.modules.app_builder.ecosystem.routes.data import router as data_router
from app.modules.app_builder.ecosystem.routes.settings import router as settings_router
from app.modules.app_builder.ecosystem.routes.free_apis import router as free_apis_router

router = APIRouter()
router.include_router(apps_router)          # /apps
router.include_router(social_router)        # /apps/{app_id}/social
router.include_router(blogs_router)         # /apps/{app_id}/blogs
router.include_router(reviews_router)       # /apps/{app_id}/reviews
router.include_router(walkthroughs_router)  # /apps/{app_id}/walkthroughs
router.include_router(data_router)          # /apps/{app_id}/data
router.include_router(settings_router)      # /apps/{app_id}/settings
router.include_router(free_apis_router)     # /apps/free-apis

__all__ = ["router"]
