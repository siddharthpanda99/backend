"""App-Ops Routes.

Thin FastAPI router exposing health check functionality. Delegates all
logic to ``common_lib.modules.app_ops``. The live route count is computed
here (from the FastAPI app) and injected into the common_lib service —
common_lib itself never imports the FastAPI app.
"""

from app.modules.app_ops.routes.router import router

__all__ = ["router"]
