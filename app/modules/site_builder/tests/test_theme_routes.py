"""API tests for site_builder theme routes."""

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
from common_lib.modules.site_builder.models.theme_models import SiteTheme

_db_file = os.path.join(tempfile.gettempdir(), "test_site_theme_api.db")
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
from app.modules.site_builder.routes.theme_routes import router

app.include_router(router)
app.dependency_overrides[get_db_session] = _override_get_session
client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    SiteTheme.__table__.create(_test_engine, checkfirst=True)
    yield
    SiteTheme.__table__.drop(_test_engine, checkfirst=True)


# --- POST /themes ---


def test_create_theme():
    resp = client.post("/themes", json={"name": "Dark Theme"})
    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "Dark Theme"


# --- GET /themes ---


def test_list_themes():
    client.post("/themes", json={"name": "T1"})
    client.post("/themes", json={"name": "T2"})
    resp = client.get("/themes")
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 2


# --- GET /themes/{id} ---


def test_get_theme():
    create_resp = client.post("/themes", json={"name": "Get Me"})
    tid = create_resp.json()["data"]["id"]
    resp = client.get(f"/themes/{tid}")
    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "Get Me"


# --- PUT /themes/{id} ---


def test_update_theme():
    create_resp = client.post("/themes", json={"name": "Old"})
    tid = create_resp.json()["data"]["id"]
    resp = client.put(f"/themes/{tid}", json={"name": "New"})
    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "New"


# --- DELETE /themes/{id} ---


def test_delete_theme():
    create_resp = client.post("/themes", json={"name": "Del"})
    tid = create_resp.json()["data"]["id"]
    resp = client.delete(f"/themes/{tid}")
    assert resp.status_code == 200


# --- POST /themes/{id}/presets/{preset_name} ---


def test_apply_preset():
    create_resp = client.post("/themes", json={"name": "Preset Test"})
    tid = create_resp.json()["data"]["id"]
    resp = client.post(f"/themes/{tid}/presets/dark_mode")
    assert resp.status_code == 200
    assert resp.json()["data"]["tokens_json"]["color-bg"] == "#0f172a"
