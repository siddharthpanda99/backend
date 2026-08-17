"""Reasoning Mode — REST API module.

Exposes requirement-plan creation/CRUD and brief step explanations under
``/api/v1/reasoning``. Logic lives in ``common_lib.modules.reasoning``
(thin-router convention).
"""

from app.modules.reasoning.routes import router

__all__ = ["router"]
