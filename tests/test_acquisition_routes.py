"""Nexus Cluster 4 acquisition routes — endpoint tests (chunk CA-023).

Mounts the acquisition router standalone (no full-app import, no auth) and
covers: flag gating (503 when OFF), context build, gap detection, acquisition
planning, and gap fetch (200 + 404).

Run: cd "Backend Monorepo/Backend" && uv run pytest tests/test_acquisition_routes.py -v
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.knowledge_engine.acquisition.routes.router import router
from common_lib.modules.knowledge_engine.acquisition import gap_ledger
from common_lib.modules.rip.feature_flags import clear_all_overrides, set_flag_override
from common_lib.modules.rip.rip_context import flags as context_flags  # noqa: F401  (flag registration)

app = FastAPI()
app.include_router(router)
client = TestClient(app)

ALL_FLAGS = (
    "NEXUS_CONTEXT_ACQUISITION_ENABLED",
    "EVIDENCE_BUNDLES_ENABLED",
    "CONTEXT_BUDGET_OPTIMIZER_ENABLED",
    "KNOWLEDGE_GAP_DETECTION_ENABLED",
    "AUTONOMOUS_ACQUISITION_ENABLED",
)


def _enable_all():
    for name in ALL_FLAGS:
        set_flag_override(name, True)


@pytest.fixture(autouse=True)
def _clean_state():
    clear_all_overrides()
    gap_ledger.clear_ledger()
    yield
    clear_all_overrides()
    gap_ledger.clear_ledger()


class TestFlagGating:
    def test_context_build_503_when_off(self):
        resp = client.post(
            "/context-acquisition/context/build", json={"evidence_items": []}
        )
        assert resp.status_code == 503

    def test_gaps_detect_503_when_off(self):
        resp = client.post("/context-acquisition/gaps/detect", json={"query": "q"})
        assert resp.status_code == 503

    def test_plan_503_when_off(self):
        resp = client.post("/context-acquisition/acquisition/plan", json={"query": "q"})
        assert resp.status_code == 503


class TestContextBuild:
    def test_build(self):
        _enable_all()
        resp = client.post(
            "/context-acquisition/context/build",
            json={
                "system_instructions": "Be helpful.",
                "memory_blocks": ["user likes tea"],
                "evidence_items": [
                    {
                        "id": "e1",
                        "text": "governed fact here",
                        "relevance": 0.95,
                        "authority": 0.9,
                    },
                    {"id": "e2", "text": "background note", "relevance": 0.3},
                ],
                "max_tokens": 8000,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "governed fact" in data["context"]
        assert data["edge_ids"] == ["e1"]
        assert data["admitted_count"] == 2


class TestGapDetect:
    def test_detects_and_records(self):
        _enable_all()
        resp = client.post(
            "/context-acquisition/gaps/detect",
            json={
                "query": "Who founded Acme?",
                "bundle": {"evidence": []},
                "requirements": {"entities": ["founder"]},
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["evaluation"]["sufficient"] is False
        assert len(data["gaps"]) == 1
        assert data["gaps"][0]["gap_type"] == "MISSING_ENTITY"

    def test_sufficient_no_gaps(self):
        _enable_all()
        resp = client.post(
            "/context-acquisition/gaps/detect",
            json={
                "query": "Who is Alice?",
                "bundle": {
                    "entities": [{"name": "Alice"}],
                    "evidence": [
                        {"id": "e1", "text": "Alice leads Acme", "source": "DATABASE"}
                    ],
                },
                "requirements": {"entities": ["Alice"]},
            },
        )
        assert resp.status_code == 200
        assert resp.json()["gaps"] == []


class TestPlanAndFetch:
    def test_plan_routes_channels(self):
        _enable_all()
        resp = client.post(
            "/context-acquisition/acquisition/plan",
            json={
                "query": "Who founded Acme?",
                "gaps": [
                    {
                        "id": "gap-1",
                        "gap_type": "MISSING_ENTITY",
                        "missing_information": "entities: founder",
                        "candidate_sources": ["WORLD_MODEL", "INTERNET_SEARCH"],
                    }
                ],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["sub_queries"]) == 1
        assert data["plan"][0]["gap_id"] == "gap-1"
        assert data["plan"][0]["channel"] == "WORLD_MODEL"

    def test_get_gap_404(self):
        _enable_all()
        resp = client.get("/context-acquisition/gaps/does-not-exist")
        assert resp.status_code == 404

    def test_get_gap_200(self):
        _enable_all()
        detect = client.post(
            "/context-acquisition/gaps/detect",
            json={
                "query": "q",
                "bundle": {"evidence": []},
                "requirements": {"entities": ["Zelda"]},
            },
        )
        gap_id = detect.json()["gaps"][0]["id"]
        resp = client.get(f"/context-acquisition/gaps/{gap_id}")
        assert resp.status_code == 200
        assert resp.json()["gap"]["id"] == gap_id
