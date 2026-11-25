"""
Entity Studio Module — FastAPI transport layer.

Routes are defined in app/modules/entity_studio/routes/
Business logic lives in common_lib.modules.entity_studio
"""

from .routes import router

__all__ = ["router"]
