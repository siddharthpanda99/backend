"""``app.modules.i2w.routes.router`` — aggregator.

Mounts every per-stage sub-router under a single ``APIRouter`` so
``app.core.routers.ROUTER_DEFINITIONS`` has exactly one entry per
module (the platform convention).
"""

from __future__ import annotations

from fastapi import APIRouter

from app.modules.i2w.routes import (
    dispatch,
    executions,
    generate,
    health,
    ingest,
    metrics,
    plan,
    reason,
    search,
    training,
    workflows,
    ws,
)


router = APIRouter()

# The /generate, /ingest, /reason, /plan, /dispatch sub-routers
# have their own prefix-free paths and mount at the parent's prefix.
# The workflows / executions / training / search / health / metrics
# routers are mounted flat so the per-resource paths work
# (/api/v1/i2w/plans/... etc).
router.include_router(generate.router)
router.include_router(ingest.router)
router.include_router(reason.router)
router.include_router(plan.router)
router.include_router(dispatch.router)
router.include_router(workflows.router)
router.include_router(executions.router)
router.include_router(training.router)
router.include_router(search.router)
router.include_router(health.router)
router.include_router(metrics.router)
router.include_router(ws.router)


__all__ = ["router"]
