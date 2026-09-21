from .router import router
from .capabilities import router as capabilities_router

router.include_router(capabilities_router)

__all__ = ["router", "capabilities_router"]
