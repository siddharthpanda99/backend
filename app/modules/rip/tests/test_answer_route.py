"""Route tests for C069 /rip/answer/* (thin delegation)."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.rip.routes.answer import router as answer_router


@pytest.fixture()
def client():
    app = FastAPI()
    app.include_router(answer_router)
    return TestClient(app)


_PLAN = {
    "query": "List every event involving John Smith",
    "normalized_query": "list every event involving john smith",
    "scope": "CURRENT_FOLDER",
    "query_types": ["ENUMERATION"],
    "requirements": {},
    "completeness_level": "EXHAUSTIVE",
    "memory_policy": "MEMORY_CONTEXT_ONLY",
    "coverage_threshold": 0.98,
    "verification_policy": "FULL",
    "retrieval_modes": ["GLOBAL"],
    "source_policy": {},
    "output_mode": "STRUCTURED",
    "budgets": {},
}

_CONTEXT = [
    {"id": "e1", "content": "John Smith arrived in London on Monday March 4th 2020.", "authority": 0.9},
]


def test_contract_endpoint(client):
    resp = client.post("/rip/answer/contract", json={"plan": _PLAN})
    assert resp.status_code == 200
    body = resp.json()
    assert body["contract"]["completeness_requirement"] == "EXHAUSTIVE"
    assert body["contract"]["contradiction_policy"] == "RETAIN_BOTH"
    assert len(body["contract"]) == 13


def test_contract_endpoint_requires_plan(client):
    resp = client.post("/rip/answer/contract", json={"plan": {}})
    # Empty plan → missing plan.query → ValueError → 422 (§56 deterministic gate)
    assert resp.status_code == 422


def test_generate_check_endpoint_clean(client):
    resp = client.post(
        "/rip/answer/generate",
        json={"answer": "John Smith arrived in London on Monday March 4th 2020, according to document A."},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["check"]["passed"] is True
    assert len(body["check"]["rules_checked"]) == 10


def test_generate_check_endpoint_violation(client):
    resp = client.post(
        "/rip/answer/generate",
        json={"answer": "All events are listed.", "coverage_ok": False},
    )
    assert resp.status_code == 200
    rules = [v["rule"] for v in resp.json()["check"]["violations"]]
    assert "NO_FALSE_EXHAUSTIVENESS" in rules


def test_verify_endpoint_supported(client):
    resp = client.post(
        "/rip/answer/verify",
        json={
            "answer": "John Smith arrived in London on Monday March 4th 2020.",
            "contract": {"scope": "ALL_ALLOWED", "unresolved_items": [], "coverage_status": "READY"},
            "context_items": _CONTEXT,
        },
    )
    assert resp.status_code == 200
    ver = resp.json()["verification"]
    assert ver["passed"] is True
    assert set(ver["reliability"]) == {
        "grounding", "coverage", "truth_confidence", "source_authority",
        "freshness", "temporal_correctness", "contradiction_state", "provenance_completeness",
    }


def test_verify_endpoint_unsupported(client):
    resp = client.post(
        "/rip/answer/verify",
        json={
            "answer": "John Smith visited Paris in 1999.",
            "contract": {"scope": "ALL_ALLOWED", "unresolved_items": [], "coverage_status": "READY"},
            "context_items": _CONTEXT,
        },
    )
    assert resp.status_code == 200
    ver = resp.json()["verification"]
    assert ver["passed"] is False
    assert ver["verdict"] == "REJECT"


def test_verify_endpoint_requires_answer(client):
    resp = client.post("/rip/answer/verify", json={"answer": ""})
    assert resp.status_code == 422
