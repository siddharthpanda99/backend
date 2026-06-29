"""Integration tests for SOTA REST endpoints.

Tests all 18 endpoints under /api/v1/sota/ using FastAPI TestClient
with a fully mocked SOTAService.  No LLM calls, no real agent init.

Usage:
    cd Backend Monorepo/Backend
    uv run python -m pytest app/modules/sota/tests/test_sota_routes.py -v
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.sota.routes.router import router as sota_router


# ---------------------------------------------------------------------------
# Sample response data
# ---------------------------------------------------------------------------

SAMPLE_MEM0_ADD = {"added": 2, "updated": 1, "deleted": 0}
SAMPLE_MEM0_SEARCH = [{"id": "m1", "text": "prefers dark mode", "score": 0.92}]
SAMPLE_MEM0_STATE = {"user_count": 3, "total_memories": 42}

SAMPLE_MEMGPT_STEP = "I remember you mentioned Python."
SAMPLE_MEMGPT_STATE = {
    "core_memory": {"persona": "helpful assistant"},
    "archival_count": 5,
    "conversation_turns": 8,
}

SAMPLE_REFLEXION_RUN = {
    "success": True,
    "attempt": "def solve(): return 42",
    "trials": 2,
    "outcome": "passed",
    "reflections": ["Need to handle edge cases"],
}

SAMPLE_GEN_AGENT_ACT = "I will recommend the Italian place."
SAMPLE_GEN_AGENT_RETRIEVE = [
    {"content": "likes pasta", "importance": 0.9, "type": "observation"},
    {"content": "visited Rome", "importance": 0.6, "type": "reflection"},
]
SAMPLE_GEN_AGENT_STATE = {
    "name": "Agent",
    "persona": "Helpful AI",
    "memory_stream_count": 15,
    "reflections": 4,
}

SAMPLE_LONGMEM_CHAT = "In our earlier conversation, you asked about compression."
SAMPLE_LONGMEM_STATE = {"active_turns": 4, "compressed_chunks": 3, "total_turns": 12}

SAMPLE_ZEP_EPISODE = "ep_abc123"
SAMPLE_ZEP_SEARCH = [{"entity": "Alice", "fact": "lives in Paris", "score": 0.88}]
SAMPLE_ZEP_FACTS = [{"entity": "Alice", "fact": "works at TechCorp", "valid_from": "2024-01-01"}]
SAMPLE_ZEP_STATE = {"entities": 8, "edges": 20, "episodes": 12, "currently_valid_edges": 18}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_service() -> MagicMock:
    """Create a fully mocked SOTAService with known return values."""
    svc = MagicMock()

    # Mem0
    svc.mem0_add = AsyncMock(return_value=SAMPLE_MEM0_ADD)
    svc.mem0_search = AsyncMock(return_value=SAMPLE_MEM0_SEARCH)
    svc.mem0_get_all = AsyncMock(return_value=[{"id": "m1"}, {"id": "m2"}])
    svc.mem0_delete = AsyncMock(return_value=True)
    svc.mem0_state = AsyncMock(return_value=SAMPLE_MEM0_STATE)

    # MemGPT
    svc.memgpt_step = AsyncMock(return_value=SAMPLE_MEMGPT_STEP)
    svc.memgpt_state = AsyncMock(return_value=SAMPLE_MEMGPT_STATE)
    svc.memgpt_reset = AsyncMock()
    svc.memgpt_reset_all = AsyncMock()

    # Reflexion
    svc.reflexion_run = AsyncMock(return_value=SAMPLE_REFLEXION_RUN)
    svc.reflexion_clear = AsyncMock()
    svc.reflexion_state = AsyncMock(return_value={"episodes": 5, "reflections": 2})

    # Generative Agent
    svc.gen_agent_observe = AsyncMock()
    svc.gen_agent_act = AsyncMock(return_value=SAMPLE_GEN_AGENT_ACT)
    svc.gen_agent_retrieve = AsyncMock(return_value=SAMPLE_GEN_AGENT_RETRIEVE)
    svc.gen_agent_state = AsyncMock(return_value=SAMPLE_GEN_AGENT_STATE)
    svc.gen_agent_clear = AsyncMock()

    # LongMem
    svc.longmem_chat = AsyncMock(return_value=SAMPLE_LONGMEM_CHAT)
    svc.longmem_state = AsyncMock(return_value=SAMPLE_LONGMEM_STATE)
    svc.longmem_clear = AsyncMock()

    # Zep
    svc.zep_add_episode = AsyncMock(return_value=SAMPLE_ZEP_EPISODE)
    svc.zep_search = AsyncMock(return_value=SAMPLE_ZEP_SEARCH)
    svc.zep_facts = AsyncMock(return_value=SAMPLE_ZEP_FACTS)
    svc.zep_state = AsyncMock(return_value=SAMPLE_ZEP_STATE)
    svc.zep_clear = AsyncMock()

    return svc


@pytest.fixture
def client(mock_service: MagicMock) -> TestClient:
    """Create a sync TestClient with the SOTA router and mocked service."""
    app = FastAPI()
    app.include_router(sota_router, prefix="/api/v1/sota")

    # Patch get_sota_service to return our mock
    with patch(
        "app.modules.sota.routes.router.get_sota_service",
        return_value=mock_service,
    ):
        with TestClient(app) as c:
            yield c


# ── Health ──────────────────────────────────────────────────────────────────

class TestHealthEndpoint:
    """GET /api/v1/sota/health"""

    def test_health_returns_200(self, client: TestClient):
        response = client.get("/api/v1/sota/health")
        assert response.status_code == 200

    def test_health_reports_all_agents(self, client: TestClient):
        body = client.get("/api/v1/sota/health").json()
        assert body["status"] == "ok"
        for agent in ["mem0", "memgpt", "reflexion", "gen_agent", "longmem", "zep"]:
            assert agent in body["agents"]
            assert body["agents"][agent] is True


# ── Mem0 ────────────────────────────────────────────────────────────────────

class TestMem0Endpoints:
    """POST /mem0/add, POST /mem0/search, GET /mem0/{uid}/memories,
    DELETE /mem0/{uid}/memories/{id}, GET /mem0/state"""

    def test_add_memories(self, client: TestClient, mock_service: MagicMock):
        response = client.post(
            "/api/v1/sota/mem0/add",
            json={
                "messages": [{"role": "user", "content": "I like dark mode"}],
                "user_id": "u1",
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["added"] == 2
        assert body["updated"] == 1
        mock_service.mem0_add.assert_awaited_once()

    def test_add_memories_missing_messages_returns_422(self, client: TestClient):
        response = client.post("/api/v1/sota/mem0/add", json={"user_id": "u1"})
        assert response.status_code == 422

    def test_search_memories(self, client: TestClient, mock_service: MagicMock):
        response = client.post(
            "/api/v1/sota/mem0/search",
            json={"query": "dark mode preference", "user_id": "u1", "top_k": 5},
        )
        assert response.status_code == 200
        body = response.json()
        assert len(body["results"]) == 1
        assert body["results"][0]["text"] == "prefers dark mode"

    def test_get_all_memories(self, client: TestClient, mock_service: MagicMock):
        response = client.get("/api/v1/sota/mem0/u1/memories")
        assert response.status_code == 200
        body = response.json()
        assert len(body["memories"]) == 2

    def test_delete_memory(self, client: TestClient, mock_service: MagicMock):
        response = client.delete("/api/v1/sota/mem0/u1/memories/m1")
        assert response.status_code == 200
        assert response.json()["deleted"] is True
        mock_service.mem0_delete.assert_awaited_once_with("m1", "u1")

    def test_get_state(self, client: TestClient, mock_service: MagicMock):
        response = client.get("/api/v1/sota/mem0/state")
        assert response.status_code == 200
        body = response.json()
        assert body["total_memories"] == 42


# ── MemGPT ──────────────────────────────────────────────────────────────────

class TestMemGPTEndpoints:
    """POST /memgpt/step, GET /memgpt/state, POST /memgpt/reset, POST /memgpt/reset-all"""

    def test_step(self, client: TestClient, mock_service: MagicMock):
        response = client.post(
            "/api/v1/sota/memgpt/step",
            json={"message": "What do you remember about me?"},
        )
        assert response.status_code == 200
        assert response.json()["reply"] == SAMPLE_MEMGPT_STEP
        mock_service.memgpt_step.assert_awaited_once_with("What do you remember about me?")

    def test_step_missing_message_returns_422(self, client: TestClient):
        response = client.post("/api/v1/sota/memgpt/step", json={})
        assert response.status_code == 422

    def test_get_state(self, client: TestClient, mock_service: MagicMock):
        response = client.get("/api/v1/sota/memgpt/state")
        assert response.status_code == 200
        body = response.json()
        assert body["archival_count"] == 5
        assert body["conversation_turns"] == 8

    def test_reset(self, client: TestClient, mock_service: MagicMock):
        response = client.post("/api/v1/sota/memgpt/reset")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        mock_service.memgpt_reset.assert_awaited_once()

    def test_reset_all(self, client: TestClient, mock_service: MagicMock):
        response = client.post("/api/v1/sota/memgpt/reset-all")
        assert response.status_code == 200
        mock_service.memgpt_reset_all.assert_awaited_once()


# ── Reflexion ───────────────────────────────────────────────────────────────

class TestReflexionEndpoints:
    """POST /reflexion/run, POST /reflexion/clear, GET /reflexion/state"""

    def test_run(self, client: TestClient, mock_service: MagicMock):
        response = client.post(
            "/api/v1/sota/reflexion/run",
            json={
                "task": "solve FizzBuzz",
                "expected_outcome": "correct output for 1-100",
                "context": "Python",
                "max_trials": 3,
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["trials"] == 2
        assert len(body["reflections"]) == 1

    def test_run_missing_task_returns_422(self, client: TestClient):
        response = client.post("/api/v1/sota/reflexion/run", json={})
        assert response.status_code == 422

    def test_run_delegates_to_service(self, client: TestClient, mock_service: MagicMock):
        client.post(
            "/api/v1/sota/reflexion/run",
            json={"task": "test", "max_trials": 5},
        )
        mock_service.reflexion_run.assert_awaited_once_with(
            task="test", expected_outcome="", context="", max_trials=5,
        )

    def test_clear(self, client: TestClient, mock_service: MagicMock):
        response = client.post("/api/v1/sota/reflexion/clear")
        assert response.status_code == 200
        mock_service.reflexion_clear.assert_awaited_once()

    def test_get_state(self, client: TestClient, mock_service: MagicMock):
        response = client.get("/api/v1/sota/reflexion/state")
        assert response.status_code == 200
        assert response.json()["episodes"] == 5


# ── Generative Agent ────────────────────────────────────────────────────────

class TestGenAgentEndpoints:
    """POST /gen-agent/observe, POST /gen-agent/act, POST /gen-agent/retrieve,
    GET /gen-agent/state, POST /gen-agent/clear"""

    def test_observe(self, client: TestClient, mock_service: MagicMock):
        response = client.post(
            "/api/v1/sota/gen-agent/observe",
            json={"observation": "saw a cat at the park"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        mock_service.gen_agent_observe.assert_awaited_once_with("saw a cat at the park")

    def test_act(self, client: TestClient, mock_service: MagicMock):
        response = client.post(
            "/api/v1/sota/gen-agent/act",
            json={"observation": "hungry cat nearby"},
        )
        assert response.status_code == 200
        assert response.json()["action"] == SAMPLE_GEN_AGENT_ACT

    def test_retrieve(self, client: TestClient, mock_service: MagicMock):
        response = client.post(
            "/api/v1/sota/gen-agent/retrieve",
            json={"situation": "looking for food", "top_k": 5},
        )
        assert response.status_code == 200
        body = response.json()
        assert len(body["results"]) == 2
        assert body["results"][0]["content"] == "likes pasta"

    def test_get_state(self, client: TestClient, mock_service: MagicMock):
        response = client.get("/api/v1/sota/gen-agent/state")
        assert response.status_code == 200
        body = response.json()
        assert body["memory_stream_count"] == 15
        assert body["reflections"] == 4

    def test_clear(self, client: TestClient, mock_service: MagicMock):
        response = client.post("/api/v1/sota/gen-agent/clear")
        assert response.status_code == 200
        mock_service.gen_agent_clear.assert_awaited_once()


# ── LongMem ─────────────────────────────────────────────────────────────────

class TestLongMemEndpoints:
    """POST /longmem/chat, GET /longmem/state, POST /longmem/clear"""

    def test_chat(self, client: TestClient, mock_service: MagicMock):
        response = client.post(
            "/api/v1/sota/longmem/chat",
            json={"message": "What did we discuss earlier?", "system_prompt": "You are helpful"},
        )
        assert response.status_code == 200
        assert response.json()["reply"] == SAMPLE_LONGMEM_CHAT
        mock_service.longmem_chat.assert_awaited_once_with(
            "What did we discuss earlier?", system_prompt="You are helpful",
        )

    def test_chat_missing_message_returns_422(self, client: TestClient):
        response = client.post("/api/v1/sota/longmem/chat", json={})
        assert response.status_code == 422

    def test_get_state(self, client: TestClient, mock_service: MagicMock):
        response = client.get("/api/v1/sota/longmem/state")
        assert response.status_code == 200
        body = response.json()
        assert body["compressed_chunks"] == 3
        assert body["total_turns"] == 12

    def test_clear(self, client: TestClient, mock_service: MagicMock):
        response = client.post("/api/v1/sota/longmem/clear")
        assert response.status_code == 200
        mock_service.longmem_clear.assert_awaited_once()


# ── Zep ─────────────────────────────────────────────────────────────────────

class TestZepEndpoints:
    """POST /zep/episode, POST /zep/search, POST /zep/facts,
    GET /zep/state, POST /zep/clear"""

    def test_add_episode(self, client: TestClient, mock_service: MagicMock):
        response = client.post(
            "/api/v1/sota/zep/episode",
            json={
                "messages": [{"role": "user", "content": "Met Alice today"}],
                "user_id": "u1",
            },
        )
        assert response.status_code == 200
        assert response.json()["episode_id"] == "ep_abc123"

    def test_add_episode_missing_messages_returns_422(self, client: TestClient):
        response = client.post("/api/v1/sota/zep/episode", json={})
        assert response.status_code == 422

    def test_search(self, client: TestClient, mock_service: MagicMock):
        response = client.post(
            "/api/v1/sota/zep/search",
            json={"query": "Where does Alice live?", "user_id": "u1", "limit": 5},
        )
        assert response.status_code == 200
        body = response.json()
        assert len(body["results"]) == 1
        assert body["results"][0]["entity"] == "Alice"

    def test_facts(self, client: TestClient, mock_service: MagicMock):
        response = client.post(
            "/api/v1/sota/zep/facts",
            json={"user_id": "u1", "entity": "Alice"},
        )
        assert response.status_code == 200
        body = response.json()
        assert len(body["facts"]) == 1
        assert body["facts"][0]["entity"] == "Alice"

    def test_facts_no_entity(self, client: TestClient, mock_service: MagicMock):
        response = client.post(
            "/api/v1/sota/zep/facts",
            json={"user_id": "u1"},
        )
        assert response.status_code == 200
        mock_service.zep_facts.assert_awaited_once_with(user_id="u1", entity=None)

    def test_get_state(self, client: TestClient, mock_service: MagicMock):
        response = client.get("/api/v1/sota/zep/state")
        assert response.status_code == 200
        body = response.json()
        assert body["entities"] == 8
        assert body["edges"] == 20

    def test_clear(self, client: TestClient, mock_service: MagicMock):
        response = client.post("/api/v1/sota/zep/clear")
        assert response.status_code == 200
        mock_service.zep_clear.assert_awaited_once()


# ── Error handling ──────────────────────────────────────────────────────────

class TestErrorHandling:
    """Verify 500 responses when service methods raise exceptions."""

    def test_mem0_add_error(self, client: TestClient, mock_service: MagicMock):
        mock_service.mem0_add = AsyncMock(side_effect=RuntimeError("LLM timeout"))
        response = client.post(
            "/api/v1/sota/mem0/add",
            json={"messages": [{"role": "user", "content": "test"}], "user_id": "u1"},
        )
        assert response.status_code == 500
        assert "LLM timeout" in response.json()["detail"]

    def test_memgpt_step_error(self, client: TestClient, mock_service: MagicMock):
        mock_service.memgpt_step = AsyncMock(side_effect=ValueError("bad state"))
        response = client.post(
            "/api/v1/sota/memgpt/step",
            json={"message": "hello"},
        )
        assert response.status_code == 500

    def test_zep_search_error(self, client: TestClient, mock_service: MagicMock):
        mock_service.zep_search = AsyncMock(side_effect=ConnectionError("graph unavailable"))
        response = client.post(
            "/api/v1/sota/zep/search",
            json={"query": "test"},
        )
        assert response.status_code == 500
        assert "graph unavailable" in response.json()["detail"]

    def test_longmem_chat_error(self, client: TestClient, mock_service: MagicMock):
        mock_service.longmem_chat = AsyncMock(side_effect=RuntimeError("model offline"))
        response = client.post(
            "/api/v1/sota/longmem/chat",
            json={"message": "hello"},
        )
        assert response.status_code == 500
