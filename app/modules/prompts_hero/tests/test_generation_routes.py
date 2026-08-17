"""API tests for prompts_hero generation routes."""

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

_db_file = os.path.join(tempfile.gettempdir(), "test_ph_generation_api.db")
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
from app.modules.prompts_hero.routes.generation_routes import router

app.include_router(router, prefix="/prompts-hero")
app.dependency_overrides[get_db_session] = _override_get_session
client = TestClient(app)

_TABLES = [PromptGeneration]


@pytest.fixture(autouse=True)
def setup_db():
    for model in _TABLES:
        model.__table__.create(_test_engine, checkfirst=True)
    yield
    for model in reversed(_TABLES):
        model.__table__.drop(_test_engine, checkfirst=True)


def _make_generation(user_id="user-1", prompt_text="a cat", model_id="sd15"):
    with Session(_test_engine) as s:
        gen = PromptGeneration(
            user_id=user_id, prompt_text=prompt_text, model_id=model_id
        )
        s.add(gen)
        s.commit()
        s.refresh(gen)
        return gen.id


# --- POST /generations ---


def test_create_generation():
    resp = client.post(
        "/prompts-hero/generations",
        json={
            "user_id": "user-1",
            "prompt_text": "a beautiful sunset",
            "model_id": "sdxl",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["prompt_text"] == "a beautiful sunset"
    assert data["data"]["model_id"] == "sdxl"


# --- GET /generations/{generation_id} ---


def test_get_generation():
    gid = _make_generation()
    resp = client.get(f"/prompts-hero/generations/{gid}")
    assert resp.status_code == 200
    assert resp.json()["data"]["prompt_text"] == "a cat"


def test_get_generation_not_found():
    resp = client.get("/prompts-hero/generations/nonexistent")
    assert resp.status_code == 404


# --- GET /generations/user/{user_id} ---


def test_list_user_generations():
    _make_generation(user_id="u1")
    _make_generation(user_id="u1")
    _make_generation(user_id="u2")
    resp = client.get("/prompts-hero/generations/user/u1")
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 2


# --- DELETE /generations/{generation_id} ---


def test_delete_generation():
    gid = _make_generation()
    resp = client.delete(f"/prompts-hero/generations/{gid}")
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    resp2 = client.get(f"/prompts-hero/generations/{gid}")
    assert resp2.status_code == 404


# --- PUT /generations/{generation_id}/visibility ---


def test_update_visibility():
    gid = _make_generation()
    resp = client.put(
        f"/prompts-hero/generations/{gid}/visibility",
        json={"is_public": False},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["is_public"] is False
    assert resp.json()["data"]["is_private"] is True
