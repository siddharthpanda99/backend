"""Tests for doom loop detection routes."""

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
from common_lib.modules.agents.models.doom_loop_models import DoomLoopEvent
from common_lib.modules.agents.services.doom_loop_service import DoomLoopService

_db_file = os.path.join(tempfile.gettempdir(), "test_doom_loop_api.db")
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
from app.modules.agents.routes.doom_loop_routes import router as doom_loop_router

app.include_router(doom_loop_router, prefix="/doom-loops")
app.dependency_overrides[get_db_session] = _override_get_session

client = TestClient(app)

_TABLES = [DoomLoopEvent.__table__]


@pytest.fixture(autouse=True, scope="module")
def setup_db():
    SQLModel.metadata.create_all(_test_engine, tables=_TABLES)
    yield
    SQLModel.metadata.drop_all(_test_engine, tables=_TABLES)


def _seed_event(session, session_id="test-sess"):
    svc = DoomLoopService()
    return svc.record_event(
        session,
        session_id=session_id,
        tool_calls=[{"tool_name": "search", "arguments": '{"q":"x"}'}],
        detection={"period": 1, "occurrences": 3, "signatures": ["a", "a", "a"]},
    )


class TestListEvents:
    def test_empty(self):
        resp = client.get("/doom-loops/events?session_id=empty")
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    def test_returns_events(self):
        with Session(_test_engine) as s:
            _seed_event(s)
            _seed_event(s)
        resp = client.get("/doom-loops/events?session_id=test-sess")
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 2


class TestGetStats:
    def test_stats(self):
        with Session(_test_engine) as s:
            _seed_event(s, "s1")
        resp = client.get("/doom-loops/stats/s1")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total_events"] == 1
        assert data["session_id"] == "s1"

    def test_stats_empty(self):
        resp = client.get("/doom-loops/stats/empty")
        assert resp.status_code == 200
        assert resp.json()["data"]["total_events"] == 0
