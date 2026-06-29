from fastapi import APIRouter

from app.modules.prompt_studio.routes.scraper import router as scraper_router
from app.modules.prompt_studio.routes.form_configs import router as form_configs_router

# Mount sub-routers with their own prefixes
router = APIRouter(prefix="/prompt-studio")
router.include_router(scraper_router)
router.include_router(form_configs_router)

__all__ = ["router"]
