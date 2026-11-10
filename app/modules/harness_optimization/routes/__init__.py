"""Harness Optimization API Routes.

Thin transport layer - all business logic lives in common_lib.
"""

from fastapi import APIRouter

from app.modules.harness_optimization.routes import (
    harnesses,
    runs,
    lessons,
    traces,
    evaluation,
    sandbox,
)

router = APIRouter(prefix="/harness-optimization", tags=["Harness Optimization"])

router.include_router(harnesses.router)
router.include_router(runs.router)
router.include_router(lessons.router)
router.include_router(traces.router)
router.include_router(evaluation.router)
router.include_router(sandbox.router)
