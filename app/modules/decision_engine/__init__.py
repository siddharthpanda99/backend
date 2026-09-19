"""Decision Engine transport module — thin router only.

All business logic lives in common_lib.modules.decision_engine.
This module only provides the FastAPI transport layer.
"""

from app.modules.decision_engine.routes import router  # noqa: F401

__all__ = ["router"]
