from app.modules.models.routes.resolve import router as resolve_router
from app.modules.models.routes.router import router, get_container

# Merge the NEX-P4-001 resolve endpoint into the shared models router so
# POST /models/resolve is served alongside the existing registry routes.
router.include_router(resolve_router)

__all__ = ["router", "get_container", "resolve_router"]
