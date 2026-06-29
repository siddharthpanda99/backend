"""API tests for site_builder project routes."""

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
from common_lib.modules.site_builder.models.sitemap_models import (
    SiteProject,
    SitePage,
    SiteSection,
)

_db_file = os.path.join(tempfile.gettempdir(), "test_site_project_api.db")
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
from app.modules.site_builder.routes.project_routes import router

app.include_router(router, prefix="/site-projects")
app.dependency_overrides[get_db_session] = _override_get_session
client = TestClient(app)

_TABLES = [SiteProject, SitePage, SiteSection]


@pytest.fixture(autouse=True)
def setup_db():
    for model in _TABLES:
        model.__table__.create(_test_engine, checkfirst=True)
    yield
    for model in reversed(_TABLES):
        model.__table__.drop(_test_engine, checkfirst=True)


def _make_project(name="Test Site"):
    with Session(_test_engine) as s:
        p = SiteProject(name=name, brief="desc")
        s.add(p)
        s.commit()
        s.refresh(p)
        return p.id


# --- POST /site-projects ---


def test_create_project():
    resp = client.post("/site-projects", json={"name": "My Site", "brief": "A website"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["name"] == "My Site"


# --- GET /site-projects/{id} ---


def test_get_project():
    pid = _make_project()
    resp = client.get(f"/site-projects/{pid}")
    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "Test Site"


def test_get_project_not_found():
    resp = client.get("/site-projects/nonexistent")
    assert resp.status_code == 404


# --- GET /site-projects ---


def test_list_projects():
    _make_project("A")
    _make_project("B")
    resp = client.get("/site-projects")
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 2


# --- PUT /site-projects/{id} ---


def test_update_project():
    pid = _make_project()
    resp = client.put(f"/site-projects/{pid}", json={"name": "Updated"})
    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "Updated"


# --- DELETE /site-projects/{id} ---


def test_delete_project():
    pid = _make_project()
    resp = client.delete(f"/site-projects/{pid}")
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    # Verify gone
    resp2 = client.get(f"/site-projects/{pid}")
    assert resp2.status_code == 404
