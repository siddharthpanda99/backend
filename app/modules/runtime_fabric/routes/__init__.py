"""Runtime Fabric routers (thin re-exports of common_lib routers)."""

from app.modules.runtime_fabric.routes.admin_routes import router

__all__ = ["router"]
