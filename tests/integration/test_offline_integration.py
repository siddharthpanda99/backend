"""
Integration tests for Offline Sync (Domain 26).

Tests FastAPI route handlers with a real SQLite database.
No service mocking — full HTTP -> route -> service -> DB chain.
"""

import os
import tempfile
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session, create_engine, SQLModel, text
from unittest.mock import patch


@pytest.fixture
def db_engine():
    """Create engine with a temporary file-based SQLite database.

    Uses a tempfile instead of ``:memory:`` because in-memory SQLite creates a
    **new database per connection** from the pool. When ``TestClient`` processes
    a request, SQLAlchemy may open a new connection under the hood that cannot
    see tables created on the original connection, causing ``no such table``
    errors.

    A file-based database avoids this because all connections see the same
    single-file database regardless of which connection in the pool they use.
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_path = tmp.name
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    from common_lib.modules.project_management.init_db import get_pm_metadata
    metadata = get_pm_metadata()
    pm_tables = [
        table for name, table in metadata.tables.items()
        if name.startswith("pm_")
    ]
    SQLModel.metadata.create_all(engine, tables=pm_tables)
    yield engine
    # Dispose the engine before unlinking to release all connections
    engine.dispose()
    try:
        os.unlink(db_path)
    except PermissionError:
        pass


@pytest.fixture
def db_session(db_engine):
    with Session(db_engine) as session:
        yield session


@pytest.fixture
def client(db_session):
    with patch(
        "app.modules.auth.dependencies.get_current_user",
        lambda: {"id": "test-user"},
        create=True,
    ):
        from app.modules.project_management.routes.offline_routes import (
            router as offline_router,
        )
        app = FastAPI()
        from app.modules.project_management.deps import get_pm_session
        app.dependency_overrides[get_pm_session] = lambda: db_session
        app.include_router(offline_router)
        with TestClient(app) as c:
            yield c


class TestMutations:
    def test_enqueue_and_list(self, client):
        r = client.post("/offline/mutations", params={
            "workspace_id": "ws-1", "entity_type": "issue",
            "entity_id": "iss-1", "mutation_type": "update",
        })
        assert r.status_code == 200
        mut_id = r.json()["id"]

        r = client.get("/offline/mutations", params={"workspace_id": "ws-1"})
        assert r.status_code == 200
        assert r.json()["count"] == 1
        assert r.json()["mutations"][0]["id"] == mut_id

    def test_ack_mutation(self, client):
        r = client.post("/offline/mutations", params={
            "workspace_id": "ws-1", "entity_type": "issue",
            "entity_id": "iss-1", "mutation_type": "update",
        })
        mut_id = r.json()["id"]

        r = client.post(f"/offline/mutations/{mut_id}/ack")
        assert r.status_code == 200
        assert r.json()["status"] == "synced"

    def test_unknown_ack_404(self, client):
        assert client.post("/offline/mutations/unknown/ack").status_code == 404

    def test_sync_status(self, client):
        for i in range(3):
            client.post("/offline/mutations", params={
                "workspace_id": "ws-st", "entity_type": "issue",
                "entity_id": f"iss-{i}", "mutation_type": "update",
            })
        r = client.get("/offline/sync-status", params={"workspace_id": "ws-st"})
        assert r.status_code == 200
        assert r.json()["total_mutations"] == 3


class TestCache:
    def test_set_and_get(self, client):
        client.post("/offline/cache", params={
            "workspace_id": "ws-1", "cache_key": "k1",
            "entity_type": "issue", "entity_id": "iss-1",
        }, json={"data": {"title": "Test"}})
        r = client.get("/offline/cache/k1", params={"workspace_id": "ws-1"})
        assert r.status_code == 200
        assert r.json()["cache_key"] == "k1"

    def test_get_miss_404(self, client):
        r = client.get("/offline/cache/nonexistent", params={"workspace_id": "ws-1"})
        assert r.status_code == 404

    def test_invalidate(self, client):
        client.post("/offline/cache", params={
            "workspace_id": "ws-inv", "cache_key": "k1",
            "entity_type": "issue", "entity_id": "i1",
        }, json={"data": {"a": 1}})
        r = client.delete("/offline/cache", params={"workspace_id": "ws-inv"})
        assert r.status_code == 200
        assert r.json()["deleted_count"] == 1


class TestConflicts:
    def test_resolve(self, client):
        r = client.post("/offline/conflicts", params={
            "workspace_id": "ws-1", "entity_type": "issue",
            "entity_id": "iss-1", "local_version": 1, "server_version": 2,
        })
        assert r.status_code == 200
        assert "id" in r.json()

    def test_list(self, client):
        client.post("/offline/conflicts", params={
            "workspace_id": "ws-list", "entity_type": "issue",
            "entity_id": "iss-1", "local_version": 1, "server_version": 2,
        })
        r = client.get("/offline/conflicts", params={"workspace_id": "ws-list"})
        assert r.status_code == 200
        assert r.json()["count"] >= 1


class TestDB:
    def test_sqlite_works(self, db_session):
        result = db_session.exec(text("SELECT 1")).first()
        assert result[0] == 1
