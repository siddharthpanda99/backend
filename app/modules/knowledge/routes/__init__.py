from app.modules.knowledge.routes.router import (
    router,
    ConfigUpdateRequest,
    _get_learning_instance,
)

# Include learning sub-routes AFTER the main router is fully loaded
# to avoid circular imports (learning_routes.py imports back from routes)
from app.modules.knowledge.learning_routes import router as learning_router

router.include_router(learning_router)

__all__ = ["router", "ConfigUpdateRequest", "_get_learning_instance"]
