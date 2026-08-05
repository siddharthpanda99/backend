"""Plugin Routes."""
from app.modules.plugins.routes.router import router
from app.modules.plugins.routes.plugin_routes import router as plugin_router

__all__ = ["router", "plugin_router"]
