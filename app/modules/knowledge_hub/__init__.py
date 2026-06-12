"""
Knowledge Sources Hub — API Module.

FastAPI routes for the Knowledge Sources Hub at /api/v1/knowledge-hub/.

This module provides the API layer for managing data sources, ingestion
pipelines, data packets, and knowledge projects. All data is persisted
via SQLModel and served through the knowledge_hub service layer.
"""

from app.modules.knowledge_hub.routes.sources import router as sources_router
from app.modules.knowledge_hub.routes.pipelines import router as pipelines_router
from app.modules.knowledge_hub.routes.packets import router as packets_router
from app.modules.knowledge_hub.routes.projects import router as projects_router

__all__ = [
    "sources_router",
    "pipelines_router",
    "packets_router",
    "projects_router",
]
