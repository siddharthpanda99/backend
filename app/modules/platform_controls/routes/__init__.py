"""app.modules.platform_controls.routes — Phase 0 router surface.

The full route set (sessions, catalog, history, chat, prefs, audit,
WS) lands in later phases per docs/08_api_contracts.md and
docs/12_implementation_phases.md. Phase 0 ships ONE endpoint:
``GET /api/v1/platform-controls/health``, which is unauthenticated
per docs/14_observability_security.md §3 ("the unauthenticated health
check returns only {status, version, capabilities}").
"""

from app.modules.platform_controls.routes.router import router

__all__ = ["router"]
