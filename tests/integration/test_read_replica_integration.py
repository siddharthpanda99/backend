"""
Integration tests for Read Replicas (Domain 27.06).

Tests FastAPI route handlers with a **real SQLite database**.
No service mocking — full HTTP -> route -> service -> SQLite chain.
"""

import os
import tempfile
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session, create_engine, SQLModel
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
    from common_lib.modules.project_management.read_replica.service import (
        PmReadReplicaService,
    )
    shared_replicas: dict = {}

    original_init = PmReadReplicaService.__init__

    def shared_init(self, session):
        original_init(self, session)
        self._replicas = shared_replicas

    with patch.object(PmReadReplicaService, "__init__", shared_init):
        with patch(
            "app.modules.auth.dependencies.get_current_user",
            lambda: {"id": "test-user"},
            create=True,
        ):
            from app.modules.project_management.routes.read_replica_routes import (
                router as read_replica_router,
            )
            app = FastAPI()
            from app.modules.project_management.deps import get_pm_session
            app.dependency_overrides[get_pm_session] = lambda: db_session
            app.include_router(read_replica_router)
            with TestClient(app) as c:
                yield c


class TestReadReplicaLifecycle:
    BASE = "/read-replicas"

    def test_full_lifecycle(self, client):
        # Register
        r = client.post(self.BASE, json={"name": "r1", "connection_string": "pg://r1"})
        assert r.status_code == 200
        assert r.json()["name"] == "r1"

        # List
        r = client.get(self.BASE)
        assert r.status_code == 200
        assert r.json()["count"] == 1

        # Get
        r = client.get(f"{self.BASE}/r1")
        assert r.status_code == 200
        assert r.json()["name"] == "r1"

        # Health check
        r = client.post(f"{self.BASE}/r1/health-check")
        assert r.status_code == 200
        assert "healthy" in r.json()

        # Update
        r = client.patch(f"{self.BASE}/r1", json={"weight": 5.0})
        assert r.status_code == 200
        assert r.json()["weight"] == 5.0

        # Delete
        r = client.delete(f"{self.BASE}/r1")
        assert r.status_code == 200
        assert r.json()["success"] is True

        # Verify deletion
        r = client.get(f"{self.BASE}/r1")
        assert r.status_code == 404


class TestReadReplicaHealth:
    """Health check tests — including unhealthy state detection."""

    BASE = "/read-replicas"

    def test_healthy(self, client):
        """Health check returns healthy=True when DB is working."""
        client.post(self.BASE, json={"name": "r1", "connection_string": "pg://r1"})
        r = client.post(f"{self.BASE}/r1/health-check")
        assert r.status_code == 200
        assert r.json()["healthy"] is True

    def test_unhealthy_db_error(self, client, db_session):
        """Health check returns healthy=False with error when DB is broken.

        Uses ``patch.object(db_session, "exec")`` to make ``SELECT 1`` raise
        an exception. This simulates a real database connection failure
        without mocking the service layer — ``PmReadReplicaService``'s real
        ``check_replica_health()`` method catches the exception and returns
        ``{"healthy": False, "error": "..."}``.

        Note: ``Session.close()`` does NOT break in-memory SQLite because
        the engine auto-creates new connections. We use ``patch.object``
        on ``session.exec`` instead to inject a controlled failure.
        """
        client.post(self.BASE, json={"name": "r1", "connection_string": "pg://r1"})

        # Simulate a DB connection failure by making session.exec() raise.
        # This is injected at the session layer (not the service layer),
        # so the real error handling code path in check_replica_health runs.
        from unittest.mock import patch
        with patch.object(db_session, "exec", side_effect=Exception("Simulated DB failure")):
            r = client.post(f"{self.BASE}/r1/health-check")
            assert r.status_code == 200, (
                f"Expected 200, got {r.status_code}: {r.text}"
            )
            data = r.json()
            assert data["healthy"] is False, f"Expected unhealthy, got: {data}"
            assert "error" in data, f"Expected error message, got: {data}"
            assert "Simulated DB failure" in data["error"], (
                f"Expected simulated error message, got: {data['error']}"
            )

    def test_unhealthy_replica_not_registered(self, client):
        """Health check for an unregistered name returns healthy=False."""
        r = client.post(f"{self.BASE}/unknown/health-check")
        assert r.status_code == 200
        assert r.json()["healthy"] is False
        assert "not registered" in r.json().get("error", "").lower()


class TestReadReplicaValidation:
    BASE = "/read-replicas"

    def test_rejects_empty_payload(self, client):
        assert client.post(self.BASE, json={}).status_code == 422

    def test_get_unknown_404(self, client):
        assert client.get(f"{self.BASE}/unknown").status_code == 404

    def test_update_unknown_404(self, client):
        assert client.patch(f"{self.BASE}/unknown", json={"weight": 1.0}).status_code == 404

    def test_delete_unknown_404(self, client):
        assert client.delete(f"{self.BASE}/unknown").status_code == 404
