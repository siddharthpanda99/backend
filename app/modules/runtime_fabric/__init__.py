"""Runtime Fabric thin transport module.

All logic lives in common_lib.modules.runtime_fabric; this package only
re-hosts it over HTTP under /api/v1/runtime (admin + observability surface).
"""

from app.modules.runtime_fabric.routes import router

__all__ = ["router"]
