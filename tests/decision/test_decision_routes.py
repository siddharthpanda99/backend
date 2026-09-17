"""DF-030 — Backend decision route tests: registration + flag guards."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from common_lib.modules.decision_engine.flags import (
    NEXUS_DECISION_FABRIC_ENABLED,
)
from common_lib.modules.integration.ports.rip_port import get_rip_feature_flag_api
from app.modules.decision.routes import router


@pytest.fixture()
def client():
    app = FastAPI()
    app.include_router(router, prefix="/decision")
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clean_flags():
    api = get_rip_feature_flag_api()
    assert api is not None
    api["clear_all_overrides"]()
    yield
    api["clear_all_overrides"]()


class TestFlagGuards:
    def test_fabric_off_returns_503(self, client):
        response = client.post("/decision/plans", json={"goal": "test goal"})
        assert response.status_code == 503
        assert "NEXUS_DECISION_FABRIC_ENABLED" in response.json()["detail"]

    def test_fabric_on_allows_create(self, client):
        api = get_rip_feature_flag_api()
        api["set_flag_override"](NEXUS_DECISION_FABRIC_ENABLED, True)
        response = client.post("/decision/plans", json={"goal": "analyze contracts"})
        assert response.status_code == 200
        body = response.json()
        assert body["plan_id"]
        assert body["status"] == "REVIEW_REQUIRED"

    def test_create_requires_goal(self, client):
        api = get_rip_feature_flag_api()
        api["set_flag_override"](NEXUS_DECISION_FABRIC_ENABLED, True)
        response = client.post("/decision/plans", json={})
        assert response.status_code == 422

    def test_get_plan_404(self, client):
        api = get_rip_feature_flag_api()
        api["set_flag_override"](NEXUS_DECISION_FABRIC_ENABLED, True)
        response = client.get("/decision/plans/ghost")
        assert response.status_code == 404


class TestEndpointSurface:
    def test_all_9_plan_endpoints_registered(self):
        paths = {route.path for route in router.routes}
        expected = {
            "/plans",
            "/plans/{plan_id}",
            "/plans/{plan_id}/validate",
            "/plans/{plan_id}/approve",
            "/plans/{plan_id}/reject",
            "/plans/{plan_id}/compile",
            "/plans/{plan_id}/execute",
            "/plans/{plan_id}/replan",
        }
        missing = expected - paths
        assert not missing, f"missing endpoints: {missing}"
        # PATCH edit on the plan resource
        methods = {
            (route.path, tuple(sorted(getattr(route, "methods", []) or [])))
            for route in router.routes
        }
        assert any(p == "/plans/{plan_id}" and "PATCH" in m for p, m in methods)

    def test_coordination_endpoints_guarded(self, client):
        response = client.post("/decision/coordination/intake", json={"goal": "x"})
        assert response.status_code == 503  # fabric off → guarded even before coordination flag
