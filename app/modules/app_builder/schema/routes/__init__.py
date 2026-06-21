"""
Schema Builder — Aggregated Router

Combines all sub-routers (tables, relationships, migrations, DDL, models)
under the /api/v1/schema prefix.
"""

from fastapi import APIRouter
from app.modules.app_builder.schema.routes.tables import router as tables_router
from app.modules.app_builder.schema.routes.relationships import router as relationships_router
from app.modules.app_builder.schema.routes.migrations import router as migrations_router
from app.modules.app_builder.schema.routes.ddl import router as ddl_router
from app.modules.app_builder.schema.routes.models_gen import router as models_gen_router
from app.modules.app_builder.schema.routes.models import router as models_crud_router
from app.modules.app_builder.schema.routes.snapshots import router as snapshots_router
from app.modules.app_builder.schema.routes.seed_data import router as seed_data_router
from app.modules.app_builder.schema.routes.diagram_layout import router as diagram_layout_router
from app.modules.app_builder.schema.routes.versions import router as versions_router
from app.modules.app_builder.schema.routes.router import router as dry_run_router
from app.modules.app_builder.schema.routes.databases import router as databases_router
from app.modules.app_builder.schema.routes.marketplace import router as marketplace_router
from app.modules.app_builder.schema.routes.reviews import router as reviews_router
from app.modules.app_builder.schema.routes.blogs import router as blogs_router
from app.modules.app_builder.schema.routes.guides import router as guides_router
from app.modules.app_builder.schema.routes.forums import router as forums_router
from app.modules.app_builder.schema.routes.fan_pages import router as fan_pages_router
from app.modules.app_builder.schema.routes.promotions import router as promotions_router

router = APIRouter()

router.include_router(tables_router)
router.include_router(relationships_router)
router.include_router(migrations_router)
router.include_router(ddl_router)
router.include_router(models_gen_router)
router.include_router(models_crud_router)
router.include_router(snapshots_router)
router.include_router(seed_data_router)
router.include_router(diagram_layout_router)
router.include_router(versions_router)
router.include_router(dry_run_router)
router.include_router(databases_router)
router.include_router(marketplace_router)
router.include_router(reviews_router)
router.include_router(blogs_router)
router.include_router(guides_router)
router.include_router(forums_router)
router.include_router(fan_pages_router)
router.include_router(promotions_router)

__all__ = ["router"]
