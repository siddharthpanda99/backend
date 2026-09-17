"""Route tests for C080 /rip/debug/retrieval (flag-gated §75 debugger)."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.rip.routes.debug import router as debug_router


@pytest.fixture()
def client():
    app = FastAPI()
    app.include_router(debug_router)
    return TestClient(app)


@pytest.fixture()
def flag_on(monkeypatch):
    monkeypatch.setenv("RIP_FLAG_NEXUS_RETRIEVAL_DEBUGGER_ENABLED", "true")
    yield
    monkeypatch.delenv("RIP_FLAG_NEXUS_RETRIEVAL_DEBUGGER_ENABLED", raising=False)


def _trace() -> dict:
    return {
        "classification": {"query_types": ["TIMELINE", "ENUMERATION"]},
        "channels": {"used": ["lexical", "vector", "temporal"]},
        "candidates": {"count": 42},
        "scores": {"top": 0.93},
        "expansions": {"parent_sections": 4},
        "context": {"tokens": 1800},
    }


class TestFlagGate:
    def test_flag_off_returns_403_not_payload(self, client):
        resp = client.post(
            "/rip/debug/retrieval",
            json={"query_id": "q-1", "retrieval_trace": _trace()},
        )
        assert resp.status_code == 403

    def test_flag_on_returns_stages(self, client, flag_on):
        resp = client.post(
            "/rip/debug/retrieval",
            json={"query_id": "q-1", "retrieval_trace": _trace()},
        )
        assert resp.status_code == 200
        payload = resp.json()["payload"]
        assert payload["debug_enabled"] is True
        assert payload["stages"]["classification"]["query_types"] == ["TIMELINE", "ENUMERATION"]
        assert "built_at" in payload


class TestPayloadShape:
    def test_missing_stages_reported(self, client, flag_on):
        resp = client.post(
            "/rip/debug/retrieval",
            json={"query_id": "q-2", "retrieval_trace": {"classification": {"types": ["SUMMARY"]}}},
        )
        assert resp.status_code == 200
        payload = resp.json()["payload"]
        assert "channels" in payload["missing_stages"]

    def test_query_id_required(self, client):
        resp = client.post("/rip/debug/retrieval", json={"retrieval_trace": {}})
        assert resp.status_code == 422
