"""API tests for site_builder export routes."""

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
from common_lib.modules.site_builder.models.registry_models import SiteSectionBlock

_db_file = os.path.join(tempfile.gettempdir(), "test_site_export_api.db")
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
from app.modules.site_builder.routes.export_routes import router

app.include_router(router)
app.dependency_overrides[get_db_session] = _override_get_session
client = TestClient(app)

_TABLES = [SiteProject, SitePage, SiteSection, SiteSectionBlock]


@pytest.fixture(autouse=True)
def setup_db():
    for model in _TABLES:
        model.__table__.create(_test_engine, checkfirst=True)
    yield
    for model in reversed(_TABLES):
        model.__table__.drop(_test_engine, checkfirst=True)


def _make_project_with_sections():
    with Session(_test_engine) as s:
        p = SiteProject(name="Export Site", brief="desc")
        s.add(p)
        s.flush()
        page = SitePage(project_id=p.id, title="Home", slug="/", order_index=0)
        s.add(page)
        s.flush()
        block = SiteSectionBlock(
            id="hero-b", name="Hero", category="hero", layout="stack"
        )
        s.add(block)
        sec = SiteSection(
            page_id=page.id, intent="hero", block_id="hero-b", order_index=0
        )
        s.add(sec)
        s.commit()
        return p.id


# --- POST /projects/{project_id}/export/json ---


def test_export_json():
    pid = _make_project_with_sections()
    resp = client.post(f"/projects/{pid}/export/json")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "project" in data
    assert "pages" in data


# --- POST /projects/{project_id}/export/react ---


def test_export_react():
    pid = _make_project_with_sections()
    resp = client.post(f"/projects/{pid}/export/react")
    assert resp.status_code == 200
    files = resp.json()["data"]["files"]
    assert len(files) > 0
    paths = [f["path"] for f in files]
    assert "package.json" in paths


# --- POST /projects/{project_id}/export/html ---


def test_export_html():
    pid = _make_project_with_sections()
    resp = client.post(f"/projects/{pid}/export/html")
    assert resp.status_code == 200
    files = resp.json()["data"]["files"]
    assert len(files) == 1
    assert "index.html" in files[0]["path"]


# --- POST /projects/{project_id}/export/figma ---


def test_export_figma():
    pid = _make_project_with_sections()
    resp = client.post(
        f"/projects/{pid}/export/figma",
        json={"figma_token": "tok", "figma_file_key": "key"},
    )
    assert resp.status_code == 200
    assert "figma_url" in resp.json()["data"]


# --- Export nonexistent project ---


def test_export_nonexistent():
    resp = client.post("/projects/nonexistent/export/json")
    assert resp.status_code == 404
