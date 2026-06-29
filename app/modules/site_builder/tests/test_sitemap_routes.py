"""API tests for site_builder sitemap routes."""

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

_db_file = os.path.join(tempfile.gettempdir(), "test_site_sitemap_api.db")
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
from app.modules.site_builder.routes.sitemap_routes import router

app.include_router(router)
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


def _make_project():
    with Session(_test_engine) as s:
        p = SiteProject(name="Site", brief="desc")
        s.add(p)
        s.commit()
        s.refresh(p)
        return p.id


# --- GET /projects/{project_id}/sitemap ---


def test_get_sitemap_empty():
    pid = _make_project()
    resp = client.get(f"/projects/{pid}/sitemap")
    assert resp.status_code == 200
    assert resp.json()["data"]["pages"] == []


def test_get_sitemap_not_found():
    resp = client.get("/projects/nonexistent/sitemap")
    assert resp.status_code == 404


# --- POST /projects/{project_id}/sitemap/pages ---


def test_add_page():
    pid = _make_project()
    resp = client.post(
        f"/projects/{pid}/sitemap/pages", json={"title": "About", "slug": "/about"}
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["title"] == "About"


# --- DELETE /projects/{project_id}/sitemap/pages/{page_id} ---


def test_remove_page():
    pid = _make_project()
    create_resp = client.post(
        f"/projects/{pid}/sitemap/pages", json={"title": "P", "slug": "/p"}
    )
    page_id = create_resp.json()["data"]["id"]
    resp = client.delete(f"/projects/{pid}/sitemap/pages/{page_id}")
    assert resp.status_code == 200


# --- PUT /projects/{project_id}/sitemap/sections/{section_id} ---


def test_update_section():
    pid = _make_project()
    client.post(f"/projects/{pid}/sitemap/pages", json={"title": "P", "slug": "/p"})
    resp = client.get(f"/projects/{pid}/sitemap")
    sections = resp.json()["data"]["pages"][0]["sections"]
    if sections:
        sid = sections[0]["id"]
        resp2 = client.put(
            f"/projects/{pid}/sitemap/sections/{sid}", json={"intent": "hero_v2"}
        )
        assert resp2.status_code == 200
        assert resp2.json()["data"]["pages"][0]["sections"][0]["intent"] == "hero_v2"


# --- POST /projects/{project_id}/sitemap/generate ---


def test_generate_sitemap():
    pid = _make_project()
    resp = client.post(f"/projects/{pid}/sitemap/generate")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    # Should have created pages
    sitemap = client.get(f"/projects/{pid}/sitemap").json()
    assert len(sitemap["data"]["pages"]) > 0
