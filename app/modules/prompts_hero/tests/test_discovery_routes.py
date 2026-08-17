"""API tests for prompts_hero discovery routes."""

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
from common_lib.modules.prompt_studio.prompts_hero.models.generation_models import PromptGeneration
from common_lib.modules.prompt_studio.prompts_hero.models.share_models import PromptShare

_db_file = os.path.join(tempfile.gettempdir(), "test_ph_discovery_api.db")
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
from app.modules.prompts_hero.routes.discovery_routes import router

app.include_router(router, prefix="/prompts-hero")
app.dependency_overrides[get_db_session] = _override_get_session
client = TestClient(app)

_TABLES = [PromptGeneration, PromptShare]


@pytest.fixture(autouse=True)
def setup_db():
    for model in _TABLES:
        model.__table__.create(_test_engine, checkfirst=True)
    yield
    for model in reversed(_TABLES):
        model.__table__.drop(_test_engine, checkfirst=True)


def _make_generation(
    user_id="user-1", prompt_text="a cat", model_id="sd15", is_public=True
):
    with Session(_test_engine) as s:
        gen = PromptGeneration(
            user_id=user_id,
            prompt_text=prompt_text,
            model_id=model_id,
            is_public=is_public,
        )
        s.add(gen)
        s.commit()
        s.refresh(gen)
        return gen.id


# --- GET /feed ---


def test_get_feed_empty():
    resp = client.get("/prompts-hero/feed")
    assert resp.status_code == 200
    assert resp.json()["data"] == []


def test_get_feed_returns_public_generations():
    _make_generation(prompt_text="sunset")
    _make_generation(prompt_text="mountain")
    _make_generation(user_id="user-2", prompt_text="private", is_public=False)
    resp = client.get("/prompts-hero/feed")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 2


# --- POST /generations/{id}/share ---


def test_share_generation():
    gid = _make_generation()
    resp = client.post(
        f"/prompts-hero/generations/{gid}/share",
        json={"user_id": "user-1", "title": "Cool art"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["title"] == "Cool art"


# --- GET /featured ---


def test_list_featured_empty():
    resp = client.get("/prompts-hero/featured")
    assert resp.status_code == 200
    assert resp.json()["data"] == []
