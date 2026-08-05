"""
Integration tests for Universal Work Graph (Domain 00.04).

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
        from app.modules.project_management.routes.universal_graph_routes import (
            router as graph_router,
        )
        app = FastAPI()
        from app.modules.project_management.deps import get_pm_session
        app.dependency_overrides[get_pm_session] = lambda: db_session
        app.include_router(graph_router)
        with TestClient(app) as c:
            yield c


WS = "ws-int"


class TestNodes:
    def test_register_and_list(self, client):
        r = client.post("/graph/nodes", params={
            "workspace_id": WS, "entity_type": "issue", "entity_id": "iss-1",
        })
        assert r.status_code == 200
        assert r.json()["entity_id"] == "iss-1"

        r = client.get("/graph/nodes", params={"workspace_id": WS})
        assert r.status_code == 200
        assert r.json()["total"] == 1

    def test_register_duplicate_upserts(self, client):
        client.post("/graph/nodes", params={
            "workspace_id": WS, "entity_type": "issue", "entity_id": "iss-u1",
        })
        client.post("/graph/nodes", params={
            "workspace_id": WS, "entity_type": "issue", "entity_id": "iss-u1",
        })
        r = client.get("/graph/nodes", params={"workspace_id": WS})
        assert r.json()["total"] == 1

    def test_unregister_node(self, client):
        client.post("/graph/nodes", params={
            "workspace_id": WS, "entity_type": "issue", "entity_id": "iss-del",
        })
        r = client.delete(f"/graph/nodes/issue/iss-del", params={"workspace_id": WS})
        assert r.status_code == 200
        assert r.json()["success"] is True

        r = client.get("/graph/nodes", params={"workspace_id": WS})
        assert r.json()["total"] == 0

    def test_unregister_unknown_404(self, client):
        r = client.delete("/graph/nodes/issue/unknown", params={"workspace_id": WS})
        assert r.status_code == 404


class TestEdges:
    def test_link_nodes(self, client):
        for eid in ["A", "B"]:
            client.post("/graph/nodes", params={
                "workspace_id": WS, "entity_type": "issue", "entity_id": eid,
            })
        r = client.post("/graph/edges", params={
            "workspace_id": WS, "source_type": "issue", "source_id": "A",
            "target_type": "issue", "target_id": "B", "relationship": "blocks",
        })
        assert r.status_code == 200
        assert r.json()["relationship_type"] == "blocks"

    def test_get_related(self, client):
        for eid in ["R1", "R2", "R3"]:
            client.post("/graph/nodes", params={
                "workspace_id": WS, "entity_type": "issue", "entity_id": eid,
            })
        client.post("/graph/edges", params={
            "workspace_id": WS, "source_type": "issue", "source_id": "R1",
            "target_type": "issue", "target_id": "R2", "relationship": "blocks",
        })
        client.post("/graph/edges", params={
            "workspace_id": WS, "source_type": "issue", "source_id": "R2",
            "target_type": "issue", "target_id": "R3", "relationship": "blocks",
        })
        r = client.get("/graph/related", params={
            "workspace_id": WS, "entity_type": "issue", "entity_id": "R1", "max_depth": 3,
        })
        assert r.status_code == 200
        assert r.json()["total_nodes"] == 3


class TestCycleDetection:
    def test_detects_cycle(self, client):
        for eid in ["A", "B"]:
            client.post("/graph/nodes", params={
                "workspace_id": WS, "entity_type": "issue", "entity_id": eid,
            })
        client.post("/graph/edges", params={
            "workspace_id": WS, "source_type": "issue", "source_id": "A",
            "target_type": "issue", "target_id": "B", "relationship": "depends_on",
        })
        r = client.get("/graph/cycle-check", params={
            "workspace_id": WS, "source_type": "issue", "source_id": "B",
            "target_type": "issue", "target_id": "A",
        })
        assert r.status_code == 200
        assert r.json()["would_create_cycle"] is True


class TestPathfinding:
    def test_find_path(self, client):
        for eid in ["A", "B", "C"]:
            client.post("/graph/nodes", params={
                "workspace_id": WS, "entity_type": "issue", "entity_id": eid,
            })
        for src, tgt in [("A", "B"), ("B", "C")]:
            client.post("/graph/edges", params={
                "workspace_id": WS, "source_type": "issue", "source_id": src,
                "target_type": "issue", "target_id": tgt, "relationship": "depends_on",
            })
        r = client.get("/graph/path", params={
            "workspace_id": WS, "source_type": "issue", "source_id": "A",
            "target_type": "issue", "target_id": "C", "max_depth": 5,
        })
        assert r.status_code == 200
        assert r.json()["found"] is True


class TestSnapshots:
    def test_create_and_list(self, client):
        client.post("/graph/nodes", params={
            "workspace_id": WS, "entity_type": "issue", "entity_id": "root",
        })
        r = client.post("/graph/snapshots", params={
            "workspace_id": WS, "entity_type": "issue",
            "entity_id": "root", "depth": 1, "name": "My Snap",
        })
        assert r.status_code == 200
        assert r.json()["name"] == "My Snap"

        r = client.get("/graph/snapshots", params={"workspace_id": WS})
        assert r.status_code == 200
        assert r.json()["total"] >= 1


class TestStats:
    def test_stats(self, client):
        for i in range(3):
            client.post("/graph/nodes", params={
                "workspace_id": WS, "entity_type": "issue", "entity_id": f"iss-{i}",
            })
        r = client.get("/graph/stats", params={"workspace_id": WS})
        assert r.status_code == 200
        assert r.json()["total_nodes"] == 3


class TestDB:
    def test_sqlite_works(self, db_session):
        result = db_session.exec(text("SELECT 1")).first()
        assert result[0] == 1
