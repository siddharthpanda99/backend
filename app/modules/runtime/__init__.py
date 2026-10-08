"""AI Runtime Layer — FastAPI router module.

This module provides thin API routers that delegate all business logic
to `common_lib.modules.runtime`.
"""

from __future__ import annotations

from .routes import router

__all__ = ["router"]