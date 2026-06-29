from app.modules.integration.routes.router import router as main_router
from app.modules.integration.routes.config_routes import router as config_router
from app.modules.integration.routes.middleware import ApiVersionMiddleware, get_api_version
from app.modules.integration.routes.versioning import (
    VERSION_HELP,
    VALID_VERSIONS,
    validate_version,
    resolve_api_version,
)

# Combine both routers into a single export
# main_router handles /integration/* endpoints
# config_router handles /integration/config/* endpoints
main_router.include_router(config_router)

router = main_router

__all__ = [
    "router",
    "ApiVersionMiddleware",
    "get_api_version",
    "VERSION_HELP",
    "VALID_VERSIONS",
    "validate_version",
    "resolve_api_version",
]
