from app.modules.integration.routes.router import router as main_router
from app.modules.integration.routes.config_routes import router as config_router

# Combine both routers into a single export
# main_router handles /integration/* endpoints
# config_router handles /integration/config/* endpoints
main_router.include_router(config_router)

router = main_router

__all__ = ["router"]
