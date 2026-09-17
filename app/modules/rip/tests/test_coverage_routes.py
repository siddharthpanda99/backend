"""Route tests for C035 /rip/coverage/* (thin delegation)."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.rip.routes.coverage import router as coverage_router


@pytest.fixture()
def client():
    app = FastAPI()
    app.include_router(coverage_router)
    return TestClient(app)


def _ev(eid: str) -> dict:
    return {"id": eid, "type": "DOCUMENT_TEXT", "content": f"c {eid}"}


def _payload() -> dict:
    return {
        "query": "list all events",
        "scope": "CURRENT_DOCUMENT",
        "requirements": [
            {"requirement_id": "r1", "dimension": "ENTITY"},
            {"requirement_id": "r2", "dimension": "EVENT"},
        ],
        "evidence": [_ev("e1")],
        "matches": [{"requirement_id": "r1", "evidence_id": "e1", "kind": "supports"}],
    }


class TestAssessRoute:
    def test_assess_measures(self, client):
        resp = client.post("/rip/coverage/assess", json=_payload())
        assert resp.status_code == 200
        report = resp.json()["report"]
        assert report["expected"] == 2
        assert report["supported"] == 1
        assert report["requirements"]["r1"]["state"] == "SUPPORTED"

    def test_assess_invalid_dimension_422(self, client):
        payload = _payload()
        payload["requirements"][0]["dimension"] = "BANANA"
        resp = client.post("/rip/coverage/assess", json=payload)
        assert resp.status_code == 422

    def test_assess_empty_query_422(self, client):
        resp = client.post("/rip/coverage/assess", json={**_payload(), "query": ""})
        assert resp.status_code == 422


class TestGapsRoute:
    def test_gaps_from_report(self, client):
        assess = client.post("/rip/coverage/assess", json=_payload()).json()["report"]
        resp = client.post(
            "/rip/coverage/gaps",
            json={"report": assess, "candidate_sources": ["ke-docs"]},
        )
        assert resp.status_code == 200
        gaps = resp.json()["gaps"]
        assert {g["requirement"] for g in gaps} == {"r2"}
        assert gaps[0]["candidate_sources"] == ["ke-docs"]


class TestRankRoute:
    def test_rank_orders_candidates(self, client):
        resp = client.post(
            "/rip/coverage/rank-next",
            json={
                "candidates": [
                    {"candidate_id": "a", "gap_id": "g1", "source_id": "s1"},
                    {"candidate_id": "b", "gap_id": "g2", "source_id": "s2"},
                ],
                "gaps": [
                    {"id": "g1", "missing_type": "FACT", "priority": 40},
                    {"id": "g2", "missing_type": "CORROBORATION", "priority": 40},
                ],
            },
        )
        assert resp.status_code == 200
        ranked = resp.json()["ranked"]
        assert ranked[0]["candidate_id"] == "b"


class TestExhaustionRoute:
    def test_no_evidence_found(self, client):
        resp = client.post(
            "/rip/coverage/exhaustion",
            json={"found_count": 0, "all_admissible_searched": True},
        )
        assert resp.status_code == 200
        assert resp.json()["exhaustion"]["state"] == "NO_EVIDENCE_FOUND"

    def test_blockers_may_exist(self, client):
        resp = client.post(
            "/rip/coverage/exhaustion",
            json={
                "found_count": 0,
                "all_admissible_searched": True,
                "blockers": ["permission denied"],
            },
        )
        assert resp.status_code == 200
        body = resp.json()["exhaustion"]
        assert body["state"] == "EVIDENCE_MAY_EXIST_BUT_COULD_NOT_BE_ACQUIRED"
        assert body["is_negative_answer"] is False


class TestWiring:
    def test_router_prefix_and_routes(self):
        paths = {r.path for r in coverage_router.routes}
        assert {
            "/rip/coverage/assess",
            "/rip/coverage/gaps",
            "/rip/coverage/rank-next",
            "/rip/coverage/exhaustion",
        } <= paths

    def test_thin_route_lazy_imports(self):
        import app.modules.rip.routes.coverage as mod

        source = open(mod.__file__, encoding="utf-8").read()
        # decisive thin-router check: common_lib imports live inside handlers
        for token in (
            "from common_lib.modules.rip.rip_coverage.engine import measure_coverage",
            "from common_lib.modules.rip.rip_coverage.gaps import detect_gaps",
        ):
            assert token in source
