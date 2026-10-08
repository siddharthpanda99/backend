"""Deprecated router — kept for the 6-month BC window (Phase 12 — PR 2).

.. deprecated::
    **Not currently mounted.** This router is built, but no entry in
    ``app/core/routers.py`` ``ROUTER_DEFINITIONS`` mounts it, so nothing is
    served under ``/api/v1/voice-control/`` — verified by enumerating the built
    app (0 served paths under that prefix). Kept unmounted deliberately: it is a
    sunsetting alias (Sunset 2027-02-28) with zero consumers — no frontend
    service client, no MCP tool, no test — and the canonical
    ``/api/v1/platform-controls/`` space is already mounted. Use
    ``/api/v1/platform-controls/`` instead. See
    ``common_lib/modules/platform_controls/docs/11_migration_from_voice_control.md``
    §6 for the router-level shim contract.

This router is a **pure re-export** of the canonical
:mod:`app.modules.platform_controls.routes.router` under the legacy URL
prefix. It contains no business logic — every route defined by the
canonical router is served here, transparently, so that any client still
hitting the old URL gets the same response as if it had hit the new one.

Deprecation signalling
----------------------

This module emits a :class:`DeprecationWarning` at import time so the
deprecation surfaces in uvicorn's startup logs (every deploy). The HTTP
response headers (``Deprecation: true`` + ``Sunset: <date>``) are added
by :class:`app.modules.voice_control.middleware.DeprecationHeadersMiddleware`,
which :mod:`app.main` registers only when the default-OFF feature flag
``voice_control.deprecation_headers`` is on — because with nothing mounted
here that middleware would only tag 404s. Because it is a pure
``include_router`` re-export this module also declares no decorated routes of
its own, which is why the dead-handler guard in
``tests/test_dead_routes_guard.py`` never examines it: its handlers are
identity-equal to the already-mounted canonical ones. See
:mod:`app.modules.voice_control.flags`.
"""

from __future__ import annotations

import warnings

# Emit a :class:`DeprecationWarning` at module import time (i.e. when
# uvicorn loads the app and ``routers.py`` imports this module).
# Surfaces in uvicorn's startup logs so the migration team sees it
# during every deploy.
warnings.warn(
    "app.modules.voice_control.routes is deprecated; "
    "mount app.modules.platform_controls.routes instead. "
    "Removal target: 2027-02-28 (6 months from the platform_controls v1.0.0 release).",
    DeprecationWarning,
    stacklevel=2,
)

from fastapi import APIRouter

# Import the canonical router. We re-export the same `router` object
# under a new prefix so every route it defines is served at the old
# ``/api/v1/voice-control/`` URL as well. This is the cleanest "pure
# re-export" shape: zero new business logic, zero handler duplication.
#
# The ``prefix="/voice-control"`` is what makes the old URL space
# work — the canonical router ships routes like ``/health`` and any
# future ``/voice/transcribe``, ``/chat`` etc. The prefix is applied
# on top, so the same handlers are reachable at both URL spaces
# simultaneously. The DeprecationHeadersMiddleware then tags every
# response that landed on the old prefix with the deprecation headers.
from app.modules.platform_controls.routes import router as _canonical_router

router = APIRouter(
    prefix="/voice-control",
    tags=["voice-control (deprecated)"],
)

# The canonical router's `router` is a FastAPI APIRouter; we include
# every route it ships under the deprecated prefix. This is the
# "delegating alias" pattern from doc §6.2 but in a single, maintainable
# line: every future route added to the canonical router is automatically
# available here, with no per-handler code in the shim.
router.include_router(_canonical_router)
