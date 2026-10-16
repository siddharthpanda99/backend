"""nlp2sql routes aggregator — single router for ROUTER_DEFINITIONS (G1)."""

from fastapi import APIRouter

from app.modules.nlp2sql.routes.analytics import router as analytics_router
from app.modules.nlp2sql.routes.catalog import router as catalog_router
from app.modules.nlp2sql.routes.connections import router as connections_router
from app.modules.nlp2sql.routes.dbt_projects import router as dbt_router
from app.modules.nlp2sql.routes.governance import router as governance_router
from app.modules.nlp2sql.routes.query import router as query_router
from app.modules.nlp2sql.routes.semantic import router as semantic_router
from app.modules.nlp2sql.routes.sessions import router as sessions_router

router = APIRouter()
for _sub in (
    sessions_router,
    query_router,
    connections_router,
    catalog_router,
    semantic_router,
    analytics_router,
    governance_router,
    dbt_router,
):
    router.include_router(_sub)

__all__ = ["router"]
