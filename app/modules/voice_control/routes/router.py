"""Deprecated router — kept for the 6-month BC window (Phase 12 — PR 2).

.. deprecated::
    Mounted at ``/api/v1/voice-control/``. Use
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
which is registered in :mod:`app.main`. Keeping the headers in a
middleware (rather than on every handler) ensures the BC signal is
applied to every old-URL response uniformly, including ones that land on
handlers defined in sub-routers.
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
