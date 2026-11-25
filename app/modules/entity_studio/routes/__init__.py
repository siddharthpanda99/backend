"""
Entity Studio Routes — Thin transport layer for Entity Studio API.

All business logic lives in common_lib.modules.entity_studio.service.
This module only handles HTTP parsing, validation, and response shaping.
"""

from .atoms_routes import router as atoms_router
from .molecules_routes import router as molecules_router
from .organisms_routes import router as organisms_router
from .ai_assisted_routes import router as ai_assisted_router
from .lineage_routes import router as lineage_router
from .evolution_routes import router as evolution_router
from .query_routes import router as query_router

# Combine all routers
from fastapi import APIRouter

router = APIRouter()
router.include_router(atoms_router, prefix="/atoms", tags=["Entity Studio - Atoms"])
router.include_router(
    molecules_router, prefix="/molecules", tags=["Entity Studio - Molecules"]
)
router.include_router(
    organisms_router, prefix="/organisms", tags=["Entity Studio - Organisms"]
)
router.include_router(
    ai_assisted_router, prefix="/ai-assisted", tags=["Entity Studio - AI Assisted"]
)
router.include_router(
    lineage_router, prefix="/lineage", tags=["Entity Studio - Lineage"]
)
router.include_router(
    evolution_router, prefix="/evolution", tags=["Entity Studio - Evolution"]
)
router.include_router(query_router, prefix="", tags=["Entity Studio - Query"])
