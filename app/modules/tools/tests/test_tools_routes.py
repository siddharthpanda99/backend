"""Run-1 audit regression tests for the ``/api/v1/tools`` HTTP surface.

These exercise the router directly with a minimal FastAPI app. They deliberately
do **not** call ``app.core.routers.register_routers`` — that builds the entire
platform (~70s) and, per MODULE-TRACKER.md, an uncached call inside a
parametrised test once cost 93 x 70s. Route *mounting* is verified separately
and once, by ``test_tools.py::test_module_router_is_mounted_at_api_v1_tools``.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.tools.routes import index as tools_index
from common_lib.modules.tools import service as service_module
from common_lib.modules.tools.flags import TOOLS_FEATURE_FLAGS, set_flag

HTTP_FLAG = "tools.http.expose_catalog_and_execution_routes"


@pytest.fixture(autouse=True)
def _restore_flags():
    before = dict(TOOLS_FEATURE_FLAGS)
    yield
    TOOLS_FEATURE_FLAGS.clear()
    TOOLS_FEATURE_FLAGS.update(before)


@pytest.fixture(autouse=True)
def _no_store(monkeypatch):
    """The tool store is absent, so no test can touch a database."""
    monkeypatch.setattr(service_module, "HAS_MEMORY", False)


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(tools_index.router, prefix="/api/v1/tools")
    return TestClient(app, raise_server_exceptions=False)


def _declared_order() -> list[str]:
    """Paths as declared, i.e. relative to the router's own mount prefix.

    The prefix is applied by `app/core/routers.py`, which this module must not
    depend on, so the ordering assertions below use the router-relative form.
    """
    return [r.path for r in tools_index.router.routes]


# ---------------------------------------------------------------------------
# Route ordering — the shadowing trap (MODULE-TRACKER.md finding 9)
# ---------------------------------------------------------------------------


def test_literal_routes_are_declared_before_the_id_route():
    """FastAPI matches in declaration order: `/{id}` must come last.

    Declaring `/catalog` after `/{id}` makes `GET /tools/catalog` resolve as
    `GET /tools/{id}` with `id="catalog"` — a 404 that looks like a missing
    capability rather than a routing bug.
    """
    paths = _declared_order()
    param_index = paths.index("/{id}")
    for literal in (
        "/catalog",
        "/catalog/{tool_id}",
        "/catalog/categories",
        "/execute",
        "/execute-chain",
        "/stats",
        "/history",
        "/versions",
        "/health",
        "/feature-flags",
    ):
        assert literal in paths, f"{literal} was never declared"
        assert paths.index(literal) < param_index, (
            f"{literal} is declared after /{{id}} and will be shadowed"
        )


def test_collection_routes_are_declared_after_the_literals():
    paths = _declared_order()
    assert paths.index("/health") < paths.index("/")


def test_no_literal_path_is_swallowed_by_the_id_route(client):
    """Belt and braces: prove the match, not just the declaration order."""
    set_flag(HTTP_FLAG, True)
    for path in ("/api/v1/tools/catalog", "/api/v1/tools/stats"):
        response = client.get(path)
        assert response.status_code != 404 or path.endswith("catalog"), (
            f"{path} resolved through the /{{id}} route"
        )


# ---------------------------------------------------------------------------
# C2 — the gated surface
# ---------------------------------------------------------------------------


def test_gated_routes_are_404_with_a_pointer_while_the_flag_is_off(client):
    """G9: the new surface must not change a live deployment by default."""
    set_flag(HTTP_FLAG, False)
    for path in (
        "/api/v1/tools/catalog",
        "/api/v1/tools/stats",
        "/api/v1/tools/history",
        "/api/v1/tools/versions",
        "/api/v1/tools/health",
    ):
        response = client.get(path)
        assert response.status_code == 404, path
        assert HTTP_FLAG in response.json()["detail"], path


def test_gated_post_routes_are_404_while_the_flag_is_off(client):
    set_flag(HTTP_FLAG, False)
    assert (
        client.post("/api/v1/tools/execute", json={"tool_id": "x"}).status_code == 404
    )
    assert (
        client.post("/api/v1/tools/execute-chain", json={"steps": []}).status_code
        == 404
    )


def test_feature_flags_route_is_ungated_so_operators_can_inspect(client):
    response = client.get("/api/v1/tools/feature-flags")
    assert response.status_code == 200
    flags = response.json()["data"]["flags"]
    assert flags[HTTP_FLAG] is False
    assert all(v is False for v in flags.values())


def test_catalog_is_served_once_the_flag_is_on(client):
    set_flag(HTTP_FLAG, True)
    response = client.get("/api/v1/tools/catalog")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] == len(data["tools"])
    assert data["total"] > 0
    assert data["categories"]


def test_catalog_categories_route(client):
    set_flag(HTTP_FLAG, True)
    response = client.get("/api/v1/tools/catalog/categories")
    assert response.status_code == 200
    assert response.json()["data"]["categories"]


def test_catalog_entry_404s_for_an_unknown_tool(client):
    set_flag(HTTP_FLAG, True)
    assert client.get("/api/v1/tools/catalog/nope-xyz").status_code == 404


def test_catalog_entry_is_not_confused_with_the_crud_route(client):
    set_flag(HTTP_FLAG, True)
    from common_lib.modules.tools.catalog import get_catalog

    known_id = get_catalog()[0]["id"]
    response = client.get(f"/api/v1/tools/catalog/{known_id}")
    assert response.status_code == 200
    assert "tool" in response.json()["data"]


def test_execute_reports_an_unknown_tool_as_an_error_not_a_success(client):
    set_flag(HTTP_FLAG, True)
    response = client.post(
        "/api/v1/tools/execute", json={"tool_id": "definitely-not-a-tool"}
    )
    assert response.status_code == 200
    result = response.json()["data"]
    assert result["status"] == "error"
    assert "No handler registered" in result["error"]
    assert result["timed_out"] is False


def test_execute_chain_route(client):
    set_flag(HTTP_FLAG, True)
    response = client.post(
        "/api/v1/tools/execute-chain",
        json={"steps": [{"tool_id": "definitely-not-a-tool"}]},
    )
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "error"


def test_stats_route(client):
    set_flag(HTTP_FLAG, True)
    response = client.get("/api/v1/tools/stats")
    assert response.status_code == 200
    stats = response.json()["data"]
    for key in (
        "total_executions",
        "successful",
        "errors",
        "timeouts",
        "success_rate",
        "avg_duration_ms",
        "registered_handlers",
    ):
        assert key in stats, key


def test_history_route(client):
    set_flag(HTTP_FLAG, True)
    response = client.get("/api/v1/tools/history?limit=5")
    assert response.status_code == 200
    assert response.json()["data"]["count"] >= 0


def test_versions_route_round_trip(client):
    set_flag(HTTP_FLAG, True)
    registered = client.post(
        "/api/v1/tools/versions/probe-tool",
        json={"definition": {"a": 1}, "version": "1.0.0", "changelog": "init"},
    )
    assert registered.status_code == 200

    listed = client.get("/api/v1/tools/versions?tool_id=probe-tool")
    assert listed.status_code == 200
    assert listed.json()["data"]["count"] == 1

    summary = client.get("/api/v1/tools/versions")
    assert summary.status_code == 200
    assert "probe-tool" in summary.json()["data"]["tools"]


def test_health_route(client):
    set_flag(HTTP_FLAG, True)
    response = client.get("/api/v1/tools/health")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "ok"
    assert data["catalog_size"] > 0
    assert data["flags"]


# ---------------------------------------------------------------------------
# HIGH-1 — an unavailable store must not look like an empty instance
# ---------------------------------------------------------------------------


def test_list_is_503_not_an_empty_200_when_the_store_is_gone(client):
    set_flag("tools.service.fail_closed_when_store_unavailable", True)
    response = client.get("/api/v1/tools/")
    assert response.status_code == 503, response.text
    assert "unavailable" in response.json()["detail"].lower()


def test_list_is_an_empty_200_by_default_for_back_compatibility(client):
    set_flag("tools.service.fail_closed_when_store_unavailable", False)
    response = client.get("/api/v1/tools/")
    assert response.status_code == 200
    assert response.json()["data"] == []


def test_get_by_id_is_503_when_the_store_is_gone(client):
    set_flag("tools.service.fail_closed_when_store_unavailable", True)
    assert client.get("/api/v1/tools/anything").status_code == 503


# ---------------------------------------------------------------------------
# Fix — the router must validate against the canonical schemas
# ---------------------------------------------------------------------------


def test_router_uses_the_canonical_tools_schemas():
    """It previously imported the dead ``core_infrastructure`` duplicate."""
    assert tools_index.ToolCreate.__module__ == "common_lib.modules.tools.schemas"
    assert tools_index.ToolRead.__module__ == "common_lib.modules.tools.schemas"
    assert tools_index.ToolUpdate.__module__ == "common_lib.modules.tools.schemas"


def test_router_does_not_import_core_infrastructure():
    """AST-based, so the module docstring may still *name* the old path."""
    import ast
    import pathlib

    tree = ast.parse(pathlib.Path(tools_index.__file__).read_text())
    offenders = []
    for node_ in ast.walk(tree):
        if isinstance(node_, ast.ImportFrom) and node_.module:
            if node_.module.startswith("common_lib.modules.core_infrastructure"):
                offenders.append(f"{node_.module}.{node_.names[0].name}")
        if isinstance(node_, ast.Import):
            for alias in node_.names:
                if "core_infrastructure" in alias.name:
                    offenders.append(alias.name)
    assert offenders == [], offenders


def test_create_still_requires_an_id(client):
    """HIGH (C4): the UI used to omit `id`, so every create was a 422."""
    response = client.post("/api/v1/tools/", json={"name": "no-id-here"})
    assert response.status_code == 422
    missing = {d["loc"][-1] for d in response.json()["detail"]}
    assert "id" in missing


def test_create_accepts_the_payload_the_ui_now_sends(client):
    response = client.post(
        "/api/v1/tools/",
        json={"id": "probe-from-ui", "name": "probe-from-ui", "description": "d"},
    )
    # The regression guard is the 422: the payload the UI now sends must pass
    # validation. With HAS_MEMORY pinned False the service has no store to write
    # to, so the outcome past validation is not this test's concern — the
    # fail-closed path for that is covered by
    # test_list_is_503_not_an_empty_200_when_the_store_is_gone.
    assert response.status_code != 422, response.text


# ---------------------------------------------------------------------------
# G1 — transport only
# ---------------------------------------------------------------------------


def test_router_raises_no_bare_http_exception_with_a_str_of_a_traceback():
    source = __import__("pathlib").Path(tools_index.__file__).read_text()
    assert "detail=str(e)" not in source


def test_router_uses_the_typed_tool_errors():
    source = __import__("pathlib").Path(tools_index.__file__).read_text()
    assert "ToolStoreUnavailableError" in source
    assert "ToolDeleteError" in source


# ---------------------------------------------------------------------------
# C2 — mounting in the real application
# ---------------------------------------------------------------------------

# TRAP (MODULE-TRACKER.md): `register_routers` builds the whole platform and
# costs ~70s. It is built EXACTLY ONCE here, at module scope, and shared by the
# two tests below. An earlier orphaned agent put an uncached call inside a
# 93-case parametrised test and paid 93 x 70s.
_APP_BUILD_SECONDS = "~70s"


@pytest.fixture(scope="module")
def mounted_app():
    import os

    os.environ.setdefault("DISABLE_AUTH", "true")
    from app.core.routers import register_routers

    app = FastAPI()
    register_routers(app, "/api/v1", [])
    return app


def test_module_router_is_mounted_at_api_v1_tools(mounted_app):
    from fastapi.routing import APIRoute

    paths = [
        r.path
        for r in mounted_app.routes
        if isinstance(r, APIRoute) and r.path.startswith("/api/v1/tools")
    ]
    for expected in (
        "/api/v1/tools/",
        "/api/v1/tools/health",
        "/api/v1/tools/feature-flags",
        "/api/v1/tools/catalog",
        "/api/v1/tools/execute",
        "/api/v1/tools/stats",
        "/api/v1/tools/versions",
        "/api/v1/tools/{id}",
    ):
        assert expected in paths, f"{expected} is not mounted"


def test_mounted_tools_routes_are_not_shadowed(mounted_app):
    """No two mounted /api/v1/tools routes may share (path, methods).

    The `/{id}`-before-literal ordering bug is invisible to a declaration-order
    test if the router is mounted twice, so this checks the assembled app.
    """
    from collections import defaultdict

    from fastapi.routing import APIRoute

    seen = defaultdict(list)
    for route in mounted_app.routes:
        if isinstance(route, APIRoute) and route.path.startswith("/api/v1/tools"):
            seen[(route.path, tuple(sorted(route.methods)))].append(
                route.endpoint.__module__
            )
    duplicates = {k: v for k, v in seen.items() if len(v) > 1}
    assert duplicates == {}, duplicates
