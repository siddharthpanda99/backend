"""GPT Builder — Routes Package.

Assembles all sub-routers into a single router for registration.
"""

from fastapi import APIRouter

from .app_routes import router as app_router
from .session_routes import router as session_router
from .chat_routes import router as chat_router
from .marketplace_routes import router as marketplace_router
from .analytics_routes import router as analytics_router
from .ai_routes import router as ai_router
from .widget_routes import router as widget_router

router = APIRouter()

router.include_router(app_router, prefix="/gpt-builder/apps")
router.include_router(ai_router, prefix="/gpt-builder/apps")
router.include_router(session_router, prefix="/gpt-builder/sessions")
router.include_router(chat_router, prefix="/gpt-builder/sessions")
router.include_router(marketplace_router, prefix="/gpt-builder")
router.include_router(analytics_router, prefix="/gpt-builder/apps")
router.include_router(widget_router, prefix="/gpt-builder/widgets")

__all__ = ["router"]
