"""Cognitive Runtime API Routes - Thin router layer."""

from fastapi import APIRouter

from app.modules.cognitive_runtime.routes import evaluate, execute, infer, plan, runs

# No prefix here: app/core/routers.py registers this router with
# prefix="/cognitive", and FastAPI concatenates the two. Declaring "/cognitive"
# here as well produced /api/v1/cognitive/cognitive/... for all 13 routes.
router = APIRouter(tags=["Cognitive Runtime"])

router.include_router(infer.router)
router.include_router(plan.router)
router.include_router(execute.router)
router.include_router(runs.router)
router.include_router(evaluate.router)

__all__ = ["router"]
