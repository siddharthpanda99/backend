"""API version middleware — resolves version from header/query and injects
it into ``request.state`` for app-wide use.

Usage
-----
Register on any FastAPI app::

    from app.modules.integration.routes.middleware import ApiVersionMiddleware

    app.add_middleware(ApiVersionMiddleware)

Handlers then access the version via the provided dependency::

    from app.modules.integration.routes.middleware import get_api_version

    @router.get("/my-endpoint")
    async def handler(api_version: str = Depends(get_api_version)):
        ...

Or directly from ``request.state``::

    version = request.state.api_version  # "v1" default
"""

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

from app.modules.integration.routes.versioning import validate_version


__all__ = [
    "ApiVersionMiddleware",
    "get_api_version",
]


class ApiVersionMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware that resolves the API version from
    ``Accept-Version`` header or ``?version=`` query parameter and stores
    the resolved value in ``request.state.api_version``.

    Resolution priority
    -------------------
    1. ``Accept-Version`` header (e.g. ``Accept-Version: v2``)
    2. ``?version=`` query parameter (e.g. ``?version=v2``)
    3. ``"v1"`` (default)

    Invalid version values produce a ``400`` JSON response before the
    handler runs, and the ``"latest"`` alias is resolved to ``"v1"``.

    Register on your FastAPI app::

        app.add_middleware(ApiVersionMiddleware)

    .. note::

       ``BaseHTTPMiddleware`` does **not** route exceptions raised inside
       ``dispatch()`` through FastAPI's exception handlers. We catch
       ``HTTPException`` explicitly and return a ``JSONResponse``.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        try:
            version = (
                request.headers.get("Accept-Version")
                or request.query_params.get("version")
                or "v1"
            )
            validate_version(version)
            if version == "latest":
                version = "v1"
            request.state.api_version = version
        except HTTPException as exc:
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.detail},
            )
        return await call_next(request)


def get_api_version(request: Request) -> str:
    """FastAPI dependency that extracts the resolved API version from
    ``request.state.api_version`` (set by :class:`ApiVersionMiddleware`).

    Falls back to ``\"v1\"`` when the middleware has not been registered,
    making it safe to use in both middleware-enabled and minimal test apps.
    """
    return getattr(request.state, "api_version", "v1")
