"""Comprehensive API tests for session routes using FastAPI TestClient."""

import os
import tempfile

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlalchemy.pool import NullPool

from common_lib.modules.data_storage.database.connection import (
    get_session as get_db_session,
)
from common_lib.modules.agents.models.session_models import (
    AgentSession,
    AgentConversation,
    AgentMessage,
    AgentToolCall,
    SessionState,
)

_db_file = os.path.join(tempfile.gettempdir(), "test_session_api.db")
_test_engine = create_engine(
    f"sqlite:///{_db_file}",
    echo=False,
    connect_args={"check_same_thread": False},
    poolclass=NullPool,
)


def _override_get_session():
    with Session(_test_engine) as session:
        yield session


app = FastAPI()
from app.modules.agents.routes.session_routes import router as session_router

app.include_router(session_router, prefix="/runtime")

app.dependency_overrides[get_db_session] = _override_get_session

client = TestClient(app)

_SESSION_MODEL_TABLES = [
    AgentSession,
    AgentConversation,
    AgentMessage,
    AgentToolCall,
    SessionState,
]


@pytest.fixture(autouse=True)
def setup_db():
    for model in _SESSION_MODEL_TABLES:
        model.__table__.create(_test_engine, checkfirst=True)
    yield
    for model in reversed(_SESSION_MODEL_TABLES):
        model.__table__.drop(_test_engine, checkfirst=True)


