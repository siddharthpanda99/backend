"""Runtime Fabric admin routes - thin transport shim.

Re-exports the common_lib admin APIRouter so the Backend gateway serves it
under /api/v1/runtime/* without duplicating any logic.
"""

from common_lib.modules.runtime_fabric.admin import router

__all__ = ["router"]
