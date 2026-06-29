from fastapi import APIRouter
from app.modules.hitl.routes.router import router as hitl_policies_router

router = APIRouter()
router.include_router(hitl_policies_router)

__all__ = ["router"]
