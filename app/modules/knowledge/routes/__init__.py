from app.modules.knowledge.routes.router import (
    router,
    ConfigUpdateRequest,
)

# Keep learning_routes config endpoints for backward compatibility.
# The main learning routes are already included via router.py.
from app.modules.knowledge.routes.learning_routes import router as learning_router

router.include_router(learning_router)

__all__ = ["router", "ConfigUpdateRequest"]