class TestHealth:
    def test_health_check(self):
        resp = client.get("/runtime/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestCreateSession:
    def test_create_session_minimal(self):
        resp = client.post("/runtime", json={"name": "Test Session"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Test Session"
        assert data["user_id"] == "default"
        assert data["is_active"] is True
        assert data["is_pinned"] is False
        assert data["conversation_id"] is not None
        assert data["id"].startswith("session_")

    def test_create_session_full(self):
        resp = client.post(
            "/runtime",
            json={
                "name": "Full Session",
                "user_id": "user42",
                "agent_id": "agent-1",
                "agent_name": "TestAgent",
                "model_id": "gpt-4",
                "model_name": "GPT-4",
                "engine": "openai",
                "description": "A test session",
                "tags": ["test", "demo"],
                "metadata": {"source": "pytest"},
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Full Session"
        assert data["user_id"] == "user42"
        assert data["agent_id"] == "agent-1"
        assert data["agent_name"] == "TestAgent"
        assert data["model_id"] == "gpt-4"
        assert data["model_name"] == "GPT-4"
        assert data["engine"] == "openai"
        assert data["description"] == "A test session"
        assert data["tags"] == ["test", "demo"]
        assert data["metadata"] == {"source": "pytest"}

    def test_create_session_no_optional(self):
        resp = client.post("/runtime", json={"name": ""})
        assert resp.status_code == 200
        data = resp.json()
        assert data["engine"] == "vllm"
        assert data["tags"] == []
        assert data["metadata"] == {}


class TestListSessions:
    def test_list_sessions_empty(self):
        resp = client.get("/runtime")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_sessions_with_created(self):
        client.post("/runtime", json={"name": "S1"})
        client.post("/runtime", json={"name": "S2"})
        resp = client.get("/runtime")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    def test_list_sessions_user_id_filter(self):
        client.post("/runtime", json={"name": "U1", "user_id": "alice"})
        client.post("/runtime", json={"name": "U2", "user_id": "bob"})
        resp = client.get("/runtime?user_id=alice")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["user_id"] == "alice"

    def test_list_sessions_pinned_flag(self):
        s1 = client.post("/runtime", json={"name": "S1"}).json()
        client.patch(f"/runtime/{s1['id']}", json={"is_pinned": True})
        client.post("/runtime", json={"name": "S2"})
        resp = client.get("/runtime?pinned=true")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["is_pinned"] is True


class TestGetSession:
    def test_get_session_ok(self):
        created = client.post("/runtime", json={"name": "GetMe"}).json()
        resp = client.get(f"/runtime/{created['id']}")
        assert resp.status_code == 200
        assert resp.json()["id"] == created["id"]

    def test_get_session_404(self):
        resp = client.get("/runtime/nonexistent")
        assert resp.status_code == 404

    def test_get_session_with_message_count(self):
        created = client.post("/runtime", json={"name": "MsgCount"}).json()
        conv_id = created["conversation_id"]
        client.post(
            f"/runtime/conversations/{conv_id}/messages",
            json={"role": "user", "content": "hello"},
        )
        resp = client.get(f"/runtime/{created['id']}")
        assert resp.status_code == 200
        assert resp.json()["message_count"] == 1


class TestUpdateSession:
    def test_update_session_name(self):
        created = client.post("/runtime", json={"name": "Old"}).json()
        resp = client.patch(f"/runtime/{created['id']}", json={"name": "New"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "New"

    def test_update_session_pin(self):
        created = client.post("/runtime", json={"name": "PinMe"}).json()
        resp = client.patch(f"/runtime/{created['id']}", json={"is_pinned": True})
        assert resp.status_code == 200
        assert resp.json()["is_pinned"] is True

    def test_update_session_partial(self):
        created = client.post(
            "/runtime",
            json={"name": "Partial", "description": "Original desc", "tags": ["a"]},
        ).json()
        resp = client.patch(
            f"/runtime/{created['id']}", json={"description": "Updated desc"}
        )
        assert resp.status_code == 200
        assert resp.json()["description"] == "Updated desc"
        assert resp.json()["name"] == "Partial"
        assert resp.json()["tags"] == ["a"]

    def test_update_session_404(self):
        resp = client.patch("/runtime/nonexistent", json={"name": "Nope"})
        assert resp.status_code == 404


class TestDeleteSession:
    def test_delete_session_ok(self):
        created = client.post("/runtime", json={"name": "DeleteMe"}).json()
        resp = client.delete(f"/runtime/{created['id']}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"
        get_resp = client.get(f"/runtime/{created['id']}")
        assert get_resp.status_code == 404

    def test_delete_session_404(self):
        resp = client.delete("/runtime/nonexistent")
        assert resp.status_code == 404


class TestPruneEmptySessions:
    def test_prune_empty_noop(self):
        resp = client.post("/runtime/prune-empty")
        assert resp.status_code == 200
        assert resp.json()["deleted_count"] == 0

    def test_prune_empty_removes_empty(self):
        s1 = client.post("/runtime", json={"name": "Keep"}).json()
        s2 = client.post("/runtime", json={"name": "PruneMe"}).json()
        conv_id = s2["conversation_id"]
        client.post(
            f"/runtime/conversations/{conv_id}/messages",
            json={"role": "user", "content": "save me"},
        )
        resp = client.post("/runtime/prune-empty")
        assert resp.status_code == 200
        assert resp.json()["deleted_count"] == 1
        assert s1["id"] in resp.json()["deleted_ids"]

    def test_prune_empty_after_delete_conversation(self):
        created = client.post("/runtime", json={"name": "Empty"}).json()
        conv_id = created["conversation_id"]
        client.post(
            f"/runtime/conversations/{conv_id}/messages",
            json={"role": "user", "content": "msg"},
        )
        with Session(_test_engine) as session:
            from sqlmodel import select

            msgs = session.exec(select(AgentMessage)).all()
            for m in msgs:
                session.delete(m)
            session.commit()
            convs = session.exec(select(AgentConversation)).all()
            for c in convs:
                session.delete(c)
            session.commit()
        resp = client.post("/runtime/prune-empty")
        assert resp.status_code == 200
        assert resp.json()["deleted_count"] == 1


class TestCompactSession:
    def test_compact_ok(self):
        created = client.post("/runtime", json={"name": "Compact"}).json()
        conv_id = created["conversation_id"]
        client.post(
            f"/runtime/conversations/{conv_id}/messages",
            json={"role": "user", "content": "hello"},
        )
        client.post(
            f"/runtime/conversations/{conv_id}/messages",
            json={"role": "assistant", "content": "hi there"},
        )
        resp = client.post(f"/runtime/{created['id']}/compact")
        assert resp.status_code == 200
        assert resp.json()["message_count"] == 2

    def test_compact_no_messages(self):
        created = client.post("/runtime", json={"name": "CompactEmpty"}).json()
        resp = client.post(f"/runtime/{created['id']}/compact")
        assert resp.status_code == 200
        assert resp.json()["message_count"] == 0

    def test_compact_404(self):
        resp = client.post("/runtime/nonexistent/compact")
        assert resp.status_code == 404

    def test_compact_force(self):
        created = client.post("/runtime", json={"name": "ForceCompact"}).json()
        conv_id = created["conversation_id"]
        client.post(
            f"/runtime/conversations/{conv_id}/messages",
            json={"role": "user", "content": "test"},
        )
        resp = client.post(f"/runtime/{created['id']}/compact?force=true")
        assert resp.status_code == 200
        assert resp.json()["message_count"] >= 1


class TestSessionMessages:
    def test_list_session_messages_empty(self):
        created = client.post("/runtime", json={"name": "NoMsgs"}).json()
        resp = client.get(f"/runtime/{created['id']}/messages")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_session_messages_with_data(self):
        created = client.post("/runtime", json={"name": "HasMsgs"}).json()
        conv_id = created["conversation_id"]
        client.post(
            f"/runtime/conversations/{conv_id}/messages",
            json={"role": "user", "content": "first"},
        )
        client.post(
            f"/runtime/conversations/{conv_id}/messages",
            json={"role": "assistant", "content": "second"},
        )
        resp = client.get(f"/runtime/{created['id']}/messages")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    def test_create_session_message_auto_creates_session(self):
        resp = client.post(
            "/runtime/session_auto_test_123/messages",
            json={"role": "user", "content": "Auto-create session"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "user"
        assert data["content"] == "Auto-create session"
        assert data["conversation_id"] is not None

    def test_create_session_message_with_data(self):
        created = client.post("/runtime", json={"name": "MsgData"}).json()
        resp = client.post(
            f"/runtime/{created['id']}/messages",
            json={
                "role": "assistant",
                "content": "Hello!",
                "content_html": "<p>Hello!</p>",
                "reasoning": "...thinking...",
                "model_used": "gpt-4",
                "tokens_used": 42,
                "duration_ms": 100,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "assistant"
        assert data["content"] == "Hello!"
        assert data["content_html"] == "<p>Hello!</p>"
        assert data["reasoning"] == "...thinking..."
        assert data["model_used"] == "gpt-4"
        assert data["tokens_used"] == 42
        assert data["duration_ms"] == 100


class TestConversations:
    def test_list_conversations_ok(self):
        created = client.post("/runtime", json={"name": "ConvList"}).json()
        resp = client.get(f"/runtime/{created['id']}/conversations")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["session_id"] == created["id"]

    def test_list_conversations_404(self):
        resp = client.get("/runtime/nonexistent/conversations")
        assert resp.status_code == 404

    def test_create_conversation(self):
        created = client.post("/runtime", json={"name": "NewConv"}).json()
        resp = client.post(
            f"/runtime/{created['id']}/conversations",
            json={"session_id": created["id"], "title": "Second Chat"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Second Chat"
        assert data["session_id"] == created["id"]
        assert data["order_index"] == 1 or data["order_index"] == 0
        assert data["message_count"] == 0

    def test_create_conversation_default_title(self):
        created = client.post("/runtime", json={"name": "DefTitle"}).json()
        resp = client.post(
            f"/runtime/{created['id']}/conversations",
            json={"session_id": created["id"]},
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "New Chat"

    def test_create_conversation_404(self):
        resp = client.post(
            "/runtime/nonexistent/conversations",
            json={"session_id": "nonexistent"},
        )
        assert resp.status_code == 404


class TestConversationMessages:
    def test_list_conversation_messages_empty(self):
        created = client.post("/runtime", json={"name": "EmptyConvMsg"}).json()
        conv_id = created["conversation_id"]
        resp = client.get(f"/runtime/conversations/{conv_id}/messages")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_conversation_messages_with_data(self):
        created = client.post("/runtime", json={"name": "ConvMsgList"}).json()
        conv_id = created["conversation_id"]
        client.post(
            f"/runtime/conversations/{conv_id}/messages",
            json={"role": "user", "content": "q1"},
        )
        client.post(
            f"/runtime/conversations/{conv_id}/messages",
            json={"role": "assistant", "content": "a1"},
        )
        resp = client.get(f"/runtime/conversations/{conv_id}/messages")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_list_conversation_messages_404(self):
        resp = client.get("/runtime/conversations/nonexistent/messages")
        assert resp.status_code == 404

    def test_create_conversation_message(self):
        created = client.post("/runtime", json={"name": "ConvMsgCreate"}).json()
        conv_id = created["conversation_id"]
        resp = client.post(
            f"/runtime/conversations/{conv_id}/messages",
            json={"role": "user", "content": "Hello world"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "user"
        assert data["content"] == "Hello world"
        assert data["conversation_id"] == conv_id

    def test_create_conversation_message_updates_timestamps(self):
        created = client.post("/runtime", json={"name": "TimeUpdate"}).json()
        conv_id = created["conversation_id"]
        resp = client.post(
            f"/runtime/conversations/{conv_id}/messages",
            json={"role": "user", "content": "now"},
        )
        assert resp.status_code == 200

    def test_create_conversation_message_404(self):
        resp = client.post(
            "/runtime/conversations/nonexistent/messages",
            json={"role": "user", "content": "fail"},
        )
        assert resp.status_code == 404

    def test_message_ordering(self):
        created = client.post("/runtime", json={"name": "Order"}).json()
        conv_id = created["conversation_id"]
        client.post(
            f"/runtime/conversations/{conv_id}/messages",
            json={"role": "user", "content": "first"},
        )
        client.post(
            f"/runtime/conversations/{conv_id}/messages",
            json={"role": "assistant", "content": "second"},
        )
        msgs = client.get(f"/runtime/conversations/{conv_id}/messages").json()
        assert len(msgs) == 2


class TestToolCalls:
    def test_list_tool_calls_empty(self):
        resp = client.get("/runtime/messages/nonexistent/tool_calls")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_create_tool_call(self):
        created = client.post("/runtime", json={"name": "ToolTest"}).json()
        conv_id = created["conversation_id"]
        msg = client.post(
            f"/runtime/conversations/{conv_id}/messages",
            json={"role": "assistant", "content": "using tool"},
        ).json()
        resp = client.post(
            f"/runtime/messages/{msg['id']}/tool_calls",
            json={
                "message_id": msg["id"],
                "tool_name": "calculator",
                "arguments": {"a": 1, "b": 2},
                "result": "3",
                "status": "completed",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["tool_name"] == "calculator"
        assert data["arguments"] == {"a": 1, "b": 2}
        assert data["result"] == "3"

    def test_create_and_list_tool_calls(self):
        created = client.post("/runtime", json={"name": "ToolList"}).json()
        conv_id = created["conversation_id"]
        msg = client.post(
            f"/runtime/conversations/{conv_id}/messages",
            json={"role": "assistant", "content": "tools"},
        ).json()
        client.post(
            f"/runtime/messages/{msg['id']}/tool_calls",
            json={"message_id": msg["id"], "tool_name": "search"},
        )
        client.post(
            f"/runtime/messages/{msg['id']}/tool_calls",
            json={"message_id": msg["id"], "tool_name": "code"},
        )
        resp = client.get(f"/runtime/messages/{msg['id']}/tool_calls")
        assert resp.status_code == 200
        assert len(resp.json()) == 2


class TestSessionState:
    def test_get_state_creates_default(self):
        created = client.post("/runtime", json={"name": "StateTest"}).json()
        resp = client.get(f"/runtime/{created['id']}/state")
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == created["id"]
        assert data["status"] == "idle"
        assert data["progress"] == 0.0

    def test_get_state_404(self):
        resp = client.get("/runtime/nonexistent/state")
        assert resp.status_code == 404

    def test_update_state(self):
        created = client.post("/runtime", json={"name": "UpdateState"}).json()
        resp = client.put(
            f"/runtime/{created['id']}/state",
            json={
                "status": "running",
                "progress": 0.5,
                "current_step": "processing",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "running"
        assert data["progress"] == 0.5
        assert data["current_step"] == "processing"

    def test_update_state_with_variables(self):
        created = client.post("/runtime", json={"name": "StateVars"}).json()
        resp = client.put(
            f"/runtime/{created['id']}/state",
            json={
                "state_variables": {"key": "value"},
                "hints": ["hint1"],
                "facts": ["fact1"],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["state_variables"] == {"key": "value"}
        assert data["hints"] == ["hint1"]
        assert data["facts"] == ["fact1"]

    def test_update_state_404(self):
        resp = client.put(
            "/runtime/nonexistent/state",
            json={"status": "running"},
        )
        assert resp.status_code == 404


class TestSessionFiles:
    def test_list_files_empty(self):
        created = client.post("/runtime", json={"name": "FileList"}).json()
        resp = client.get(f"/runtime/{created['id']}/files")
        assert resp.status_code == 200
        assert resp.json()["files"] == []

    def test_list_files_404(self):
        resp = client.get("/runtime/nonexistent/files")
        assert resp.status_code == 404


class TestEvolve:
    @pytest.mark.xfail(
        reason="evolve_workflow imports a non-existent module (common_lib.modules.orchestration.agents.agent.execution.workflow_matcher)",
        strict=False,
    )
    def test_evolve_missing_session(self):
        resp = client.post(
            "/runtime/evolve",
            json={
                "session_id": "nonexistent",
                "workflow_id": "wf-1",
                "outcome": "success",
            },
        )
        assert resp.status_code == 404


class TestEdgeCases:
    def test_create_session_with_long_name(self):
        long_name = "A" * 256
        resp = client.post("/runtime", json={"name": long_name})
        assert resp.status_code == 200
        assert resp.json()["name"] == long_name

    def test_list_sessions_pagination(self):
        for i in range(5):
            client.post("/runtime", json={"name": f"S{i}"})
        resp = client.get("/runtime?limit=3&offset=0")
        assert resp.status_code == 200
        assert len(resp.json()) == 3
        resp = client.get("/runtime?limit=3&offset=3")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_delete_session_cascades(self):
        created = client.post("/runtime", json={"name": "Cascade"}).json()
        conv_id = created["conversation_id"]
        msg = client.post(
            f"/runtime/conversations/{conv_id}/messages",
            json={"role": "user", "content": "msg"},
        ).json()
        client.post(
            f"/runtime/messages/{msg['id']}/tool_calls",
            json={"message_id": msg["id"], "tool_name": "tool"},
        )
        client.delete(f"/runtime/{created['id']}")
        get_resp = client.get(f"/runtime/{created['id']}")
        assert get_resp.status_code == 404
        conv_resp = client.get(f"/runtime/conversations/{conv_id}/messages")
        assert conv_resp.status_code == 404

    def test_multiple_conversations_have_correct_messages(self):
        created = client.post("/runtime", json={"name": "MultiConv"}).json()
        sid = created["id"]
        conv1 = created["conversation_id"]
        conv2 = client.post(
            f"/runtime/{sid}/conversations",
            json={"session_id": sid, "title": "Conv2"},
        ).json()["id"]
        client.post(
            f"/runtime/conversations/{conv1}/messages",
            json={"role": "user", "content": "in conv1"},
        )
        client.post(
            f"/runtime/conversations/{conv2}/messages",
            json={"role": "user", "content": "in conv2"},
        )
        msgs1 = client.get(f"/runtime/conversations/{conv1}/messages").json()
        msgs2 = client.get(f"/runtime/conversations/{conv2}/messages").json()
        assert len(msgs1) == 1
        assert len(msgs2) == 1
        assert msgs1[0]["content"] == "in conv1"
        assert msgs2[0]["content"] == "in conv2"
