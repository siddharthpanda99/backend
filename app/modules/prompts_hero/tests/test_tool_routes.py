"""API tests for prompts_hero tool routes."""

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
from common_lib.modules.prompt_studio.prompts_hero.models.tool_models import PromptTool

_db_file = os.path.join(tempfile.gettempdir(), "test_ph_tool_api.db")
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
from app.modules.prompts_hero.routes.tool_routes import router

app.include_router(router, prefix="/prompts-hero")
app.dependency_overrides[get_db_session] = _override_get_session
client = TestClient(app)

_TABLES = [PromptTool]


@pytest.fixture(autouse=True)
def setup_db():
    for model in _TABLES:
        model.__table__.create(_test_engine, checkfirst=True)
    yield
    for model in reversed(_TABLES):
        model.__table__.drop(_test_engine, checkfirst=True)


def _make_tool(name="AI Tool", slug="ai-tool", category="images"):
    with Session(_test_engine) as s:
        tool = PromptTool(name=name, slug=slug, category=category)
        s.add(tool)
        s.commit()
        s.refresh(tool)
        return tool.id


# --- GET /tools ---


def test_list_tools_empty():
    resp = client.get("/prompts-hero/tools")
    assert resp.status_code == 200
    assert resp.json()["data"] == []


def test_list_tools():
    _make_tool("Tool A", "tool-a", "images")
    _make_tool("Tool B", "tool-b", "edit")
    resp = client.get("/prompts-hero/tools")
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 2


# --- GET /tools/{tool_id} ---


def test_get_tool():
    tid = _make_tool()
    resp = client.get(f"/prompts-hero/tools/{tid}")
    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "AI Tool"


def test_get_tool_not_found():
    resp = client.get("/prompts-hero/tools/nonexistent")
    assert resp.status_code == 404


# --- GET /tools/slug/{slug} ---


def test_get_tool_by_slug():
    _make_tool(slug="face-swap")
    resp = client.get("/prompts-hero/tools/slug/face-swap")
    assert resp.status_code == 200
    assert resp.json()["data"]["slug"] == "face-swap"


# --- POST /tools ---


def test_create_tool():
    resp = client.post(
        "/prompts-hero/tools",
        json={
            "name": "Sticker Maker",
            "slug": "sticker-maker",
            "category": "fun",
            "description": "Make stickers",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "Sticker Maker"


# --- POST /tools/seed ---


def test_seed_tools():
    resp = client.post("/prompts-hero/tools/seed")
    assert resp.status_code == 200
    assert resp.json()["data"]["counted"] > 0


# --- DELETE /tools/{tool_id} ---


def test_delete_tool():
    tid = _make_tool()
    resp = client.delete(f"/prompts-hero/tools/{tid}")
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    resp2 = client.get(f"/prompts-hero/tools/{tid}")
    assert resp2.status_code == 404
