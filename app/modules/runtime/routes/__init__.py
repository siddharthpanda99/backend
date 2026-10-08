"""AI Runtime Layer — Route definitions.

Aggregates all runtime API endpoints under a single router.
"""

from __future__ import annotations

from fastapi import APIRouter

from . import (
    plan,
    execute,
    capabilities,
    devices,
    runtimes,
    artifacts,
    models,
    executions,
    health,
)

router = APIRouter()

# Include all sub-routers
router.include_router(plan.router, tags=["Runtime — Planning"])
router.include_router(execute.router, tags=["Runtime — Execution"])
router.include_router(capabilities.router, tags=["Runtime — Capabilities"])
router.include_router(devices.router, tags=["Runtime — Devices"])
router.include_router(runtimes.router, tags=["Runtime — Runtimes"])
router.include_router(artifacts.router, tags=["Runtime — Artifacts"])
router.include_router(models.router, tags=["Runtime — Models"])
router.include_router(executions.router, tags=["Runtime — Executions"])
router.include_router(health.router, tags=["Runtime — Health"])

__all__ = ["router"]