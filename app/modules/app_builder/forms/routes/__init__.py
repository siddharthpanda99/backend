"""
Form Builder — Routes Aggregator
"""

"""
Form Builder — Routes Aggregator
"""

from fastapi import APIRouter
from app.modules.app_builder.forms.routes.forms import router as forms_router
from app.modules.app_builder.forms.routes.composition import router as composition_router

router = APIRouter()
router.include_router(forms_router)
router.include_router(composition_router)

__all__ = ["router"]
