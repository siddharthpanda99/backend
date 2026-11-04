"""Auto-Ontology routes package.

Thin router layer — all business logic lives in
common_lib.modules.auto_ontology.service.
"""

from __future__ import annotations

from fastapi import APIRouter

# Re-export all sub-routers
from .connections_routes import router as connections_router
from .ingestion_routes import router as ingestion_router
from .terms_routes import router as terms_router
from .sql_attributes_routes import router as sql_attributes_router
from .tables_routes import router as tables_router
from .questions_routes import router as questions_router
from .model_routes import router as model_router

# Combined router for the auto-ontology module
router = APIRouter(prefix="/auto-ontology", tags=["Auto-Ontology"])
router.include_router(connections_router)
router.include_router(ingestion_router)
router.include_router(terms_router)
router.include_router(sql_attributes_router)
router.include_router(tables_router)
router.include_router(questions_router)
router.include_router(model_router)

__all__ = [
    "connections_router",
    "ingestion_router",
    "terms_router",
    "sql_attributes_router",
    "tables_router",
    "questions_router",
    "model_router",
    "router",
]
