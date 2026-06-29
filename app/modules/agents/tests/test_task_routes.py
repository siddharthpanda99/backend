"""API tests for task routes using FastAPI TestClient."""

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
from common_lib.modules.agents.models.task_models import TaskRecord, TaskAttempt

_db_file = os.path.join(tempfile.gettempdir(), "test_task_api.db")
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
from app.modules.agents.routes.task_routes import router as task_router

app.include_router(task_router, prefix="/tasks")

app.dependency_overrides[get_db_session] = _override_get_session

client = TestClient(app)

_TASK_TABLES = [TaskRecord, TaskAttempt]


@pytest.fixture(autouse=True)
def setup_db():
    for model in _TASK_TABLES:
        model.__table__.create(_test_engine, checkfirst=True)
    yield
    for model in reversed(_TASK_TABLES):
        model.__table__.drop(_test_engine, checkfirst=True)


# ── Create ─────────────────────────────────────────────────────────────────────


class TestCreateTask:
    def test_create_task_minimal(self):
        resp = client.post("/tasks/", json={"title": "Test task"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        task = data["data"]
        assert task["id"].startswith("task_")
        assert task["title"] == "Test task"
        assert task["status"] == "queued"
        assert task["priority"] == 0
        assert task["attempt_count"] == 0

    def test_create_task_full(self):
        resp = client.post(
            "/tasks/",
            json={
                "title": "Deploy",
                "description": "Deploy to prod",
                "agent_id": "agent-1",
                "priority": 5,
                "parent_task_id": "task_parent",
                "concurrency_key": "backend",
                "tags": ["deploy"],
                "metadata": {"env": "prod"},
                "max_attempts": 5,
            },
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["title"] == "Deploy"
        assert data["description"] == "Deploy to prod"
        assert data["agent_id"] == "agent-1"
        assert data["priority"] == 5
        assert data["parent_task_id"] == "task_parent"
        assert data["concurrency_key"] == "backend"
        assert data["tags"] == ["deploy"]
        assert data["metadata_json"] == {"env": "prod"}
        assert data["max_attempts"] == 5


# ── List ───────────────────────────────────────────────────────────────────────


class TestListTasks:
    def test_list_empty(self):
        resp = client.get("/tasks/")
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    def test_list_with_tasks(self):
        client.post("/tasks/", json={"title": "A"})
        client.post("/tasks/", json={"title": "B"})
        resp = client.get("/tasks/")
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 2

    def test_list_filter_status(self):
        r1 = client.post("/tasks/", json={"title": "Q"}).json()["data"]
        r2 = client.post("/tasks/", json={"title": "D"}).json()["data"]
        # Complete the second task
        client.post(f"/tasks/{r2['id']}/claim", json={"agent_id": "a"})
        client.post(f"/tasks/{r2['id']}/start", json={"agent_id": "a"})
        client.post(f"/tasks/{r2['id']}/complete", json={"agent_id": "a"})

        resp = client.get("/tasks/?status=queued")
        assert len(resp.json()["data"]) == 1
        assert resp.json()["data"][0]["id"] == r1["id"]

    def test_list_filter_agent(self):
        client.post("/tasks/", json={"title": "A", "agent_id": "x"})
        client.post("/tasks/", json={"title": "B", "agent_id": "y"})
        resp = client.get("/tasks/?agent_id=x")
        assert len(resp.json()["data"]) == 1

    def test_list_pagination(self):
        for i in range(5):
            client.post("/tasks/", json={"title": f"T{i}"})
        resp = client.get("/tasks/?limit=2&offset=0")
        assert len(resp.json()["data"]) == 2
        resp2 = client.get("/tasks/?limit=2&offset=2")
        assert len(resp2.json()["data"]) == 2


# ── Get ────────────────────────────────────────────────────────────────────────


class TestGetTask:
    def test_get_existing(self):
        created = client.post("/tasks/", json={"title": "Get me"}).json()["data"]
        resp = client.get(f"/tasks/{created['id']}")
        assert resp.status_code == 200
        assert resp.json()["data"]["id"] == created["id"]

    def test_get_not_found(self):
        resp = client.get("/tasks/task_nonexistent")
        assert resp.status_code == 404


# ── Claim ──────────────────────────────────────────────────────────────────────


class TestClaimTask:
    def test_claim_queued(self):
        created = client.post("/tasks/", json={"title": "Claim"}).json()["data"]
        resp = client.post(
            f"/tasks/{created['id']}/claim", json={"agent_id": "agent-1"}
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "claimed"
        assert resp.json()["data"]["agent_id"] == "agent-1"

    def test_claim_already_completed(self):
        created = client.post("/tasks/", json={"title": "Done"}).json()["data"]
        client.post(f"/tasks/{created['id']}/claim", json={"agent_id": "a"})
        client.post(f"/tasks/{created['id']}/start", json={"agent_id": "a"})
        client.post(f"/tasks/{created['id']}/complete", json={"agent_id": "a"})
        resp = client.post(f"/tasks/{created['id']}/claim", json={"agent_id": "b"})
        assert resp.status_code == 409

    def test_claim_not_found(self):
        resp = client.post("/tasks/task_ghost/claim", json={"agent_id": "a"})
        assert resp.status_code == 404


# ── Start ──────────────────────────────────────────────────────────────────────


class TestStartTask:
    def test_start_claimed(self):
        created = client.post("/tasks/", json={"title": "Start"}).json()["data"]
        client.post(f"/tasks/{created['id']}/claim", json={"agent_id": "agent-1"})
        resp = client.post(
            f"/tasks/{created['id']}/start",
            json={"agent_id": "agent-1", "session_id": "sess-1", "work_dir": "/tmp"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["status"] == "in_progress"
        assert data["attempt_count"] == 1

    def test_start_not_claimed(self):
        created = client.post("/tasks/", json={"title": "Not claimed"}).json()["data"]
        resp = client.post(f"/tasks/{created['id']}/start", json={"agent_id": "a"})
        assert resp.status_code == 409

    def test_start_wrong_agent(self):
        created = client.post("/tasks/", json={"title": "Mine"}).json()["data"]
        client.post(f"/tasks/{created['id']}/claim", json={"agent_id": "agent-1"})
        resp = client.post(
            f"/tasks/{created['id']}/start", json={"agent_id": "agent-2"}
        )
        assert resp.status_code == 409


# ── Complete ───────────────────────────────────────────────────────────────────


class TestCompleteTask:
    def test_complete_in_progress(self):
        created = client.post("/tasks/", json={"title": "Complete"}).json()["data"]
        client.post(f"/tasks/{created['id']}/claim", json={"agent_id": "a"})
        client.post(f"/tasks/{created['id']}/start", json={"agent_id": "a"})
        resp = client.post(
            f"/tasks/{created['id']}/complete",
            json={"agent_id": "a", "result_summary": "Done!"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "completed"

    def test_complete_wrong_agent(self):
        created = client.post("/tasks/", json={"title": "Not yours"}).json()["data"]
        client.post(f"/tasks/{created['id']}/claim", json={"agent_id": "a"})
        client.post(f"/tasks/{created['id']}/start", json={"agent_id": "a"})
        resp = client.post(f"/tasks/{created['id']}/complete", json={"agent_id": "b"})
        assert resp.status_code == 409


# ── Fail ───────────────────────────────────────────────────────────────────────


class TestFailTask:
    def test_fail_logic_terminal(self):
        created = client.post("/tasks/", json={"title": "Fail"}).json()["data"]
        client.post(f"/tasks/{created['id']}/claim", json={"agent_id": "a"})
        client.post(f"/tasks/{created['id']}/start", json={"agent_id": "a"})
        resp = client.post(
            f"/tasks/{created['id']}/fail",
            json={
                "agent_id": "a",
                "error_message": "Compile error",
                "failure_type": "logic",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "failed"

    def test_fail_infra_requeues(self):
        created = client.post("/tasks/", json={"title": "Timeout"}).json()["data"]
        client.post(f"/tasks/{created['id']}/claim", json={"agent_id": "a"})
        client.post(f"/tasks/{created['id']}/start", json={"agent_id": "a"})
        resp = client.post(
            f"/tasks/{created['id']}/fail",
            json={
                "agent_id": "a",
                "error_message": "Timeout",
                "failure_type": "timeout",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "queued"


# ── Cancel ─────────────────────────────────────────────────────────────────────


class TestCancelTask:
    def test_cancel_queued(self):
        created = client.post("/tasks/", json={"title": "Cancel"}).json()["data"]
        resp = client.post(f"/tasks/{created['id']}/cancel")
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "cancelled"

    def test_cancel_completed_rejected(self):
        created = client.post("/tasks/", json={"title": "Done"}).json()["data"]
        client.post(f"/tasks/{created['id']}/claim", json={"agent_id": "a"})
        client.post(f"/tasks/{created['id']}/start", json={"agent_id": "a"})
        client.post(f"/tasks/{created['id']}/complete", json={"agent_id": "a"})
        resp = client.post(f"/tasks/{created['id']}/cancel")
        assert resp.status_code == 409


# ── Attempts ───────────────────────────────────────────────────────────────────


class TestGetAttempts:
    def test_get_attempts_empty(self):
        created = client.post("/tasks/", json={"title": "No attempts"}).json()["data"]
        resp = client.get(f"/tasks/{created['id']}/attempts")
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    def test_get_attempts_after_start(self):
        created = client.post("/tasks/", json={"title": "Has attempt"}).json()["data"]
        client.post(f"/tasks/{created['id']}/claim", json={"agent_id": "a"})
        client.post(f"/tasks/{created['id']}/start", json={"agent_id": "a"})
        resp = client.get(f"/tasks/{created['id']}/attempts")
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 1

    def test_get_attempts_not_found(self):
        resp = client.get("/tasks/task_ghost/attempts")
        assert resp.status_code == 404


# ── Active Count ───────────────────────────────────────────────────────────────


class TestActiveCount:
    def test_active_count_zero(self):
        resp = client.get("/tasks/agent/new-agent/active-count")
        assert resp.status_code == 200
        assert resp.json()["data"]["active_count"] == 0

    def test_active_count_after_tasks(self):
        for _ in range(3):
            r = client.post("/tasks/", json={"title": "X"}).json()["data"]
            client.post(f"/tasks/{r['id']}/claim", json={"agent_id": "busy-agent"})
            client.post(f"/tasks/{r['id']}/start", json={"agent_id": "busy-agent"})
        resp = client.get("/tasks/agent/busy-agent/active-count")
        assert resp.json()["data"]["active_count"] == 3
