from app.modules.audio.routes.router import router as main_router
from app.modules.audio.routes.takes_routes import router as takes_router

# Merge takes routes into the main audio router under the same prefix
# The takes_router has sub-path /generate, /takes/*, etc.
for route in takes_router.routes:
    main_router.routes.append(route)

__all__ = ["router"]

# Re-export main_router as router
router = main_router
