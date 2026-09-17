"""Route tests for MEM-026 /memory/cognitive/* (thin delegation, flag-gated)."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from common_lib.modules.integration.ports.rip_port import get_rip_feature_flag_api
from common_lib.modules.memory.letta.blocks import get_core_block_store
from common_lib.modules.memory.stores.semantic_store import get_semantic_store

from app.modules.memory.routes.cognitive import router as cognitive_router


@pytest.fixture()
def client():
    app = FastAPI()
    app.include_router(cognitive_router)
    return TestClient(app)


@pytest.fixture(autouse=True)
def _env():
    api = get_rip_feature_flag_api()
    api["clear_all_overrides"]()
    api["set_flag_override"]("NEXUS_MEMORY_ENGINE_ENABLED", True)
    api["set_flag_override"]("MEMORY_AGENT_MANAGED_ENABLED", True)
    sem = get_semantic_store()
    for mid in list(sem._memories.keys()):
        sem._memories.pop(mid, None)
    get_core_block_store().reset()
    yield
    api["clear_all_overrides"]()
    for mid in list(sem._memories.keys()):
        sem._memories.pop(mid, None)
    get_core_block_store().reset()


class TestFlagGate:
    def test_engine_off_503(self, client):
        api = get_rip_feature_flag_api()
        api["set_flag_override"]("NEXUS_MEMORY_ENGINE_ENABLED", False)
        resp = client.post("/memory/cognitive/remember", json={"content": "x"})
        assert resp.status_code == 503

    def test_engine_default_off_503(self, client):
        api = get_rip_feature_flag_api()
        api["clear_all_overrides"]()
        resp = client.post("/memory/cognitive/recall", json={"query": "x"})
        assert resp.status_code == 503


class TestRememberRecall:
    def test_remember_roundtrip(self, client):
        resp = client.post(
            "/memory/cognitive/remember",
            json={"content": "Falcon uses Postgres", "scope": "PRIVATE", "agent_id": "a1"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["action"] == "created"
        assert body["memory_id"]

        recall = client.post(
            "/memory/cognitive/recall", json={"query": "Falcon", "token_budget": 2000}
        )
        assert recall.status_code == 200
        assert "results" in recall.json()

    def test_remember_validation_error(self, client):
        resp = client.post("/memory/cognitive/remember", json={"content": ""})
        assert resp.status_code == 422


class TestBlocks:
    def test_read_blocks(self, client):
        resp = client.get("/memory/cognitive/blocks", params={"agent_id": "agent-x"})
        assert resp.status_code == 200
        assert "persona" in resp.json()

    def test_append_block(self, client):
        resp = client.post(
            "/memory/cognitive/blocks/append",
            json={"agent_id": "agent-x", "name": "persona", "text": "Be terse."},
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_tools_endpoint_gated_and_working(self, client):
        resp = client.post(
            "/memory/cognitive/tools",
            json={"agent_id": "agent-x", "tool": "core_memory_append", "args": {"name": "human", "text": "hi"}},
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True


class TestReflectConsolidate:
    def test_reflect(self, client):
        client.post("/memory/cognitive/remember", json={"content": "Falcon uses Redis"})
        resp = client.post("/memory/cognitive/reflect", json={"topic": "Falcon", "store": False})
        assert resp.status_code == 200
        assert "synthesis" in resp.json()

    def test_consolidate_dry_run(self, client):
        resp = client.post(
            "/memory/cognitive/consolidate",
            json={"agent_id": "a1", "dry_run": True},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "clusters" in body


class TestMisc:
    def test_freshness_endpoint(self, client):
        created = client.post(
            "/memory/cognitive/remember", json={"content": "fresh fact for freshness"}
        ).json()
        mid = created["memory_id"]
        resp = client.get("/memory/cognitive/freshness", params={"memory_id": mid})
        assert resp.status_code == 200
        assert resp.json()["verdict"] in ("FRESH", "AGING", "STALE", "EXPIRED")

    def test_error_normalized_502(self, client):
        resp = client.get("/memory/cognitive/freshness", params={"memory_id": "sem-does-not-exist"})
        assert resp.status_code == 502

    def test_share_endpoint(self, client):
        created = client.post(
            "/memory/cognitive/remember",
            json={"content": "shareable fact", "agent_id": "agent-1"},
        ).json()
        mid = created["memory_id"]
        resp = client.post(
            "/memory/cognitive/share",
            json={"memory_id": mid, "pool_scope": "project:apollo", "caller_agent_id": "agent-1"},
        )
        assert resp.status_code == 200
        assert resp.json()["shared"] is True

    def test_promote_endpoint_denied_stage(self, client):
        # Promotion requires MEMORY_PROMOTION_ENABLED; leave it off → stage denial (200 w/ structured body)
        created = client.post(
            "/memory/cognitive/remember", json={"content": "Falcon uses Postgres", "agent_id": "a1"}
        ).json()
        mid = created["memory_id"]
        resp = client.post(
            "/memory/cognitive/promote", json={"memory_id": mid, "kb_id": "kb-1"}
        )
        assert resp.status_code == 200
        assert resp.json()["promoted"] is False
