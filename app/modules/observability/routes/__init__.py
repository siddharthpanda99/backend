from fastapi import APIRouter
from .observability_routes import router as main_router
from .admin import router as admin_router

router = APIRouter()
router.include_router(main_router)
router.include_router(admin_router)

__all__ = ["router"]
