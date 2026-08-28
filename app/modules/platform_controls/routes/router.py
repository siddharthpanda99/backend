"""Phase 0 router for the Universal Platform Control Framework.

Thin handler. ALL business logic lives in
``common_lib.modules.platform_controls.service.PlatformControlService``.

Phase 0 endpoints:
  - ``GET /api/v1/platform-controls/health`` — unauthenticated.
    Returns the same dict as
    ``PlatformControlService().health()``. The router itself does
    no processing — it is a one-line delegate. The shape of the
    response is owned by the service (per docs/14 §3: never leak
    user data; only status + version).

Per docs/14 §3, ``/health`` is the ONE endpoint that is unauthenticated
in the whole framework — every other endpoint added in later phases
requires a JWT bearer (and the admin / audit endpoints require the
``platform:voice:admin`` scope on top of the JWT). Phase 0 has
nothing else, so there is no auth wiring yet.

The endpoint is mounted at prefix ``/api/v1/platform-controls`` via
``Backend/app/core/routers.py`` ``ROUTER_DEFINITIONS``.
"""

from __future__ import annotations

from fastapi import APIRouter

from common_lib.modules.platform_controls import (
    PlatformControlService,
    __version__,
)


router = APIRouter()


@router.get(
    "/health",
    summary="Platform Controls health probe (Phase 0 skeleton).",
    description=(
        "Returns ``{status, version}``. ``status`` is ``'skeleton'`` when the "
        "master feature flag ``platform_controls.enabled`` is on, "
        "``'disabled'`` when it is off. No auth required "
        "(load-balancer probe). The shape of the body is owned by "
        "``common_lib.modules.platform_controls.service.PlatformControlService.health``."
    ),
    # Note: NO `dependencies=` here. The router is registered in
    # ``ROUTER_DEFINITIONS`` with ``auth=False`` so the global auth
    # dependency is not applied. Per docs/14 §3, /health is the only
    # public endpoint in the framework.
    tags=["Platform Controls"],
    response_model=None,  # the shape is a plain dict
)
def health() -> dict[str, str]:
    """One-line delegate to the service.

    Per the be-rules-boundary invariant: the router contains no
    business logic. It constructs a service instance (cheap in
    Phase 0 — no DI container yet) and returns its result.
    """
    return PlatformControlService().health()


# Re-export the version at the module level so an OpenAPI tag or a
# future ``/version`` endpoint can import it without re-traversing the
# package tree.
__all__ = ["router", "__version__"]
