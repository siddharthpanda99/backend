"""API tests for prompts_hero community routes."""

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
from common_lib.modules.prompts_hero.models.generation_models import PromptGeneration
from common_lib.modules.prompts_hero.models.community_models import (
    PromptLike,
    PromptComment,
    PromptCollection,
    PromptCollectionItem,
)

_db_file = os.path.join(tempfile.gettempdir(), "test_ph_community_api.db")
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
from app.modules.prompts_hero.routes.community_routes import router

app.include_router(router, prefix="/prompts-hero")
app.dependency_overrides[get_db_session] = _override_get_session
client = TestClient(app)

_TABLES = [
    PromptGeneration,
    PromptLike,
    PromptComment,
    PromptCollection,
    PromptCollectionItem,
]


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


def _make_collection(user_id="user-1", name="My Collection"):
    with Session(_test_engine) as s:
        col = PromptCollection(user_id=user_id, name=name)
        s.add(col)
        s.commit()
        s.refresh(col)
        return col.id


# --- POST /generations/{id}/like ---


def test_like_generation():
    gid = _make_generation()
    resp = client.post(
        f"/prompts-hero/generations/{gid}/like",
        json={"user_id": "user-1"},
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_like_generation_duplicate():
    gid = _make_generation()
    client.post(f"/prompts-hero/generations/{gid}/like", json={"user_id": "user-1"})
    resp = client.post(
        f"/prompts-hero/generations/{gid}/like",
        json={"user_id": "user-1"},
    )
    assert resp.status_code == 409


# --- DELETE /generations/{id}/like ---


def test_unlike_generation():
    gid = _make_generation()
    client.post(f"/prompts-hero/generations/{gid}/like", json={"user_id": "user-1"})
    resp = client.request(
        "DELETE",
        f"/prompts-hero/generations/{gid}/like",
        json={"user_id": "user-1"},
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


# --- POST /generations/{id}/comments ---


def test_add_comment():
    gid = _make_generation()
    resp = client.post(
        f"/prompts-hero/generations/{gid}/comments",
        json={"user_id": "user-1", "content": "Great prompt!"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["content"] == "Great prompt!"


# --- GET /generations/{id}/comments ---


def test_list_comments():
    gid = _make_generation()
    client.post(
        f"/prompts-hero/generations/{gid}/comments",
        json={"user_id": "user-1", "content": "Nice"},
    )
    client.post(
        f"/prompts-hero/generations/{gid}/comments",
        json={"user_id": "user-2", "content": "Love it"},
    )
    resp = client.get(f"/prompts-hero/generations/{gid}/comments")
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 2


# --- POST /collections ---


def test_create_collection():
    resp = client.post(
        "/prompts-hero/collections",
        json={"user_id": "user-1", "name": "Favorites", "description": "Best stuff"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "Favorites"


# --- POST /collections/{id}/items ---


def test_add_to_collection_and_list():
    col_id = _make_collection()
    gid = _make_generation()
    resp = client.post(
        f"/prompts-hero/collections/{col_id}/items",
        json={"generation_id": gid, "note": "top pick"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["generation_id"] == gid

    resp2 = client.get(f"/prompts-hero/collections/{col_id}/items")
    assert resp2.status_code == 200
    assert len(resp2.json()["data"]) == 1


# --- DELETE /collections/{id}/items/{gen_id} ---


def test_remove_from_collection():
    col_id = _make_collection()
    gid = _make_generation()
    client.post(
        f"/prompts-hero/collections/{col_id}/items",
        json={"generation_id": gid},
    )
    resp = client.delete(f"/prompts-hero/collections/{col_id}/items/{gid}")
    assert resp.status_code == 200
    assert resp.json()["success"] is True

    resp2 = client.get(f"/prompts-hero/collections/{col_id}/items")
    assert len(resp2.json()["data"]) == 0
