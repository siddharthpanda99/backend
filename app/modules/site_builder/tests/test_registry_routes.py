"""API tests for site_builder registry routes."""

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
from common_lib.modules.site_builder.models.registry_models import SiteSectionBlock

_db_file = os.path.join(tempfile.gettempdir(), "test_site_registry_api.db")
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
from app.modules.site_builder.routes.registry_routes import router

app.include_router(router)
app.dependency_overrides[get_db_session] = _override_get_session
client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    SiteSectionBlock.__table__.create(_test_engine, checkfirst=True)
    yield
    SiteSectionBlock.__table__.drop(_test_engine, checkfirst=True)


# --- GET /registry ---


def test_list_blocks_empty():
    resp = client.get("/registry")
    assert resp.status_code == 200
    assert resp.json()["data"] == []


def test_list_blocks_with_data():
    with Session(_test_engine) as s:
        s.add(SiteSectionBlock(id="b1", name="Hero", category="hero"))
        s.commit()
    resp = client.get("/registry")
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 1


# --- GET /registry/search ---


def test_search_blocks():
    with Session(_test_engine) as s:
        s.add(
            SiteSectionBlock(
                id="b1", name="Hero Section", category="hero", intent_tags=["hero"]
            )
        )
        s.commit()
    resp = client.get("/registry/search", params={"intent": "hero"})
    assert resp.status_code == 200
    assert len(resp.json()["data"]) >= 1


# --- GET /registry/{block_id} ---


def test_get_block():
    with Session(_test_engine) as s:
        s.add(SiteSectionBlock(id="b1", name="CTA", category="cta"))
        s.commit()
    resp = client.get("/registry/b1")
    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "CTA"


def test_get_block_not_found():
    resp = client.get("/registry/nonexistent")
    assert resp.status_code == 404
