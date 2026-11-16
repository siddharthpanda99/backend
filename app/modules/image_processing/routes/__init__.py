"""Image Processing routes package."""

from .comparator_routes import router
from .creative_studio_routes import router as creative_studio_router

__all__ = ["router", "creative_studio_router"]
