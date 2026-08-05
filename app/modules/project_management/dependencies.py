"""
PM Module — Shared dependency re-exports.

Provides backward-compatible re-exports for route modules that import
from app.modules.project_management.dependencies.

Used by:
- offline_routes.py (imports get_db_session)
- universal_graph_routes.py (imports get_db_session)

Both delegate to the canonical get_pm_session function in deps.py.
"""

from app.modules.project_management.deps import get_pm_session

# Backward-compatible alias: get_db_session → get_pm_session
get_db_session = get_pm_session

__all__ = ["get_db_session", "get_pm_session"]
