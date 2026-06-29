"""Tests for tool artifact routes."""

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
from common_lib.modules.agents.models.tool_artifact_models import ToolArtifact
from common_lib.modules.agents.services.tool_artifact_service import ToolArtifactService

_db_file = os.path.join(tempfile.gettempdir(), "test_tool_artifact_api.db")
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
from app.modules.agents.routes.tool_artifact_routes import (
    router as tool_artifact_router,
)

app.include_router(tool_artifact_router, prefix="/tool-artifacts")
app.dependency_overrides[get_db_session] = _override_get_session

client = TestClient(app)

_TABLES = [ToolArtifact.__table__]


@pytest.fixture(autouse=True, scope="module")
def setup_db():
    SQLModel.metadata.create_all(_test_engine, tables=_TABLES)
    yield
    SQLModel.metadata.drop_all(_test_engine, tables=_TABLES)


def _seed_artifact(session):
    svc = ToolArtifactService()
    return svc.archive_output(
        session, session_id="test-sess", tool_name="big_tool", output="X" * 20000
    )


class TestListArtifacts:
    def test_empty(self):
        resp = client.get("/tool-artifacts/?session_id=empty")
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    def test_returns_artifacts(self):
        with Session(_test_engine) as s:
            _seed_artifact(s)
        resp = client.get("/tool-artifacts/?session_id=test-sess")
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 1


class TestGetArtifact:
    def test_existing(self):
        with Session(_test_engine) as s:
            result = _seed_artifact(s)
        resp = client.get(f"/tool-artifacts/{result['artifact_id']}")
        assert resp.status_code == 200
        assert resp.json()["data"]["tool_name"] == "big_tool"

    def test_not_found(self):
        resp = client.get("/tool-artifacts/nonexistent")
        assert resp.status_code == 404


class TestGetPreview:
    def test_existing(self):
        with Session(_test_engine) as s:
            result = _seed_artifact(s)
        resp = client.get(f"/tool-artifacts/{result['artifact_id']}/preview")
        assert resp.status_code == 200
        assert "preview" in resp.json()["data"]

    def test_not_found(self):
        resp = client.get("/tool-artifacts/nonexistent/preview")
        assert resp.status_code == 404


class TestDeleteArtifact:
    def test_delete(self):
        with Session(_test_engine) as s:
            result = _seed_artifact(s)
        resp = client.delete(f"/tool-artifacts/{result['artifact_id']}")
        assert resp.status_code == 200
        assert resp.json()["data"]["deleted"] is True

    def test_delete_not_found(self):
        resp = client.delete("/tool-artifacts/nonexistent")
        assert resp.status_code == 404
