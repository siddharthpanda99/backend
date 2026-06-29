from fastapi import APIRouter

from app.modules.prompts_hero.routes.generation_routes import (
    router as generation_router,
)
from app.modules.prompts_hero.routes.community_routes import router as community_router
from app.modules.prompts_hero.routes.discovery_routes import router as discovery_router
from app.modules.prompts_hero.routes.tool_routes import router as tool_router
from app.modules.prompts_hero.routes.gamification_routes import (
    router as gamification_router,
)

router = APIRouter()
router.include_router(generation_router)
router.include_router(community_router)
router.include_router(discovery_router)
router.include_router(tool_router)
router.include_router(gamification_router)
