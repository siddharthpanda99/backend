"""Route tests for C041 /rip/acquisition/* (thin delegation, blocked-mode §97)."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.rip.routes.acquisition import router as acquisition_router


@pytest.fixture()
def client():
    app = FastAPI()
    app.include_router(acquisition_router)
    return TestClient(app)


GAP = {"id": "g1", "missing_type": "FACT", "priority": 80, "scope": "KNOWLEDGE_BASE"}
SOURCE = {"id": "kb", "provides": ["FACT"], "authority": 0.9, "scope": "KNOWLEDGE_BASE", "available": True}


class TestPlanRoute:
    def test_plan_returns_ordered_sources(self, client):
        resp = client.post("/rip/acquisition/plan", json={"gaps": [GAP], "sources": [SOURCE]})
        assert resp.status_code == 200
        plans = resp.json()["plans"]
        assert plans[0]["gap_id"] == "g1"
        assert plans[0]["ordered_sources"][0]["candidate_id"] == "kb"

    def test_plan_empty_inputs_ok(self, client):
        resp = client.post("/rip/acquisition/plan", json={})
        assert resp.status_code == 200
        assert resp.json()["plans"] == []


class TestResolveRoute:
    def test_resolve_blocked_mode_explicit(self, client):
        """HTTP transport has no seams → every gap must be explicitly BLOCKED (§97)."""
        resp = client.post("/rip/acquisition/resolve-gaps", json={"gaps": [GAP], "sources": [SOURCE]})
        assert resp.status_code == 200
        result = resp.json()["result"]
        assert result["summary"]["gaps"] == 1
        assert result["summary"]["BLOCKED"] == 1
        assert any("seam unavailable" in b for b in result["blockers"])
        outcome = result["outcomes"][0]
        assert outcome["status"] == "BLOCKED"
        assert outcome["blockers"], "explicit blocker required"

    def test_resolve_empty_gaps(self, client):
        resp = client.post("/rip/acquisition/resolve-gaps", json={})
        assert resp.status_code == 200
        assert resp.json()["result"]["summary"]["gaps"] == 0


class TestStatusRoute:
    def test_status_reports_flags(self, client):
        resp = client.get("/rip/acquisition/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["flag"] == "NEXUS_ACQUISITION_ENABLED"
        assert body["external_gate"] == "NEXUS_EXTERNAL_ACQUISITION_ENABLED"
        assert isinstance(body["enabled"], bool)


class TestWiring:
    def test_router_prefix_and_routes(self):
        paths = {r.path for r in acquisition_router.routes}
        assert {
            "/rip/acquisition/plan",
            "/rip/acquisition/resolve-gaps",
            "/rip/acquisition/status",
        } <= paths

    def test_thin_route_lazy_imports(self):
        import app.modules.rip.routes.acquisition as mod

        source = open(mod.__file__, encoding="utf-8").read()
        # decisive thin-router check: common_lib imports live inside handlers
        for token in (
            "from common_lib.modules.rip.rip_acquisition.planner import plan_acquisition",
            "from common_lib.modules.rip.rip_acquisition.concurrent import",
        ):
            assert token in source

    def test_registered_in_aggregate_router(self):
        from app.modules.rip.routes import router as aggregate

        paths = {r.path for r in aggregate.routes}
        assert "/rip/acquisition/plan" in paths
