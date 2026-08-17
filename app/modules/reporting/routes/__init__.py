"""Reporting router — aggregates per-resource route submodules.

Mirrors the submodule layout used by ``dip``/``hitl``/``knowledge``: each
resource area owns its route file, and this module composes them into one
``router`` mounted at ``/api/v1/reporting``.

    templates/   → /templates             (CRUD, seed, office-source create,
    │                                      version history/diff/rollback)
    generate/    → /generate, /formats, /health
    editing/     → /edit/render
    commands/    → /command, /workflow/run
    workflow/    → /triggers
    marketplace/ → /marketplace
    assets/      → /assets, /brand-kits, /audit, /documents
    benchmarks/  → /benchmarks/run        (Phase 47 — render/merge throughput)
    forms/       → /forms/*               (Phase 31 — UFP submission bridge)
    ai/          → /ai/*                  (Phases 34-35 — summary/draft/clean)
    plugins/     → /plugins/*             (Phases 41-43 — SDK manifest)
    security/    → /security/*            (Phase 48 — redact/scan/authorize)
"""

from __future__ import annotations

from fastapi import APIRouter

from app.modules.reporting.routes.ai import router as ai_router
from app.modules.reporting.routes.assets import router as assets_router
from app.modules.reporting.routes.benchmarks import router as benchmarks_router
from app.modules.reporting.routes.commands import router as commands_router
from app.modules.reporting.routes.editing import router as editing_router
from app.modules.reporting.routes.forms import router as forms_router
from app.modules.reporting.routes.generate import router as generate_router
from app.modules.reporting.routes.marketplace import router as marketplace_router
from app.modules.reporting.routes.plugins import router as plugins_router
from app.modules.reporting.routes.security import router as security_router
from app.modules.reporting.routes.templates import router as templates_router
from app.modules.reporting.routes.workflow import router as workflow_router

router = APIRouter()
router.include_router(templates_router)
router.include_router(generate_router)
router.include_router(editing_router)
router.include_router(commands_router)
router.include_router(workflow_router)
router.include_router(marketplace_router)
router.include_router(assets_router)
router.include_router(benchmarks_router)
router.include_router(forms_router)
router.include_router(ai_router)
router.include_router(plugins_router)
router.include_router(security_router)

__all__ = ["router"]
