"""Route tests for C074 /rip/memory/{policy,scope,promote,conflict} (thin delegation)."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.rip.routes.memory import router as memory_router


@pytest.fixture()
def client():
    app = FastAPI()
    app.include_router(memory_router)
    return TestClient(app)


class TestPolicyRoute:
    def test_policy_defaults_to_context_only_for_document_questions(self, client):
        resp = client.post("/rip/memory/policy", json={"query": "What does the contract say?"})
        assert resp.status_code == 200
        body = resp.json()["result"]
        assert body["policy"] == "MEMORY_CONTEXT_ONLY"

    def test_policy_unknown_rejected_422(self, client):
        resp = client.post(
            "/rip/memory/policy",
            json={"query": "q", "explicit_policy": "BOGUS_POLICY"},
        )
        assert resp.status_code == 422


class TestScopeRoute:
    def test_scope_gate_filters_fail_closed(self, client):
        resp = client.post(
            "/rip/memory/scope",
            json={
                "records": [
                    {"id": "m1", "scope": "CURRENT_DOCUMENT"},
                    {"id": "m2", "scope": "PROJECT"},
                ],
                "query_scope": "CURRENT_DOCUMENT",
            },
        )
        assert resp.status_code == 200
        result = resp.json()["result"]
        ids = [r["id"] for r in result["kept"]]
        assert "m1" in ids
        assert "m2" not in ids
        assert result["excluded"][0]["reason"].startswith("OUT_OF_SCOPE")

    def test_scope_missing_scope_excluded_fail_closed(self, client):
        resp = client.post(
            "/rip/memory/scope",
            json={"records": [{"id": "m3"}], "query_scope": "CURRENT_DOCUMENT"},
        )
        assert resp.status_code == 200
        result = resp.json()["result"]
        assert result["kept"] == []
        assert result["excluded"][0]["reason"] == "MISSING_OR_UNKNOWN_SCOPE"


class TestPromoteRoute:
    def test_promote_memory_happy_path(self, client):
        resp = client.post(
            "/rip/memory/promote",
            json={
                "evidence": {
                    "id": "ev-1",
                    "content": "John arrived in London on March 4.",
                    "doc_id": "doc-1",
                    "confidence": 0.9,
                }
            },
        )
        assert resp.status_code == 200
        assert resp.json()["result"]["status"] == "PROMOTED"

    def test_promote_rejection_is_explicit_not_500(self, client):
        resp = client.post(
            "/rip/memory/promote",
            json={"evidence": {"id": "ev-2", "content": "", "confidence": 0.1}},
        )
        assert resp.status_code == 200
        body = resp.json()["result"]
        assert body["status"] == "REJECTED"
        assert body["reasons"]


class TestConflictRoute:
    def test_conflict_authority_wins_soft_state(self, client):
        resp = client.post(
            "/rip/memory/conflict",
            json={
                "memory": {
                    "id": "mem-1",
                    "subject": "john",
                    "predicate": "was in",
                    "object": "London",
                    "source": {"type": "MEMORY", "authority": 0.25},
                },
                "evidence": {
                    "id": "ev-9",
                    "subject": "john",
                    "predicate": "was in",
                    "object": "New York",
                    "source": {"type": "PRIMARY_DOCUMENT", "authority": 0.8},
                },
            },
        )
        assert resp.status_code == 200
        result = resp.json()["result"]
        assert result["outcome"] == "AUTHORITY_RESOLVED_INVALIDATED"
        # §54: lineage preserved — original content still present.
        assert result["memory"]["object"] == "London"
        assert result["memory"]["stage"] == "INVALIDATED"

    def test_conflict_missing_fields_rejected_422(self, client):
        resp = client.post("/rip/memory/conflict", json={"memory": {}, "evidence": {}})
        assert resp.status_code == 422
