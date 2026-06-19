from fastapi import APIRouter
from common_lib.modules.auth.authorization.routes import router as authz_router

router = APIRouter()
router.include_router(authz_router, prefix="/authz", tags=["Authorization"])
