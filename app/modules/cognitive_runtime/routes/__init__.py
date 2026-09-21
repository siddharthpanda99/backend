"""Cognitive Runtime API Routes - Thin router layer."""

from fastapi import APIRouter

from app.modules.cognitive_runtime.routes import evaluate, execute, infer, plan, runs

router = APIRouter(prefix="/cognitive", tags=["Cognitive Runtime"])

router.include_router(infer.router)
router.include_router(plan.router)
router.include_router(execute.router)
router.include_router(runs.router)
router.include_router(evaluate.router)

__all__ = ["router"]
