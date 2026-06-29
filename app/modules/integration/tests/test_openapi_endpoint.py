"""TestClient tests for /api/v1/integration/openapi.json and /health endpoints.

Uses a fixture-based minimal FastAPI app with only the integration router
mounted — no database connection or full app lifespan required.

Verifies:
  - /health — status, served versions, latest alias
  - /openapi.json — 200 status, valid OpenAPI structure
  - Version-prefixed paths (/v1/openapi.json, /v2/openapi.json)
  - Query parameter versioning (?version=v2, ?version=latest)
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def app() -> FastAPI:
    """Create a minimal FastAPI app with the integration router mounted and
    ``ApiVersionMiddleware`` registered."""
    from app.modules.integration.routes import router
    from app.modules.integration.routes.middleware import ApiVersionMiddleware

    _app = FastAPI()
    _app.include_router(router, prefix="/api/v1")
    _app.add_middleware(ApiVersionMiddleware)
    return _app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """Sync TestClient for the minimal integration app."""
    return TestClient(app)


# ── Health / Version Info ────────────────────────────────────────────────────


class TestHealthEndpoint:
    """GET /api/v1/integration/health — version info for all served API versions."""

    def test_health_returns_200(self, client: TestClient):
        """Should return 200."""
        response = client.get("/api/v1/integration/health")
        assert response.status_code == 200

    def test_health_has_status_ok(self, client: TestClient):
        """Should report status ok."""
        body = client.get("/api/v1/integration/health").json()
        assert body["status"] == "ok"
        assert body["service"] == "integration"

    def test_health_lists_all_versions(self, client: TestClient):
        """Should list v1 and v2 with their semver mappings."""
        versions = client.get("/api/v1/integration/health").json()["versions"]
        assert "v1" in versions
        assert "v2" in versions
        assert versions["v1"]["version"] == "1.0.0"
        assert versions["v2"]["version"] == "2.0.0"

    def test_health_reports_openapi_paths(self, client: TestClient):
        """Each version should list its OpenAPI endpoint path."""
        versions = client.get("/api/v1/integration/health").json()["versions"]
        for label, info in versions.items():
            path = info.get("openapi_path")
            assert path is not None
            assert path.startswith("/api/v1/integration/")
            assert label.replace("v", "") in path

    def test_health_reports_latest_alias(self, client: TestClient):
        """Should report which version is 'latest'."""
        body = client.get("/api/v1/integration/health").json()
        assert body["latest"] == "v1"

    def test_health_v1_path_resolves_to_spec(self, client: TestClient):
        """The v1 openapi_path reported by health should return a valid spec."""
        body = client.get("/api/v1/integration/health").json()
        v1_path = body["versions"]["v1"]["openapi_path"]
        spec = client.get(v1_path).json()
        assert spec["info"]["version"] == "1.0.0"

    def test_health_v2_path_resolves_to_spec(self, client: TestClient):
        """The v2 openapi_path reported by health should return a valid spec."""
        body = client.get("/api/v1/integration/health").json()
        v2_path = body["versions"]["v2"]["openapi_path"]
        spec = client.get(v2_path).json()
        assert spec["info"]["version"] == "2.0.0"


# ── Base endpoint ──────────────────────────────────────────────────────────


class TestBaseEndpoint:
    """GET /api/v1/integration/openapi.json — spec structure."""

    def test_returns_200(self, client: TestClient):
        """Should return 200."""
        response = client.get("/api/v1/integration/openapi.json")
        assert response.status_code == 200

    def test_has_openapi_field(self, client: TestClient):
        """Response should include the 'openapi' version field."""
        spec = client.get("/api/v1/integration/openapi.json").json()
        assert "openapi" in spec
        assert spec["openapi"].startswith("3.0")

    def test_has_info(self, client: TestClient):
        """Response should include an 'info' section with title and version."""
        info = client.get("/api/v1/integration/openapi.json").json()["info"]
        assert "title" in info
        assert "version" in info
        assert info["version"] == "1.0.0"

    def test_has_paths(self, client: TestClient):
        """Response should include a 'paths' section with tool endpoints."""
        paths = client.get("/api/v1/integration/openapi.json").json()["paths"]
        assert len(paths) >= 6
        assert "/tools/rip-search" in paths
        assert "/tools/rip-chunk" in paths

    def test_has_components(self, client: TestClient):
        """Response should include 'components.schemas' with tool param schemas."""
        schemas = client.get("/api/v1/integration/openapi.json").json()[
            "components"
        ]["schemas"]
        assert "rip_search_params" in schemas
        assert "ToolResult" in schemas


# ── Version-prefixed paths ────────────────────────────────────────────────


class TestVersionedPaths:
    """GET /api/v1/integration/v{1,2}/openapi.json — version-prefixed."""

    def test_v1_path_returns_200(self, client: TestClient):
        """/v1/openapi.json should return 200 with version 1.0.0."""
        spec = client.get("/api/v1/integration/v1/openapi.json").json()
        assert spec["info"]["version"] == "1.0.0"

    def test_v2_path_returns_200(self, client: TestClient):
        """/v2/openapi.json should return 200 with version 2.0.0."""
        spec = client.get("/api/v1/integration/v2/openapi.json").json()
        assert spec["info"]["version"] == "2.0.0"

    def test_v2_has_different_description(self, client: TestClient):
        """v2 endpoint should have a distinct description from v1."""
        r1 = client.get("/api/v1/integration/v1/openapi.json")
        r2 = client.get("/api/v1/integration/v2/openapi.json")
        assert r1.json()["info"]["description"] != r2.json()["info"]["description"]
        assert "v2" in r2.json()["info"]["description"].lower()

    def test_v2_has_v2_server_urls(self, client: TestClient):
        """v2 server URLs should reference /v2."""
        for server in client.get("/api/v1/integration/v2/openapi.json").json()[
            "servers"
        ]:
            assert "/v2" in server["url"]

    def test_v1_and_v2_have_same_paths(self, client: TestClient):
        """v1 and v2 should have the same tool paths (same tools, different version)."""
        r1 = client.get("/api/v1/integration/v1/openapi.json")
        r2 = client.get("/api/v1/integration/v2/openapi.json")
        assert r1.json()["paths"].keys() == r2.json()["paths"].keys()


# ── Query parameter versioning ────────────────────────────────────────────


class TestQueryVersioning:
    """GET /api/v1/integration/openapi.json?version=... — query param versioning."""

    def test_version_v2(self, client: TestClient):
        """?version=v2 should return version 2.0.0."""
        response = client.get("/api/v1/integration/openapi.json?version=v2")
        assert response.status_code == 200
        assert response.json()["info"]["version"] == "2.0.0"

    def test_version_latest(self, client: TestClient):
        """?version=latest should return version 1.0.0 (same as default)."""
        response = client.get("/api/v1/integration/openapi.json?version=latest")
        assert response.status_code == 200
        assert response.json()["info"]["version"] == "1.0.0"

    def test_version_explicit_semver(self, client: TestClient):
        """?version=2.0.0 should return version 2.0.0."""
        response = client.get("/api/v1/integration/openapi.json?version=2.0.0")
        assert response.status_code == 200
        assert response.json()["info"]["version"] == "2.0.0"


# ── Accept-Version header negotiation ────────────────────────────────────


class TestAcceptVersionHeader:
    """GET /api/v1/integration/openapi.json via Accept-Version header."""

    def test_header_v2_returns_v2(self, client: TestClient):
        """Accept-Version: v2 should return version 2.0.0."""
        response = client.get(
            "/api/v1/integration/openapi.json",
            headers={"Accept-Version": "v2"},
        )
        assert response.status_code == 200
        assert response.json()["info"]["version"] == "2.0.0"

    def test_header_latest_returns_v1(self, client: TestClient):
        """Accept-Version: latest should return version 1.0.0."""
        response = client.get(
            "/api/v1/integration/openapi.json",
            headers={"Accept-Version": "latest"},
        )
        assert response.status_code == 200
        assert response.json()["info"]["version"] == "1.0.0"

    def test_header_explicit_semver(self, client: TestClient):
        """Accept-Version: 2.0.0 should return version 2.0.0."""
        response = client.get(
            "/api/v1/integration/openapi.json",
            headers={"Accept-Version": "2.0.0"},
        )
        assert response.status_code == 200
        assert response.json()["info"]["version"] == "2.0.0"

    def test_header_precedes_query_param(self, client: TestClient):
        """Accept-Version header should take precedence over ?version query param.

        When both are provided, the header value wins.
        """
        response = client.get(
            "/api/v1/integration/openapi.json?version=v2",
            headers={"Accept-Version": "v1"},
        )
        # Header says v1, so we should get 1.0.0 even though query says v2
        assert response.status_code == 200
        assert response.json()["info"]["version"] == "1.0.0"

    def test_header_v2_via_health_path(self, client: TestClient):
        """Accept-Version header should also work on the v2 path (no-op for fixed path)."""
        # The /v2/openapi.json is a fixed path — it always returns v2 regardless
        response = client.get(
            "/api/v1/integration/v2/openapi.json",
            headers={"Accept-Version": "v1"},
        )
        assert response.status_code == 200
        # Fixed path ignores header — always v2
        assert response.json()["info"]["version"] == "2.0.0"

    def test_header_no_header_falls_back_to_default(self, client: TestClient):
        """Without Accept-Version header or ?version param, defaults to v1."""
        response = client.get("/api/v1/integration/openapi.json")
        assert response.status_code == 200
        assert response.json()["info"]["version"] == "1.0.0"


# ── Accept-Version on service endpoints ────────────────────────────────────


class TestServiceEndpointVersioning:
    """Accept-Version header negotiation on service endpoints.

    All read-only service endpoints should:
      - Accept the ``Accept-Version`` header
      - Reflect the negotiated version in ``api_version`` response field
      - Return 400 for invalid versions
      - Default to  ``"v1"`` when no header is present
    """

    SERVICE_ENDPOINTS = [
        "/api/v1/integration/health",
        "/api/v1/integration/status",
        "/api/v1/integration/events/history",
        "/api/v1/integration/events/rules",
        "/api/v1/integration/triggers",
        "/api/v1/integration/triggers/stats",
        "/api/v1/integration/rules/stats",
        "/api/v1/integration/hooks/stats",
        "/api/v1/integration/notifications/stats",
        "/api/v1/integration/observability/metrics",
        "/api/v1/integration/observability/alerts",
        "/api/v1/integration/memory/bridge/stats",
    ]

    def test_default_version_is_v1(self, client: TestClient):
        """All service endpoints default to api_version v1."""
        for path in self.SERVICE_ENDPOINTS:
            resp = client.get(path)
            assert resp.status_code == 200, f"{path} should return 200"
            body = resp.json()
            assert body.get("api_version") == "v1", f"{path} should default to v1, got {body.get('api_version')}"

    def test_header_v2_returns_v2(self, client: TestClient):
        """Accept-Version: v2 is reflected in api_version."""
        for path in self.SERVICE_ENDPOINTS:
            resp = client.get(path, headers={"Accept-Version": "v2"})
            assert resp.status_code == 200, f"{path} should return 200 with Accept-Version: v2"
            assert resp.json().get("api_version") == "v2", f"{path} should reflect v2"

    def test_header_latest_returns_v1(self, client: TestClient):
        """Accept-Version: latest maps to api_version v1."""
        for path in self.SERVICE_ENDPOINTS:
            resp = client.get(path, headers={"Accept-Version": "latest"})
            assert resp.status_code == 200, f"{path} should return 200 with Accept-Version: latest"
            assert resp.json().get("api_version") == "v1", f"{path} latest should resolve to v1"

    def test_header_invalid_returns_400(self, client: TestClient):
        """Invalid Accept-Version returns 400 on all service endpoints."""
        for path in self.SERVICE_ENDPOINTS:
            resp = client.get(path, headers={"Accept-Version": "not-a-real-version"})
            assert resp.status_code == 400, (
                f"{path} should return 400 for invalid Accept-Version, got {resp.status_code}"
            )
            assert "valid" in resp.json()["detail"].lower()

    def test_traces_endpoints_accept_header(self, client: TestClient):
        """Trace endpoints (list + detail) also support Accept-Version."""
        # List traces
        resp = client.get("/api/v1/integration/traces", headers={"Accept-Version": "v2"})
        assert resp.status_code == 200
        assert resp.json().get("api_version") == "v2"

        # Get specific trace — should 404 (no trace exists)
        # NOTE: 404 responses come from HTTPException, which is serialised
        # by FastAPI's default handler as {"detail": ...} without api_version.
        resp = client.get("/api/v1/integration/traces/nonexistent", headers={"Accept-Version": "v2"})
        assert resp.status_code == 404
        assert "not found" in resp.json().get("detail", "").lower()

    def test_query_version_v2_returns_v2(self, client: TestClient):
        """?version=v2 query param is reflected in api_version on service endpoints."""
        for path in self.SERVICE_ENDPOINTS:
            resp = client.get(f"{path}?version=v2")
            assert resp.status_code == 200, f"{path}?version=v2 should return 200"
            assert resp.json().get("api_version") == "v2", f"{path} should reflect v2 from query"

    def test_query_param_precedence(self, client: TestClient):
        """?version=v2 works but Accept-Version header takes precedence."""
        for path in self.SERVICE_ENDPOINTS:
            resp = client.get(f"{path}?version=v2", headers={"Accept-Version": "v1"})
            assert resp.status_code == 200, f"{path} with conflicting params should return 200"
            # Header says v1, so api_version should be v1 even though query says v2
            assert resp.json().get("api_version") == "v1", (
                f"{path}: Accept-Version header should take precedence over query"
            )

    def test_query_version_invalid_returns_400(self, client: TestClient):
        """?version=bad via query param returns 400 on service endpoints."""
        for path in self.SERVICE_ENDPOINTS:
            resp = client.get(f"{path}?version=bad")
            assert resp.status_code == 400, f"{path}?version=bad should return 400"
            assert "valid" in resp.json()["detail"].lower()

    def test_write_endpoints_do_not_require_header(self, client: TestClient):
        """POST write endpoints work without Accept-Version (they don't use the dependency)."""
        # Fire event — requires a valid body, but should still work without version header
        resp = client.post(
            "/api/v1/integration/events/fire",
            json={"event_type": "test", "data": {}},
        )
        # Should either succeed or fail gracefully, not crash
        assert resp.status_code in (200, 422, 500), f"Unexpected status: {resp.status_code}"

        # Observability reset
        resp = client.post("/api/v1/integration/observability/reset")
        assert resp.status_code in (200, 500), f"Unexpected status: {resp.status_code}"


# ── Negative tests — invalid versions ───────────────────────────────────────


class TestInvalidVersions:
    """Invalid version values should return 400, not crash or silently pass through."""

    def test_query_version_bad_returns_400(self, client: TestClient):
        """?version=bad should return 400 with a useful error message."""
        response = client.get("/api/v1/integration/openapi.json?version=bad")
        assert response.status_code == 400
        body = response.json()
        assert "detail" in body
        assert "bad" in body["detail"]
        assert "valid" in body["detail"].lower()

    def test_query_version_empty_returns_400(self, client: TestClient):
        """?version= (empty) should return 400."""
        response = client.get("/api/v1/integration/openapi.json?version=")
        assert response.status_code == 400

    def test_query_version_garbage_returns_400(self, client: TestClient):
        """?version=!@#$ should return 400."""
        response = client.get("/api/v1/integration/openapi.json?version=!@#$%")
        assert response.status_code == 400

    def test_header_bad_version_returns_400(self, client: TestClient):
        """Accept-Version: bad should return 400 with a useful error message."""
        response = client.get(
            "/api/v1/integration/openapi.json",
            headers={"Accept-Version": "nonexistent"},
        )
        assert response.status_code == 400
        body = response.json()
        assert "detail" in body
        assert "nonexistent" in body["detail"]

    def test_valid_versions_are_not_rejected(self, client: TestClient):
        """All known version aliases should return 200, not 400."""
        for v in ["v1", "v2", "latest", "1.0.0", "2.0.0"]:
            response = client.get(f"/api/v1/integration/openapi.json?version={v}")
            assert response.status_code == 200, f"version={v} should be valid"


# ── ApiVersionMiddleware + get_api_version extractor ───────────────────────


class TestApiVersionMiddleware:
    """Tests that the ``ApiVersionMiddleware`` correctly resolves the version
    from header/query/default and that the ``get_api_version`` dependency
    extractor reads from ``request.state``.
    """

    def _make_test_app(self):
        """Create a minimal app with a single handler that uses ``get_api_version``."""
        from fastapi import Depends, FastAPI
        from fastapi.testclient import TestClient
        from app.modules.integration.routes.middleware import (
            ApiVersionMiddleware,
            get_api_version,
        )

        app = FastAPI()
        app.add_middleware(ApiVersionMiddleware)

        @app.get("/version-test")
        async def version_test(api_version: str = Depends(get_api_version)):
            return {"api_version": api_version}

        return TestClient(app)

    def test_default_returns_v1(self):
        """Without any header or query param, defaults to v1."""
        client = self._make_test_app()
        resp = client.get("/version-test")
        assert resp.status_code == 200
        assert resp.json()["api_version"] == "v1"

    def test_header_v2_returns_v2(self):
        """Accept-Version: v2 is reflected."""
        client = self._make_test_app()
        resp = client.get("/version-test", headers={"Accept-Version": "v2"})
        assert resp.status_code == 200
        assert resp.json()["api_version"] == "v2"

    def test_query_version_v2_returns_v2(self):
        """?version=v2 query param is reflected."""
        client = self._make_test_app()
        resp = client.get("/version-test?version=v2")
        assert resp.status_code == 200
        assert resp.json()["api_version"] == "v2"

    def test_header_takes_precedence_over_query(self):
        """Accept-Version header wins over conflicting ?version= query param."""
        client = self._make_test_app()
        resp = client.get(
            "/version-test?version=v2",
            headers={"Accept-Version": "v1"},
        )
        assert resp.status_code == 200
        assert resp.json()["api_version"] == "v1"

    def test_latest_resolves_to_v1(self):
        """header Accept-Version: latest resolves to v1."""
        client = self._make_test_app()
        resp = client.get("/version-test", headers={"Accept-Version": "latest"})
        assert resp.status_code == 200
        assert resp.json()["api_version"] == "v1"

    def test_invalid_version_returns_400(self):
        """Invalid version returns 400 with valid options in detail."""
        client = self._make_test_app()
        resp = client.get("/version-test?version=not-a-real-thing")
        assert resp.status_code == 400
        assert "valid" in resp.json()["detail"].lower()

    def test_middleware_does_not_break_existing_endpoints(self, client: TestClient):
        """Middleware is registered on the integration test app and existing
        endpoints still work correctly."""
        resp = client.get("/api/v1/integration/status")
        assert resp.status_code == 200
        assert resp.json()["api_version"] == "v1"


# ── Integration service endpoints ────────────────────────────────────────────


class TestServiceEndpoints:
    """Integration service endpoints — /status, /events/history, /triggers, etc.

    These endpoints use singletons (get_event_router, get_trigger_manager, …)
    that are created on first call, so they work without the full app lifespan.
    """

    def test_status_returns_200(self, client: TestClient):
        """GET /status should return 200 with module stats."""
        response = client.get("/api/v1/integration/status")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["api_version"] == "v1"
        assert "modules" in body
        assert "event_router" in body["modules"]
        assert "observability" in body["modules"]

    def test_status_has_timestamp(self, client: TestClient):
        """Status response should include a timestamp."""
        body = client.get("/api/v1/integration/status").json()
        assert "timestamp" in body
        assert isinstance(body["timestamp"], float)

    def test_events_history_returns_200(self, client: TestClient):
        """GET /events/history should return 200 with event list."""
        response = client.get("/api/v1/integration/events/history")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["api_version"] == "v1"
        assert "events" in body
        assert "count" in body

    def test_events_history_accepts_limit(self, client: TestClient):
        """/events/history should accept the limit query param."""
        response = client.get("/api/v1/integration/events/history?limit=5")
        assert response.status_code == 200
        assert response.json()["count"] == 5

    def test_events_rules_returns_200(self, client: TestClient):
        """GET /events/rules should return 200 with rules list."""
        response = client.get("/api/v1/integration/events/rules")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["api_version"] == "v1"
        assert "rules" in body

    def test_triggers_returns_200(self, client: TestClient):
        """GET /triggers should return 200 with triggers list."""
        response = client.get("/api/v1/integration/triggers")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["api_version"] == "v1"
        assert "triggers" in body
        assert "count" in body

    def test_triggers_stats_returns_200(self, client: TestClient):
        """GET /triggers/stats should return 200 with stats."""
        response = client.get("/api/v1/integration/triggers/stats")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["api_version"] == "v1"
        assert "stats" in body

    def test_rules_stats_returns_200(self, client: TestClient):
        """GET /rules/stats should return 200."""
        response = client.get("/api/v1/integration/rules/stats")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["api_version"] == "v1"

    def test_hooks_stats_returns_200(self, client: TestClient):
        """GET /hooks/stats should return 200."""
        response = client.get("/api/v1/integration/hooks/stats")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["api_version"] == "v1"
