from app.modules.memory.routes.router import router
from app.modules.memory.routes.graph import router as graph_router
from app.modules.memory.routes.cognitive import router as cognitive_router

router.include_router(graph_router)
router.include_router(cognitive_router)

# Wire sub-routers AFTER router is fully loaded to avoid circular imports
# (wire_routes.py imports `from app.modules.memory.routes import router`)
import app.modules.memory.wire_routes  # noqa: F401, E402

__all__ = ["router"]
