"""
Schema Builder — Aggregated Router

Combines all sub-routers (tables, relationships, migrations, DDL, models)
under the /api/v1/schema prefix.
"""

from fastapi import APIRouter
from .tables import router as tables_router
from .relationships import router as relationships_router
from .migrations import router as migrations_router
from .ddl import router as ddl_router
from .models_gen import router as models_gen_router
from .router import router as dry_run_router  # existing dry-run endpoints

# Aggregated schema router: mounts all sub-routers under /api/v1/schema/
router = APIRouter()

router.include_router(tables_router)          # /tables, /tables/{id}/columns
router.include_router(relationships_router)   # /relationships
router.include_router(migrations_router)      # /migrations, /migrations/{id}/execute, /rollback
router.include_router(ddl_router)             # /ddl
router.include_router(models_gen_router)      # /models
router.include_router(dry_run_router)         # /dry-run, /batch-dry-run (existing)

__all__ = ["router"]
