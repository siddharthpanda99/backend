from fastapi import APIRouter
from app.modules.team.routes.teams import router as teams_router
from app.modules.team.routes.rbac import router as rbac_router

router = APIRouter()
router.include_router(teams_router, prefix="/team", tags=["Team"])
router.include_router(rbac_router, prefix="/team", tags=["Team - RBAC"])
