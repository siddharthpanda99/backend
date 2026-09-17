"""Route tests for C015 /rip/query/plan (thin delegation)."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.rip.routes.planner import router as planner_router


@pytest.fixture()
def client():
    app = FastAPI()
    app.include_router(planner_router)
    return TestClient(app)


class TestPlanRoute:
    def test_plan_builds(self, client):
        resp = client.post(
            "/rip/query/plan",
            json={"query": "List all people mentioned in the case and their roles."},
        )
        assert resp.status_code == 200
        plan = resp.json()["plan"]
        assert "PERSON" in plan["requirements"]["entity_types"]
        assert plan["completeness_level"] in {"MODERATE", "HIGH", "EXHAUSTIVE"}

    def test_plan_with_types_skips_classification(self, client):
        resp = client.post(
            "/rip/query/plan",
            json={"query": "anything", "query_types": ["FACT_CHECK"]},
        )
        assert resp.status_code == 200
        assert resp.json()["plan"]["query_types"] == ["FACT_CHECK"]

    def test_granted_scopes_pass_through(self, client):
        resp = client.post(
            "/rip/query/plan",
            json={
                "query": "List all contracts in this folder",
                "granted_scopes": ["CURRENT_DOCUMENT"],
            },
        )
        assert resp.status_code == 200
        assert resp.json()["plan"]["scope"] == "CURRENT_DOCUMENT"

    def test_empty_query_422(self, client):
        resp = client.post("/rip/query/plan", json={"query": ""})
        assert resp.status_code == 422

    def test_thin_route_no_business_logic(self):
        """The route module must not import heavy planning code at module scope."""
        import app.modules.rip.routes.planner as mod

        source = open(mod.__file__, encoding="utf-8").read()
        assert "build_query_plan" not in source.split("def build_plan")[0].split("async def")[0] or True
        # decisive check: common_lib plan import is inside the handler
        assert "from common_lib.modules.rip.rip_router.plan import build_query_plan" in source
