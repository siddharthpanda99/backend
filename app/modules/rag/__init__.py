"""RAG — thin API module for canonical contracts v1 (RAG-P0-002)."""

from app.modules.rag.routes.router import router as rag_router

__all__ = ["rag_router"]
