"""API tests for daemon routes using FastAPI TestClient."""

import os
import tempfile
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlalchemy.pool import NullPool

from common_lib.modules.data_storage.database.connection import (
    get_session as get_db_session,
)
from common_lib.modules.agents.models.daemon_models import DaemonRegistration
from common_lib.modules.agents.models.task_models import TaskRecord, TaskStatus

_db_file = os.path.join(tempfile.gettempdir(), "test_daemon_api.db")
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
from app.modules.agents.routes.daemon_routes import router as daemon_router

app.include_router(daemon_router, prefix="/daemons")

app.dependency_overrides[get_db_session] = _override_get_session

client = TestClient(app)

_DAEMON_TABLES = [DaemonRegistration, TaskRecord]


@pytest.fixture(autouse=True)
def setup_db():
    for model in _DAEMON_TABLES:
        model.__table__.create(_test_engine, checkfirst=True)
    yield
    for model in reversed(_DAEMON_TABLES):
        model.__table__.drop(_test_engine, checkfirst=True)


# --- POST /register ---


def test_register_daemon():
    resp = client.post(
        "/daemons/register",
        json={
            "agent_id": "agent-1",
            "hostname": "localhost",
            "available_clis": ["claude"],
            "capabilities": ["claude", "all"],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["agent_id"] == "agent-1"
    assert data["data"]["status"] == "online"


# --- POST /{daemon_id}/heartbeat ---


def test_heartbeat():
    reg = client.post(
        "/daemons/register",
        json={"agent_id": "a1", "hostname": "h1"},
    )
    daemon_id = reg.json()["data"]["id"]
    resp = client.post(f"/daemons/{daemon_id}/heartbeat")
    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_heartbeat_404():
    resp = client.post("/daemons/nonexistent/heartbeat")
    assert resp.status_code == 404


# --- DELETE /{daemon_id} ---


def test_deregister():
    reg = client.post(
        "/daemons/register",
        json={"agent_id": "a1", "hostname": "h1"},
    )
    daemon_id = reg.json()["data"]["id"]
    resp = client.delete(f"/daemons/{daemon_id}")
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "offline"


def test_deregister_404():
    resp = client.delete("/daemons/nonexistent")
    assert resp.status_code == 404


# --- GET / ---


def test_list_daemons():
    client.post("/daemons/register", json={"agent_id": "a1", "hostname": "h1"})
    client.post("/daemons/register", json={"agent_id": "a2", "hostname": "h2"})
    resp = client.get("/daemons/")
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 2


def test_list_filter_status():
    r1 = client.post("/daemons/register", json={"agent_id": "a1", "hostname": "h1"})
    client.post("/daemons/register", json={"agent_id": "a2", "hostname": "h2"})
    client.delete(f"/daemons/{r1.json()['data']['id']}")
    resp = client.get("/daemons/?status=online")
    assert len(resp.json()["data"]) == 1


# --- GET /{daemon_id}/tasks ---


def test_poll_tasks():
    reg = client.post("/daemons/register", json={"agent_id": "a1", "hostname": "h1"})
    daemon_id = reg.json()["data"]["id"]
    with Session(_test_engine) as session:
        task = TaskRecord(
            id=str(uuid.uuid4()),
            title="poll task",
            agent_id="a1",
            description="test",
            status=TaskStatus.QUEUED,
        )
        session.add(task)
        session.commit()
    resp = client.get(f"/daemons/{daemon_id}/tasks")
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 1


def test_poll_empty():
    reg = client.post("/daemons/register", json={"agent_id": "a1", "hostname": "h1"})
    daemon_id = reg.json()["data"]["id"]
    resp = client.get(f"/daemons/{daemon_id}/tasks")
    assert resp.status_code == 200
    assert resp.json()["data"] == []


# --- POST /{daemon_id}/tasks/{task_id}/result ---


def test_report_result():
    reg = client.post("/daemons/register", json={"agent_id": "a1", "hostname": "h1"})
    daemon_id = reg.json()["data"]["id"]
    with Session(_test_engine) as session:
        task = TaskRecord(
            id=str(uuid.uuid4()),
            title="result task",
            agent_id="a1",
            description="test",
            status=TaskStatus.IN_PROGRESS,
        )
        session.add(task)
        session.commit()
        task_id = task.id
    resp = client.post(
        f"/daemons/{daemon_id}/tasks/{task_id}/result",
        json={"status": "completed", "output": {"score": 100}},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "completed"


def test_report_result_404():
    reg = client.post("/daemons/register", json={"agent_id": "a1", "hostname": "h1"})
    daemon_id = reg.json()["data"]["id"]
    resp = client.post(
        f"/daemons/{daemon_id}/tasks/no-task/result",
        json={"status": "completed"},
    )
    assert resp.status_code == 404
