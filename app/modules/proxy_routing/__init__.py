from fastapi import APIRouter
from app.modules.proxy_routing.routes import router as proxy_router

router = APIRouter()
router.include_router(proxy_router)

__all__ = ["router"]
