"""API tests for agent profile routes using FastAPI TestClient."""

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
from common_lib.modules.agents.models.profile_models import AgentProfile

_db_file = os.path.join(tempfile.gettempdir(), "test_profile_api.db")
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
from app.modules.agents.routes.profile_routes import router as profile_router

app.include_router(profile_router, prefix="/profiles")

app.dependency_overrides[get_db_session] = _override_get_session

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    AgentProfile.__table__.create(_test_engine, checkfirst=True)
    yield
    AgentProfile.__table__.drop(_test_engine, checkfirst=True)


# ── Create ─────────────────────────────────────────────────────────────────────


class TestCreateProfile:
    def test_create_minimal(self):
        resp = client.post("/profiles/", json={"display_name": "Agent A"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        p = data["data"]
        assert p["id"].startswith("profile_")
        assert p["display_name"] == "Agent A"
        assert p["status"] == "offline"
        assert p["concurrency_limit"] == 5
        assert p["roles"] == []

    def test_create_full(self):
        resp = client.post(
            "/profiles/",
            json={
                "display_name": "Agent Beta",
                "avatar_url": "https://example.com/avatar.png",
                "description": "Backend specialist",
                "roles": ["backend", "devops"],
                "capabilities": ["python", "docker"],
                "status": "online",
                "runtime_info": {"cli": "claude"},
                "concurrency_limit": 3,
                "metadata": {"team": "platform"},
            },
        )
        assert resp.status_code == 200
        p = resp.json()["data"]
        assert p["display_name"] == "Agent Beta"
        assert p["avatar_url"] == "https://example.com/avatar.png"
        assert p["roles"] == ["backend", "devops"]
        assert p["status"] == "online"
        assert p["concurrency_limit"] == 3


# ── List ───────────────────────────────────────────────────────────────────────


class TestListProfiles:
    def test_list_empty(self):
        resp = client.get("/profiles/")
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    def test_list_with_profiles(self):
        client.post("/profiles/", json={"display_name": "A"})
        client.post("/profiles/", json={"display_name": "B"})
        resp = client.get("/profiles/")
        assert len(resp.json()["data"]) == 2

    def test_list_filter_status(self):
        client.post("/profiles/", json={"display_name": "On", "status": "online"})
        client.post("/profiles/", json={"display_name": "Off", "status": "offline"})
        resp = client.get("/profiles/?status=online")
        assert len(resp.json()["data"]) == 1

    def test_list_filter_role(self):
        client.post("/profiles/", json={"display_name": "BE", "roles": ["backend"]})
        client.post("/profiles/", json={"display_name": "FE", "roles": ["frontend"]})
        resp = client.get("/profiles/?role=backend")
        assert len(resp.json()["data"]) == 1

    def test_list_pagination(self):
        for i in range(5):
            client.post("/profiles/", json={"display_name": f"P{i}"})
        resp = client.get("/profiles/?limit=2&offset=0")
        assert len(resp.json()["data"]) == 2


# ── Get ────────────────────────────────────────────────────────────────────────


class TestGetProfile:
    def test_get_existing(self):
        created = client.post("/profiles/", json={"display_name": "Get Me"}).json()[
            "data"
        ]
        resp = client.get(f"/profiles/{created['id']}")
        assert resp.status_code == 200
        assert resp.json()["data"]["id"] == created["id"]

    def test_get_not_found(self):
        resp = client.get("/profiles/profile_nonexistent")
        assert resp.status_code == 404


# ── Update ─────────────────────────────────────────────────────────────────────


class TestUpdateProfile:
    def test_update_display_name(self):
        created = client.post("/profiles/", json={"display_name": "Old"}).json()["data"]
        resp = client.patch(f"/profiles/{created['id']}", json={"display_name": "New"})
        assert resp.status_code == 200
        assert resp.json()["data"]["display_name"] == "New"

    def test_update_roles(self):
        created = client.post("/profiles/", json={"display_name": "Roles"}).json()[
            "data"
        ]
        resp = client.patch(f"/profiles/{created['id']}", json={"roles": ["backend"]})
        assert resp.json()["data"]["roles"] == ["backend"]

    def test_update_not_found(self):
        resp = client.patch("/profiles/profile_ghost", json={"display_name": "X"})
        assert resp.status_code == 404


# ── Status ─────────────────────────────────────────────────────────────────────


class TestUpdateStatus:
    def test_update_status(self):
        created = client.post("/profiles/", json={"display_name": "Status"}).json()[
            "data"
        ]
        resp = client.put(
            f"/profiles/{created['id']}/status",
            json={"status": "online", "runtime_info": {"cli": "codex"}},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "online"
        assert resp.json()["data"]["runtime_info"] == {"cli": "codex"}

    def test_update_status_not_found(self):
        resp = client.put("/profiles/profile_ghost/status", json={"status": "online"})
        assert resp.status_code == 404


# ── Delete ─────────────────────────────────────────────────────────────────────


class TestDeleteProfile:
    def test_delete(self):
        created = client.post("/profiles/", json={"display_name": "Delete Me"}).json()[
            "data"
        ]
        resp = client.delete(f"/profiles/{created['id']}")
        assert resp.status_code == 200
        assert resp.json()["data"]["deleted"] == created["id"]
        # Verify gone
        resp = client.get(f"/profiles/{created['id']}")
        assert resp.status_code == 404

    def test_delete_not_found(self):
        resp = client.delete("/profiles/profile_ghost")
        assert resp.status_code == 404


# ── Available ──────────────────────────────────────────────────────────────────


class TestAvailableAgents:
    def test_get_available(self):
        client.post("/profiles/", json={"display_name": "On", "status": "online"})
        client.post("/profiles/", json={"display_name": "Busy", "status": "busy"})
        client.post("/profiles/", json={"display_name": "Off", "status": "offline"})
        resp = client.get("/profiles/available")
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 2

    def test_get_by_role(self):
        client.post("/profiles/", json={"display_name": "BE", "roles": ["backend"]})
        client.post("/profiles/", json={"display_name": "FE", "roles": ["frontend"]})
        resp = client.get("/profiles/role/backend")
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 1
        assert resp.json()["data"][0]["display_name"] == "BE"
