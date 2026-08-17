"""Toolchain Builder — thin router module.

Mounted at ``/api/v1/toolchain`` via ``app.core.routers``. Exposes the
routing decision + plan used by the Toolchain Visualizer UI.
"""

from app.modules.toolchain.routes import router

__all__ = ["router"]
