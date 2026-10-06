"""Regression guard: `app.main` must import and mount its API routes.

Why this exists
---------------
`app.main` is assembled through a long lazy-import chain. A single missing or
renamed import deep in that chain (for example `core_infrastructure.registry`
raising at import time) makes `app.main` unimportable, which means NO route is
mounted and the whole application is dead. Because routers are registered
dynamically from `ROUTER_DEFINITIONS`, that failure is silent until someone
actually boots the app -- which is why agents kept hand-mounting single routers
to work around it.

These tests assert the real thing: the module imports in a fresh process, the
route table is populated, and a request through the ASGI app gets a real
status code. They deliberately do NOT require a database (they do not run the
lifespan), so a missing Postgres cannot mask an import regression.

Deliberately NOT used here: `raise_server_exceptions=False`. That flag converts
a genuine boot failure into a false green, which is the opposite of what this
guard is for.
"""

import pytest


@pytest.fixture(scope="module")
def app_obj():
    """Import `app.main` once. A failure here IS the regression we guard against."""
    from app.main import app

    return app


def test_main_imports_without_import_error(app_obj):
    """`from app.main import app` must succeed in a fresh process."""
    assert app_obj is not None
    assert hasattr(app_obj, "routes")


def test_route_table_is_populated(app_obj):
    """The route table must be non-empty -- a mounted app has thousands of routes."""
    assert len(app_obj.routes) > 1


def test_api_v1_paths_are_actually_mounted(app_obj):
    """Routers must be MOUNTED in `app.routes`, not merely registered in ROUTER_DEFINITIONS.

    Reading the registry would pass even when `include_router` never ran, so this
    asserts against the real route table.
    """
    paths = {getattr(r, "path", None) for r in app_obj.routes}
    assert any(p.startswith("/api/v1") for p in paths if p), (
        "no /api/v1 paths present in app.routes -- routers were not mounted"
    )


@pytest.mark.parametrize(
    "path",
    ["/api/v1/health", "/api/v1/auth/login"],
)
def test_core_routes_are_present(app_obj, path):
    """Spot-check specific well-known routes are in the mounted table."""
    paths = {getattr(r, "path", None) for r in app_obj.routes}
    assert path in paths


def test_health_returns_real_200(app_obj):
    """A real request through the ASGI app returns a real status, not a hang/500."""
    import anyio
    from httpx import ASGITransport, AsyncClient

    async def _get():
        # NOTE: no raise_server_exceptions=False -- see module docstring.
        transport = ASGITransport(app=app_obj)
        async with AsyncClient(transport=transport, base_url="http://testserver") as c:
            return await c.get("/api/v1/health")

    resp = anyio.run(_get)
    assert resp.status_code == 200
    assert "online" in resp.text.lower()


def test_bad_route_returns_404_not_200(app_obj):
    """A server that answers 200 to everything has NOT booted correctly."""
    import anyio
    from httpx import ASGITransport, AsyncClient

    async def _get():
        transport = ASGITransport(app=app_obj)
        async with AsyncClient(transport=transport, base_url="http://testserver") as c:
            return await c.get("/api/v1/__definitely_not_a_real_route__")

    resp = anyio.run(_get)
    assert resp.status_code == 404
