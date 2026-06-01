from fastapi import APIRouter
from .routes import views, sessions

router = APIRouter(prefix="/ext-apps")

router.include_router(views.router)
router.include_router(sessions.router)
