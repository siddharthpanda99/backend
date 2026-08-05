"""
FastAPI route tests for Domain 27.06 — Read Replicas.

Tests all 7 REST endpoints using TestClient with a local FastAPI app.
Uses clean patch() calls for both auth and PM dependencies.
Routes/__init__.py imports offline_routes which imports get_current_user
from auth.dependencies, so we patch that before importing the router.
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session


@pytest.fixture
def mock_session():
    """Create a mock session with PostgreSQL dialect."""
    session = MagicMock(spec=Session)
    session.bind = MagicMock()
    session.bind.dialect = MagicMock()
    session.bind.dialect.name = "postgresql"
    return session


@pytest.fixture
def client(mock_session):
    """Create a FastAPI TestClient with patched dependencies.

    Patches:
    1. get_pm_session — PM database session
    2. get_current_identity — Auth identity resolution
    3. get_authz_checker — Authorization checker
    """
    app = FastAPI()

    # Mock identity for auth chain
    mock_identity = MagicMock()
    mock_identity.id = "test-user"
    mock_identity.user_id = "test-user"
    mock_identity.is_super_admin = False

    mock_authz = MagicMock()
    mock_authz.check_permission.return_value = True

    # Override dependencies at the FastAPI DI level
    from app.modules.project_management.deps import get_pm_session
    from app.modules.auth.dependencies import get_current_identity, get_authz_checker

    app.dependency_overrides[get_pm_session] = lambda: mock_session
    app.dependency_overrides[get_current_identity] = lambda: mock_identity
    app.dependency_overrides[get_authz_checker] = lambda: mock_authz

    # Import router AFTER dependencies are set up
    from app.modules.project_management.routes.read_replica_routes import router as read_replica_router
    app.include_router(read_replica_router)

    with TestClient(app) as c:
        yield c


class TestReadReplicaRoutes:
    """Test read replica REST endpoints.

    Route structure:
    - Router prefix: /read-replicas
    - POST /read-replicas - Register replica
    - GET /read-replicas - List replicas
    - GET /read-replicas/health - Health summary
    - GET /read-replicas/stats - Stats
    - GET /read-replicas/{name} - Get replica
    - POST /read-replicas/{name}/health-check - Health check
    - PATCH /read-replicas/{name} - Update replica
    - DELETE /read-replicas/{name} - Remove replica
    """

    BASE = "/read-replicas"

    def test_register_replica(self, client):
        """POST /read-replicas should register a new replica."""
        from common_lib.modules.project_management.read_replica.service import PmReadReplicaService
        with patch.object(PmReadReplicaService, "register_replica", return_value={
            "name": "replica-1", "is_active": True, "registered_at": "2026-01-01T00:00:00",
        }):
            response = client.post(self.BASE, json={
                "name": "replica-1",
                "connection_string": "postgresql://user:pass@replica:5432/db",
            })
            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
            assert response.json()["name"] == "replica-1"

    def test_list_replicas(self, client):
        """GET /read-replicas should list all replicas."""
        from common_lib.modules.project_management.read_replica.service import PmReadReplicaService
        with patch.object(PmReadReplicaService, "list_replicas", return_value=[
            {"name": "r1"}, {"name": "r2"},
        ]):
            response = client.get(self.BASE)
            assert response.status_code == 200
            assert response.json()["count"] == 2

    def test_list_replicas_empty(self, client):
        """GET /read-replicas should return empty list."""
        from common_lib.modules.project_management.read_replica.service import PmReadReplicaService
        with patch.object(PmReadReplicaService, "list_replicas", return_value=[]):
            response = client.get(self.BASE)
            assert response.status_code == 200
            assert response.json()["count"] == 0

    def test_health_summary(self, client):
        """GET /read-replicas/health should return aggregate health."""
        from common_lib.modules.project_management.read_replica.service import PmReadReplicaService
        with patch.object(PmReadReplicaService, "get_health_summary", return_value={
            "total_replicas": 2, "healthy_replicas": 2,
        }):
            response = client.get(f"{self.BASE}/health")
            assert response.status_code == 200
            assert response.json()["total_replicas"] == 2

    def test_stats(self, client):
        """GET /read-replicas/stats should return comprehensive stats."""
        from common_lib.modules.project_management.read_replica.service import PmReadReplicaService
        with patch.object(PmReadReplicaService, "get_stats", return_value={
            "replica_count": 1, "available_count": 1,
        }):
            response = client.get(f"{self.BASE}/stats")
            assert response.status_code == 200
            assert response.json()["replica_count"] == 1

    def test_get_replica_found(self, client):
        """GET /read-replicas/{name} should return replica details."""
        from common_lib.modules.project_management.read_replica.service import PmReadReplicaService
        with patch.object(PmReadReplicaService, "get_replica", return_value={
            "name": "r1", "is_active": True,
        }):
            response = client.get(f"{self.BASE}/r1")
            assert response.status_code == 200
            assert response.json()["name"] == "r1"

    def test_get_replica_not_found(self, client):
        """GET /read-replicas/{name} should 404 for unknown replicas."""
        from common_lib.modules.project_management.read_replica.service import PmReadReplicaService
        with patch.object(PmReadReplicaService, "get_replica", return_value=None):
            response = client.get(f"{self.BASE}/nonexistent")
            assert response.status_code == 404

    def test_check_health(self, client):
        """POST /read-replicas/{name}/health-check should run health check."""
        from common_lib.modules.project_management.read_replica.service import PmReadReplicaService
        with patch.object(PmReadReplicaService, "check_replica_health", return_value={
            "name": "r1", "healthy": True, "latency_ms": 5.2,
        }):
            response = client.post(f"{self.BASE}/r1/health-check")
            assert response.status_code == 200
            assert response.json()["healthy"] is True

    def test_check_health_unhealthy(self, client):
        """POST /read-replicas/{name}/health-check should report unhealthy."""
        from common_lib.modules.project_management.read_replica.service import PmReadReplicaService
        with patch.object(PmReadReplicaService, "check_replica_health", return_value={
            "name": "r1", "healthy": False, "error": "Connection refused",
        }):
            response = client.post(f"{self.BASE}/r1/health-check")
            assert response.status_code == 200
            assert response.json()["healthy"] is False

    def test_update_replica(self, client):
        """PATCH /read-replicas/{name} should update config."""
        from common_lib.modules.project_management.read_replica.service import PmReadReplicaService
        with patch.object(PmReadReplicaService, "update_replica", return_value={
            "name": "r1", "weight": 5.0, "is_active": False,
        }):
            response = client.patch(f"{self.BASE}/r1", json={"weight": 5.0, "is_active": False})
            assert response.status_code == 200
            assert response.json()["weight"] == 5.0

    def test_update_replica_not_found(self, client):
        """PATCH /read-replicas/{name} should 404 for unknown."""
        from common_lib.modules.project_management.read_replica.service import PmReadReplicaService
        with patch.object(PmReadReplicaService, "update_replica", return_value=None):
            response = client.patch(f"{self.BASE}/nonexistent", json={"weight": 3.0})
            assert response.status_code == 404

    def test_delete_replica(self, client):
        """DELETE /read-replicas/{name} should remove replica."""
        from common_lib.modules.project_management.read_replica.service import PmReadReplicaService
        with patch.object(PmReadReplicaService, "remove_replica", return_value=True):
            response = client.delete(f"{self.BASE}/r1")
            assert response.status_code == 200
            assert response.json()["success"] is True

    def test_delete_replica_not_found(self, client):
        """DELETE /read-replicas/{name} should 404 for unknown."""
        from common_lib.modules.project_management.read_replica.service import PmReadReplicaService
        with patch.object(PmReadReplicaService, "remove_replica", return_value=False):
            response = client.delete(f"{self.BASE}/nonexistent")
            assert response.status_code == 404
