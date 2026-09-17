"""Route tests for C053 /rip/evidence/* (thin delegation)."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.rip.routes.evidence import router as evidence_router


@pytest.fixture()
def client():
    app = FastAPI()
    app.include_router(evidence_router)
    return TestClient(app)


EVIDENCE = [
    {"id": "e1", "content": "in-scope", "scope": "CURRENT_DOCUMENT", "document_id": "docA", "source_ref": "docA"},
    {"id": "e2", "content": "external", "scope": "EXTERNAL_SOURCES"},
]
CLAIMS = [{"id": "c1", "subject": "john", "entities": ["john"], "evidence_ids": ["e1"], "source_ref": "docA", "document_id": "docA"}]


def _bundle_payload() -> dict:
    return {
        "query": "What did John do?",
        "scope": "CURRENT_DOCUMENT",
        "evidence": EVIDENCE,
        "claims": CLAIMS,
        "permissions": {"grants": ["CURRENT_DOCUMENT"]},
    }


class TestBundleRoute:
    def test_assembles_and_gates(self, client):
        resp = client.post("/rip/evidence/bundle", json=_bundle_payload())
        assert resp.status_code == 200
        body = resp.json()
        assert [e["id"] for e in body["bundle"]["evidence"]] == ["e1"]
        assert {x["id"] for x in body["excluded_evidence"]} >= {"e2"}
        assert body["bundle"]["permissions"]["gate_enforced"] is True

    def test_empty_query_422(self, client):
        resp = client.post("/rip/evidence/bundle", json={**_bundle_payload(), "query": ""})
        assert resp.status_code == 422

    def test_19_fields(self, client):
        resp = client.post("/rip/evidence/bundle", json=_bundle_payload())
        assert len(resp.json()["bundle"]) == 19


class TestGraphRoute:
    def test_builds_graph(self, client):
        resp = client.post(
            "/rip/evidence/graph",
            json={
                "query_id": "q1",
                "scope": "CURRENT_DOCUMENT",
                "evidence": EVIDENCE,
                "claims": CLAIMS,
            },
        )
        assert resp.status_code == 200
        graph = resp.json()["graph"]
        assert graph["query_id"] == "q1"
        assert graph["ephemeral"] is True
        kinds = {n["kind"] for n in graph["nodes"]}
        assert {"evidence", "claim", "source", "document", "entity"} <= kinds

    def test_summary_endpoint_contract(self, client):
        resp = client.get("/rip/evidence/graph/q1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["query_id"] == "q1"
        assert "ephemeral" in body["note"]


class TestPromoteRoute:
    def test_promotes_known_nodes(self, client):
        graph = client.post(
            "/rip/evidence/graph",
            json={"query_id": "q1", "evidence": EVIDENCE, "claims": CLAIMS},
        ).json()["graph"]
        resp = client.post(
            "/rip/evidence/promote",
            json={"graph": graph, "node_ids": ["claim:c1"]},
        )
        assert resp.status_code == 200
        assert resp.json()["promotion"]["promoted"] == ["claim:c1"]


class TestWiring:
    def test_router_prefix_and_routes(self):
        paths = {r.path for r in evidence_router.routes}
        assert {
            "/rip/evidence/bundle",
            "/rip/evidence/graph",
            "/rip/evidence/graph/{query_id}",
            "/rip/evidence/promote",
        } <= paths

    def test_thin_route_lazy_imports(self):
        import app.modules.rip.routes.evidence as mod

        source = open(mod.__file__, encoding="utf-8").read()
        for token in (
            "from common_lib.modules.rip.rip_synthesis.bundles import assemble_bundle",
            "from common_lib.modules.rip.rip_graph.evidence_graph import",
        ):
            assert token in source

    def test_registered_in_aggregate_router(self):
        from app.modules.rip.routes import router as aggregate

        paths = {r.path for r in aggregate.routes}
        assert "/rip/evidence/bundle" in paths
