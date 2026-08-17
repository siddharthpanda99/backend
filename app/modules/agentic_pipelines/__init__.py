"""Agentic Pipelines — thin router layer (mounted at /api/v1/agentic-pipelines)."""

from app.modules.agentic_pipelines.routes import router

__all__ = ["router"]
