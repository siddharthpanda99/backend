"""Tests for context checkpoint routes."""

import os
import tempfile

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlalchemy.pool import NullPool

from common_lib.modules.data_storage.database.connection import (
    get_session as get_db_session,
)
from common_lib.modules.agents.models.checkpoint_models import ContextCheckpoint
from common_lib.modules.agents.services.checkpoint_service import CheckpointService

_db_file = os.path.join(tempfile.gettempdir(), "test_checkpoint_api.db")
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
from app.modules.agents.routes.checkpoint_routes import router as checkpoint_router

app.include_router(checkpoint_router, prefix="/checkpoints")
app.dependency_overrides[get_db_session] = _override_get_session

client = TestClient(app)

_TABLES = [ContextCheckpoint.__table__]


@pytest.fixture(autouse=True, scope="module")
def setup_db():
    SQLModel.metadata.create_all(_test_engine, tables=_TABLES)
    yield
    SQLModel.metadata.drop_all(_test_engine, tables=_TABLES)


def _seed_checkpoint(session, session_id="test-sess"):
    svc = CheckpointService()
    msgs = [
        {
            "id": f"m_{i}",
            "role": "user" if i % 2 == 0 else "assistant",
            "content": f"Msg {i}",
        }
        for i in range(10)
    ]
    return svc.create_surgical_checkpoint(session, session_id=session_id, messages=msgs)


class TestListCheckpoints:
    def test_empty(self):
        resp = client.get("/checkpoints/empty")
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    def test_returns_checkpoints(self):
        with Session(_test_engine) as s:
            _seed_checkpoint(s)
        resp = client.get("/checkpoints/test-sess")
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 1


class TestGetLatestCheckpoint:
    def test_none(self):
        resp = client.get("/checkpoints/empty/latest")
        assert resp.status_code == 200
        assert resp.json()["data"] is None

    def test_returns_latest(self):
        with Session(_test_engine) as s:
            _seed_checkpoint(s)
        resp = client.get("/checkpoints/test-sess/latest")
        assert resp.status_code == 200
        assert resp.json()["data"]["tier"] == "surgical"


class TestCheckThreshold:
    def test_under(self):
        resp = client.post(
            "/checkpoints/s1/check-threshold",
            json={"context_window_size": 10000, "current_token_count": 5000},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["threshold_exceeded"] is None

    def test_surgical(self):
        resp = client.post(
            "/checkpoints/s1/check-threshold",
            json={"context_window_size": 10000, "current_token_count": 7000},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["threshold_exceeded"] == "surgical"

    def test_destructive(self):
        resp = client.post(
            "/checkpoints/s1/check-threshold",
            json={"context_window_size": 10000, "current_token_count": 8500},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["threshold_exceeded"] == "destructive"
