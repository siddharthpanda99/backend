"""Character Studio API routes - Main router."""

from __future__ import annotations

from fastapi import APIRouter

from app.modules.character_studio.routes import (
    characters,
    dna,
    identities,
    references,
    generations,
    exports,
    profiles,
    workflows,
    jobs,
    health,
)

router = APIRouter()

# Characters routes (mounted at /character-studio/, so no duplicate prefix)
router.include_router(characters.router, prefix="", tags=["characters"])
router.include_router(dna.router, prefix="", tags=["dna"])
router.include_router(identities.router, prefix="", tags=["identities"])
router.include_router(references.router, prefix="", tags=["references"])
router.include_router(generations.router, prefix="", tags=["generations"])
router.include_router(exports.router, prefix="", tags=["exports"])
router.include_router(profiles.router, prefix="", tags=["profiles"])
router.include_router(workflows.router, prefix="/workflows", tags=["workflows"])
router.include_router(jobs.router, prefix="/generation-jobs", tags=["jobs"])
router.include_router(health.router, tags=["health"])
