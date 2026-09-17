"""Route tests for GU-020 /communities/* (thin delegation)."""

from __future__ import annotations

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from common_lib.modules.integration.ports.rip_port import get_rip_feature_flag_api
from common_lib.modules.knowledge_engine.communities.report_store import (
    reset_report_store,
)
from app.modules.knowledge_engine.routes.communities import router as communities_router


@pytest.fixture()
def client():
    app = FastAPI()
    app.include_router(communities_router)
    return TestClient(app)


@pytest.fixture()
def flags():
    api = get_rip_feature_flag_api()
    api["clear_all_overrides"]()
    yield api
    api["clear_all_overrides"]()


def _enable(api):
    # Master + pipeline flags: the orchestrator fail-closes on each layer.
    api["set_flag_override"]("NEXUS_GLOBAL_UNDERSTANDING_ENABLED", True)
    api["set_flag_override"]("GLOBAL_MAPREDUCE_ENABLED", True)
    api["set_flag_override"]("DUAL_LEVEL_SEARCH_ENABLED", True)


GRAPH_NODES = [
    {"id": f"e{i}", "entity_name": f"Entity{i}", "entity_type": "person"} for i in range(12)
]
GRAPH_EDGES = [
    {"source_id": f"e{i}", "target_id": f"e{i+1}", "relation_type": "R"} for i in range(11)
] + [{"source_id": "e0", "target_id": "e6", "relation_type": "R"}]


class TestGating:
    def test_all_endpoints_503_when_flag_off(self, client, flags):
        assert client.post("/communities/search/global", json={"query": "q"}).status_code == 503
        assert client.post(
            "/communities/search/local",
            json={"query": "q", "graph_nodes": [], "graph_edges": []},
        ).status_code == 503
        assert client.post(
            "/communities/hierarchy", json={"graph_nodes": GRAPH_NODES}
        ).status_code == 503
        assert client.get("/communities/reports/cr_x").status_code == 503


class TestGlobalSearch:
    def test_flag_off_error(self, client, flags):
        resp = client.post("/communities/search/global", json={"query": "themes"})
        assert resp.status_code == 503
        assert "NEXUS_GLOBAL_UNDERSTANDING_ENABLED" in resp.json()["detail"]

    def test_no_reports_returns_error_502(self, client, flags):
        _enable(flags)
        reset_report_store()
        resp = client.post("/communities/search/global", json={"query": "themes"})
        assert resp.status_code == 502  # no_reports denied → error surfaced
        assert "no_reports" in resp.json()["detail"]


class TestLocalSearch:
    def test_happy_path(self, client, flags):
        _enable(flags)
        resp = client.post(
            "/communities/search/local",
            json={
                "query": "Entity1",
                "graph_nodes": GRAPH_NODES,
                "graph_edges": GRAPH_EDGES,
                "max_hops": 1,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["mode"] == "local"
        assert any(e["id"] == "e1" for e in body["entities"])

    def test_no_match_empty(self, client, flags):
        _enable(flags)
        resp = client.post(
            "/communities/search/local",
            json={"query": "zzz", "graph_nodes": GRAPH_NODES, "graph_edges": GRAPH_EDGES},
        )
        assert resp.status_code == 200
        assert resp.json()["entities"] == []


class TestHierarchy:
    def test_happy_path(self, client, flags):
        _enable(flags)
        resp = client.post(
            "/communities/hierarchy",
            json={"graph_nodes": GRAPH_NODES, "graph_edges": GRAPH_EDGES, "levels": 2},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["levels_built"] == 2
        assert body["hierarchy"]
        assert body["signature"]


class TestReportLookup:
    def test_404_when_absent(self, client, flags):
        _enable(flags)
        reset_report_store()
        resp = client.get("/communities/reports/cr_doesnotexist")
        assert resp.status_code == 404

    def test_found(self, client, flags):
        _enable(flags)
        from common_lib.modules.knowledge_engine.communities.contracts import (
            CommunityReport,
            community_report_id,
        )
        from common_lib.modules.knowledge_engine.communities.report_store import (
            get_report_store,
        )

        rep = CommunityReport(
            id=community_report_id(0, 0, "Found"),
            community_id=0, level=0, title="Found", summary="s", evidence_links=["ev"],
        )
        get_report_store().upsert(rep)
        try:
            resp = client.get(f"/communities/reports/{rep.id}")
            assert resp.status_code == 200
            assert resp.json()["title"] == "Found"
        finally:
            reset_report_store()
