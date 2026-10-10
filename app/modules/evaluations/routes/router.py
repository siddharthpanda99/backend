from fastapi import APIRouter

from app.modules.evaluations.routes.eval_runs import router as eval_runs_router
from app.modules.evaluations.routes.trace_scores import router as trace_scores_router

router = APIRouter()
router.include_router(eval_runs_router)
router.include_router(trace_scores_router)

__all__ = ["router"]
