"""App-Ops Module — Backend thin router exposing health checks.

All logic lives in ``common_lib.modules.app_ops``. This module only mounts
the routes and injects the live FastAPI route count.
"""

from app.modules.app_ops.routes import router

__all__ = ["router"]
