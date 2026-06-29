"""API tests for skill routes using FastAPI TestClient."""

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
from common_lib.modules.agents.models.skill_models import WorkspaceSkill

_db_file = os.path.join(tempfile.gettempdir(), "test_skill_api.db")
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
from app.modules.agents.routes.skill_routes import router as skill_router

app.include_router(skill_router, prefix="/skills")

app.dependency_overrides[get_db_session] = _override_get_session

client = TestClient(app)

_SKILL_TABLES = [WorkspaceSkill]


@pytest.fixture(autouse=True)
def setup_db():
    for model in _SKILL_TABLES:
        model.__table__.create(_test_engine, checkfirst=True)
    yield
    for model in reversed(_SKILL_TABLES):
        model.__table__.drop(_test_engine, checkfirst=True)


# --- POST /scan ---


def test_scan_returns_discovered():
    resp = client.post("/skills/scan")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert isinstance(data["data"], list)


# --- POST /import ---


def test_import_creates_skill():
    resp = client.post(
        "/skills/import",
        json={
            "name": "new-skill",
            "source_path": "/tmp/new/SKILL.md",
            "skill_content": "content",
            "description": "desc",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["name"] == "new-skill"
    assert data["data"]["status"] == "imported"


# --- GET / ---


def test_list_empty():
    resp = client.get("/skills/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["data"] == []


def test_list_returns_all():
    client.post(
        "/skills/import",
        json={"name": "s1", "source_path": "/a/SKILL.md", "skill_content": "b1"},
    )
    client.post(
        "/skills/import",
        json={"name": "s2", "source_path": "/b/SKILL.md", "skill_content": "b2"},
    )
    resp = client.get("/skills/")
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 2


def test_list_filter_status():
    client.post(
        "/skills/import",
        json={"name": "s1", "source_path": "/a/SKILL.md", "skill_content": "b"},
    )
    resp = client.get("/skills/?status=imported")
    assert len(resp.json()["data"]) == 1


# --- GET /{skill_id} ---


def test_get_existing():
    import_resp = client.post(
        "/skills/import",
        json={"name": "get-me", "source_path": "/g/SKILL.md", "skill_content": "b"},
    )
    skill_id = import_resp.json()["data"]["id"]
    resp = client.get(f"/skills/{skill_id}")
    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "get-me"


def test_get_404():
    resp = client.get("/skills/nonexistent")
    assert resp.status_code == 404


# --- DELETE /{skill_id} ---


def test_archive():
    import_resp = client.post(
        "/skills/import",
        json={"name": "arch", "source_path": "/ar/SKILL.md", "skill_content": "b"},
    )
    skill_id = import_resp.json()["data"]["id"]
    resp = client.delete(f"/skills/{skill_id}")
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "archived"


def test_archive_404():
    resp = client.delete("/skills/nonexistent")
    assert resp.status_code == 404


# --- GET /agent/{agent_id} ---


def test_skills_for_agent():
    import json

    client.post(
        "/skills/import",
        json={
            "name": "for-claude",
            "source_path": "/a/SKILL.md",
            "skill_content": "b",
            "applicable_agents": json.dumps(["claude"]),
        },
    )
    client.post(
        "/skills/import",
        json={
            "name": "for-aider",
            "source_path": "/b/SKILL.md",
            "skill_content": "b",
            "applicable_agents": json.dumps(["aider"]),
        },
    )
    client.post(
        "/skills/import",
        json={
            "name": "no-filter",
            "source_path": "/c/SKILL.md",
            "skill_content": "b",
        },
    )
    resp = client.get("/skills/agent/claude")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 2
    names = {s["name"] for s in data}
    assert "for-claude" in names
    assert "no-filter" in names
