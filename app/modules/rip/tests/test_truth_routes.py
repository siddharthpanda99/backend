"""Route tests for C048 /rip/truth/* (thin delegation)."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.rip.routes.truth import router as truth_router


@pytest.fixture()
def client():
    app = FastAPI()
    app.include_router(truth_router)
    return TestClient(app)


EVIDENCE = [
    {"id": "e1", "content": "John arrived in London on Monday", "source_ref": "docA", "authority": 0.9},
    {"id": "e2", "content": "Witness saw John arrive Tuesday", "source_ref": "docB", "authority": 0.4},
]
CLAIMS = [
    {"id": "c1", "subject": "john", "predicate": "arrived_on", "object": "monday", "valid_from": "2022-06-06", "source_ref": "docA", "authority": 0.9},
    {"id": "c2", "subject": "john", "predicate": "arrived_on", "object": "tuesday", "valid_from": "2022-06-06", "source_ref": "docB", "authority": 0.4},
]
CX = {"id": "cx-1", "claims": CLAIMS, "resolution_status": "UNRESOLVED"}
MATCHES = [{"requirement_id": "r1", "evidence_id": "e1", "kind": "supports"}]


class TestVerifyClaim:
    def test_five_answers(self, client):
        resp = client.post(
            "/rip/truth/verify-claim",
            json={
                "claim": "John arrived in London",
                "evidence": EVIDENCE,
                "matches": MATCHES,
                "at_time": "2022-06-06T12:00:00",
                "valid_window": {"valid_from": "2022-06-06", "valid_to": None},
            },
        )
        assert resp.status_code == 200
        answers = resp.json()["verification"]["answers"]
        assert len(answers) == 5

    def test_empty_claim_422(self, client):
        resp = client.post("/rip/truth/verify-claim", json={"claim": ""})
        assert resp.status_code == 422


class TestAssess:
    def test_assembles_assessment(self, client):
        answers = [
            {"question": "DOES_SOURCE_STATE", "answer": "SUPPORTED_BY_SOURCE"},
            {"question": "CORROBORATED_BY_OTHERS", "answer": "CORROBORATED"},
            {"question": "DO_SOURCES_CONFLICT", "answer": "NO_CONFLICT_DETECTED"},
            {"question": "IS_GOVERNED_TRUE", "answer": "GOVERNED_UNKNOWN"},
            {"question": "TEMPORALLY_VALID_AT", "answer": "TEMPORALLY_VALID"},
        ]
        resp = client.post(
            "/rip/truth/assess",
            json={
                "claim": "John arrived Monday",
                "answers": answers,
                "evidence": EVIDENCE,
                "supporting_evidence_ids": ["e1", "e2"],
            },
        )
        assert resp.status_code == 200
        body = resp.json()["assessment"]
        assert body["status"] == "CORROBORATED"
        assert body["source_truth"] == "STATED"

    def test_dispute_both_sides(self, client):
        answers = [
            {"question": "DOES_SOURCE_STATE", "answer": "SUPPORTED_BY_SOURCE"},
            {"question": "CORROBORATED_BY_OTHERS", "answer": "CORROBORATED"},
            {"question": "DO_SOURCES_CONFLICT", "answer": "CONTRADICTED"},
            {"question": "IS_GOVERNED_TRUE", "answer": "GOVERNED_UNKNOWN"},
            {"question": "TEMPORALLY_VALID_AT", "answer": "TEMPORALLY_UNKNOWN"},
        ]
        resp = client.post(
            "/rip/truth/assess",
            json={
                "claim": "x",
                "answers": answers,
                "evidence": EVIDENCE,
                "supporting_evidence_ids": ["e1"],
                "contradicting_evidence_ids": ["e2"],
            },
        )
        assert resp.json()["assessment"]["status"] == "CONTRADICTED"


class TestContradictions:
    def test_direct_classification(self, client):
        resp = client.post("/rip/truth/contradictions", json={"claims": CLAIMS})
        assert resp.status_code == 200
        result = resp.json()["result"]
        assert result["available"] is True
        assert result["contradictions"][0]["contradiction_type"] == "DIRECT"
        assert result["contradictions"][0]["resolution_status"] == "UNRESOLVED"


class TestResolve:
    def test_resolves_with_signals(self, client):
        resp = client.post("/rip/truth/resolve", json={"contradiction": CX})
        assert resp.status_code == 200
        resolution = resp.json()["resolution"]
        assert resolution["outcome"] in {"RESOLVED", "PARTIALLY_RESOLVED", "UNRESOLVED", "FALSE_CONTRADICTION", "TEMPORALLY_DISTINCT"}
        assert "signals" in resolution

    def test_temporal_distinct(self, client):
        ceo = {"id": "t1", "subject": "john", "predicate": "role", "object": "ceo", "valid_from": "2020-01-01T00:00:00", "valid_to": "2023-12-31T00:00:00"}
        not_ceo = {"id": "t2", "subject": "john", "predicate": "role", "object": "not ceo", "valid_from": "2024-01-01T00:00:00", "valid_to": "2024-12-31T00:00:00"}
        resp = client.post("/rip/truth/resolve", json={"contradiction": {"id": "cx-t", "claims": [ceo, not_ceo]}})
        assert resp.status_code == 200
        assert resp.json()["resolution"]["outcome"] == "TEMPORALLY_DISTINCT"


class TestRetain:
    def test_both_sides_retained(self, client):
        resp = client.post(
            "/rip/truth/retain",
            json={"contradiction": CX, "evidence": EVIDENCE},
        )
        assert resp.status_code == 200
        retained = resp.json()["retained"]
        assert retained["both_sides_retained"] is True
        assert retained["suppressed"] == []
        assert retained["side_a"]["claim"]["object"] == "monday"
        assert retained["side_b"]["claim"]["object"] == "tuesday"


class TestWiring:
    def test_router_prefix_and_routes(self):
        paths = {r.path for r in truth_router.routes}
        assert {
            "/rip/truth/verify-claim",
            "/rip/truth/assess",
            "/rip/truth/contradictions",
            "/rip/truth/resolve",
            "/rip/truth/retain",
        } <= paths

    def test_thin_route_lazy_imports(self):
        import app.modules.rip.routes.truth as mod

        source = open(mod.__file__, encoding="utf-8").read()
        for token in (
            "from common_lib.modules.rip.rip_synthesis.verification import verify_fact",
            "from common_lib.modules.rip.rip_synthesis.contradictions import",
            "from common_lib.modules.rip.rip_synthesis.resolution import resolve_contradiction",
        ):
            assert token in source

    def test_registered_in_aggregate_router(self):
        from app.modules.rip.routes import router as aggregate

        paths = {r.path for r in aggregate.routes}
        assert "/rip/truth/verify-claim" in paths
