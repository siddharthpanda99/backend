"""Backend reporting module — thin REST layer over common_lib.modules.reporting.

All business logic lives in ``common_lib.modules.reporting``; the module only
exposes the aggregated ``routes`` router (per-resource route submodules),
mounted at ``/api/v1/reporting`` (see ``app/core/routers.py``).
"""

from app.modules.reporting.routes import router

__all__ = ["router"]
