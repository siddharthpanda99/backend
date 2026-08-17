"""API tests for prompts_hero gamification routes."""

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
from common_lib.modules.prompt_studio.prompts_hero.models.gamification_models import (
    UserStreak,
    UserBadge,
    UserBadgeAward,
)

_db_file = os.path.join(tempfile.gettempdir(), "test_ph_gamification_api.db")
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
from app.modules.prompts_hero.routes.gamification_routes import router

app.include_router(router, prefix="/prompts-hero")
app.dependency_overrides[get_db_session] = _override_get_session
client = TestClient(app)

_TABLES = [UserStreak, UserBadge, UserBadgeAward]


@pytest.fixture(autouse=True)
def setup_db():
    for model in _TABLES:
        model.__table__.create(_test_engine, checkfirst=True)
    yield
    for model in reversed(_TABLES):
        model.__table__.drop(_test_engine, checkfirst=True)


# --- GET /streak/{user_id} ---


def test_get_streak():
    resp = client.get("/prompts-hero/streak/user-1")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["current_streak"] == 0
    assert data["total_actions"] == 0


# --- POST /streak/activity ---


def test_record_activity():
    resp = client.post(
        "/prompts-hero/streak/activity",
        json={"user_id": "user-1"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["streak"] == 1


# --- GET /badges ---


def test_list_badges_empty():
    resp = client.get("/prompts-hero/badges")
    assert resp.status_code == 200
    assert resp.json()["data"] == []


# --- GET /badges/user/{user_id} ---


def test_list_user_badges_empty():
    resp = client.get("/prompts-hero/badges/user/user-1")
    assert resp.status_code == 200
    assert resp.json()["data"] == []


# --- POST /badges/seed ---


def test_seed_badges():
    resp = client.post("/prompts-hero/badges/seed")
    assert resp.status_code == 200
    assert resp.json()["data"]["counted"] > 0

    resp2 = client.get("/prompts-hero/badges")
    assert len(resp2.json()["data"]) > 0


# --- GET /profile/{user_id} ---


def test_get_profile_summary():
    client.post("/prompts-hero/streak/activity", json={"user_id": "user-1"})
    resp = client.get("/prompts-hero/profile/user-1")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["user_id"] == "user-1"
    assert data["current_streak"] >= 1
    assert data["badges_count"] == 0
