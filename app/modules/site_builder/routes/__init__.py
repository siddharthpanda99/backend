"""Site Builder routes — thin wrappers around site_builder services."""

from app.modules.site_builder.routes.project_routes import router as project_router
from app.modules.site_builder.routes.sitemap_routes import router as sitemap_router
from app.modules.site_builder.routes.wireframe_routes import router as wireframe_router
from app.modules.site_builder.routes.registry_routes import router as registry_router
from app.modules.site_builder.routes.theme_routes import router as theme_router
from app.modules.site_builder.routes.export_routes import router as export_router

__all__ = [
    "project_router",
    "sitemap_router",
    "wireframe_router",
    "registry_router",
    "theme_router",
    "export_router",
]
