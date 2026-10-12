"""Model loader — thin API module for capability discovery/validation/manifests (RAG-P1-005).

P1-004 (lifecycle) has not claimed this module yet (verified 2026-10-12:
no ``model_loader`` backend dir, tracker RAG-P1-004 still pending), so this
file is owned by RAG-P1-005. P1-004 lifecycle routes (``/models/{id}/inspect|/load``,
``/model-loader/jobs/*``) must live in a *separate* routes file to preserve ownership.
"""

from app.modules.model_loader.routes.capabilities import router as model_loader_capabilities_router

__all__ = ["model_loader_capabilities_router"]
