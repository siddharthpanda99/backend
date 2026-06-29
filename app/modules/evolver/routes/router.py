"""Evolver API — route definitions for the agent evolution framework.

All logic lives in common_lib; this module is thin routing only.
"""

from fastapi import APIRouter

from app.modules.evolver.routes.analyzer_routes import router as analyzer_router
from app.modules.evolver.routes.gene_routes import router as gene_router
from app.modules.evolver.routes.audit_routes import router as audit_router
from app.modules.evolver.routes.mailbox_routes import router as mailbox_router

router = APIRouter()
router.include_router(analyzer_router)
router.include_router(gene_router)
router.include_router(audit_router)
router.include_router(mailbox_router)
