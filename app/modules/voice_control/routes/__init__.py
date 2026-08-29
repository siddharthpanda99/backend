"""app.modules.voice_control.routes — Deprecated router (BC shim).

.. deprecated::
    Mounted at ``/api/v1/voice-control/`` (per
    ``Backend/app/core/routers.py`` ``ROUTER_DEFINITIONS``). Use
    ``/api/v1/platform-controls/`` instead. See
    ``common_lib/modules/platform_controls/docs/11_migration_from_voice_control.md``
    §6 for the shim contract.

Re-exports the canonical :mod:`app.modules.platform_controls.routes.router`
under the old import path. The :class:`DeprecationHeadersMiddleware`
(see :mod:`app.modules.voice_control.middleware`) is registered in
``app/main.py`` and adds the ``Deprecation: true`` + ``Sunset: <date>``
response headers to every old-URL response.
"""

from app.modules.voice_control.routes.router import router

__all__ = ["router"]
