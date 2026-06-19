"""Observability admin routes.

These were moved from common_lib/modules/observability/admin_routes.py
as part of the P0.3 boundary cleanup — all route definitions belong in
app/modules, with common_lib providing only services/models.
"""

from app.modules.observability.routes.admin import router

__all__ = ["router"]
