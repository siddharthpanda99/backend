from app.modules.knowledge.routes.router import (
    router,
    ConfigUpdateRequest,
)

# Keep learning_routes config endpoints for backward compatibility.
# The main learning routes are already included via router.py.
from app.modules.knowledge.routes.learning_routes import router as learning_router

router.include_router(learning_router)

# NEX-P6-002: graph-benchmark routes (flag-gated, 404 while OFF).
from app.modules.knowledge.routes.graph_benchmark import router as graph_benchmark_router

router.include_router(graph_benchmark_router)

__all__ = ["router", "ConfigUpdateRequest"]
