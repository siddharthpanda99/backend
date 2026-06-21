"""
Visual UI Builder — Module Root

Provides CRUD for canvas presets, component instances, and design tokens
used by the Figma-class DesignCanvas in the App Builder frontend.

Routes are mounted at /api/v1/builder/
"""

from app.modules.app_builder.routes import router

__all__ = ["router"]
