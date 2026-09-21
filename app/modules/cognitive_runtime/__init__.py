"""Cognitive Runtime transport module — thin routers only.

All business logic lives in common_lib.modules.cognitive_runtime.
This module only provides the FastAPI transport layer.
"""

from app.modules.cognitive_runtime.routes import router  # noqa: F401

__all__ = ["router"]
