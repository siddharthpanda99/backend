"""
Tests for Domain 27.06 — Read Replicas.

Covers: PmReadReplicaService, @node wrappers, and REST routes.
"""

import pytest
from unittest.mock import MagicMock, patch
from sqlmodel import Session
from datetime import datetime


# ── Helper ───────────────────────────────────────────────────────────────

@pytest.fixture
def mock_session():
    """Create a mock SQLModel Session with PostgreSQL dialect."""
    session = MagicMock(spec=Session)
    session.bind = MagicMock()
    session.bind.dialect = MagicMock()
    session.bind.dialect.name = "postgresql"
    return session


@pytest.fixture(autouse=True)
def patch_get_session(mock_session):
    """Patch _get_session for @node wrappers."""
    with patch("common_lib.modules.project_management.nodes._get_session", return_value=mock_session):
        yield


# ── Service Tests ────────────────────────────────────────────────────────

class TestPmReadReplicaService:
    """Test PmReadReplicaService directly."""

    def test_register_replica(self, mock_session):
        from common_lib.modules.project_management.read_replica.service import PmReadReplicaService
        svc = PmReadReplicaService(session=mock_session)
        result = svc.register_replica("replica-1", "postgresql://user:pass@replica:5432/db")
        assert result["name"] == "replica-1"
        assert result["is_active"] is True
        assert result["is_healthy"] is True
        assert "registered_at" in result

    def test_register_replica_with_custom_weight(self, mock_session):
        from common_lib.modules.project_management.read_replica.service import PmReadReplicaService
        svc = PmReadReplicaService(session=mock_session)
        result = svc.register_replica("replica-2", "postgresql://...", weight=2.0, is_active=False)
        assert result["weight"] == 2.0
        assert result["is_active"] is False

    def test_list_replicas(self, mock_session):
        from common_lib.modules.project_management.read_replica.service import PmReadReplicaService
        svc = PmReadReplicaService(session=mock_session)
        svc.register_replica("r1", "pg://r1")
        svc.register_replica("r2", "pg://r2")
        replicas = svc.list_replicas()
        assert len(replicas) == 2

    def test_get_replica(self, mock_session):
        from common_lib.modules.project_management.read_replica.service import PmReadReplicaService
        svc = PmReadReplicaService(session=mock_session)
        svc.register_replica("r1", "pg://r1")
        result = svc.get_replica("r1")
        assert result["name"] == "r1"

    def test_get_replica_not_found(self, mock_session):
        from common_lib.modules.project_management.read_replica.service import PmReadReplicaService
        svc = PmReadReplicaService(session=mock_session)
        result = svc.get_replica("nonexistent")
        assert result is None

    def test_remove_replica(self, mock_session):
        from common_lib.modules.project_management.read_replica.service import PmReadReplicaService
        svc = PmReadReplicaService(session=mock_session)
        svc.register_replica("r1", "pg://r1")
        assert svc.remove_replica("r1") is True
        assert svc.get_replica("r1") is None

    def test_remove_replica_not_found(self, mock_session):
        from common_lib.modules.project_management.read_replica.service import PmReadReplicaService
        svc = PmReadReplicaService(session=mock_session)
        assert svc.remove_replica("nonexistent") is False

    def test_update_replica(self, mock_session):
        from common_lib.modules.project_management.read_replica.service import PmReadReplicaService
        svc = PmReadReplicaService(session=mock_session)
        svc.register_replica("r1", "pg://r1", weight=1.0)
        result = svc.update_replica("r1", weight=5.0, is_active=False)
        assert result["weight"] == 5.0
        assert result["is_active"] is False

    def test_check_replica_health_success(self, mock_session):
        from common_lib.modules.project_management.read_replica.service import PmReadReplicaService
        svc = PmReadReplicaService(session=mock_session)
        svc.register_replica("r1", "pg://r1")

        mock_result = MagicMock()
        mock_result.lag_seconds = 0.5
        mock_session.exec.return_value.first.return_value = mock_result

        result = svc.check_replica_health("r1")
        assert result["healthy"] is True
        assert result["name"] == "r1"
        assert result["lag_seconds"] == 0.5

    def test_check_replica_health_not_registered(self, mock_session):
        from common_lib.modules.project_management.read_replica.service import PmReadReplicaService
        svc = PmReadReplicaService(session=mock_session)
        result = svc.check_replica_health("nonexistent")
        assert result["healthy"] is False
        assert "error" in result

    def test_check_replica_health_failure(self, mock_session):
        from common_lib.modules.project_management.read_replica.service import PmReadReplicaService
        svc = PmReadReplicaService(session=mock_session)
        svc.register_replica("r1", "pg://r1")
        mock_session.exec.side_effect = Exception("Connection refused")

        result = svc.check_replica_health("r1")
        assert result["healthy"] is False
        assert "Connection refused" in result.get("error", "")

    def test_health_summary(self, mock_session):
        from common_lib.modules.project_management.read_replica.service import PmReadReplicaService
        svc = PmReadReplicaService(session=mock_session)
        svc.register_replica("r1", "pg://r1")
        svc.register_replica("r2", "pg://r2")

        summary = svc.get_health_summary()
        assert summary["total_replicas"] == 2
        assert summary["healthy_replicas"] == 2

    def test_get_read_replica_hint(self, mock_session):
        from common_lib.modules.project_management.read_replica.service import PmReadReplicaService
        svc = PmReadReplicaService(session=mock_session)
        svc.register_replica("r1", "pg://r1", weight=1.0)
        svc.register_replica("r2", "pg://r2", weight=2.0)

        hint = svc.get_read_replica_hint()
        assert hint is not None
        assert hint["name"] in ("r1", "r2")

    def test_get_read_replica_hint_no_replicas(self, mock_session):
        from common_lib.modules.project_management.read_replica.service import PmReadReplicaService
        svc = PmReadReplicaService(session=mock_session)
        hint = svc.get_read_replica_hint()
        assert hint is None

    def test_get_stats(self, mock_session):
        from common_lib.modules.project_management.read_replica.service import PmReadReplicaService
        svc = PmReadReplicaService(session=mock_session)
        svc.register_replica("r1", "pg://r1")

        stats = svc.get_stats()
        assert stats["replica_count"] == 1
        assert stats["available_count"] == 1

    def test_replication_lag_sqlite_graceful_degradation(self):
        """Test that _check_replication_lag returns None on SQLite."""
        from common_lib.modules.project_management.read_replica.service import PmReadReplicaService
        sqlite_session = MagicMock(spec=Session)
        sqlite_session.bind = MagicMock()
        sqlite_session.bind.dialect = MagicMock()
        sqlite_session.bind.dialect.name = "sqlite"

        svc = PmReadReplicaService(session=sqlite_session)
        lag = svc._check_replication_lag()
        assert lag is None


# ── @node Wrapper Tests ──────────────────────────────────────────────────

class TestReadReplicaNodes:
    """Test read replica @node wrappers."""

    def test_register_read_replica_node(self, mock_session):
        from common_lib.modules.project_management.read_replica.nodes import register_read_replica
        with patch("common_lib.modules.project_management.read_replica.service.PmReadReplicaService.register_replica",
                   return_value={"name": "r1", "is_active": True, "is_healthy": True}):
            result = register_read_replica("r1", "pg://r1")
            assert result["name"] == "r1"
            assert result["is_active"] is True

    def test_list_read_replicas_node(self, mock_session):
        from common_lib.modules.project_management.read_replica.nodes import list_read_replicas
        with patch("common_lib.modules.project_management.read_replica.service.PmReadReplicaService.list_replicas",
                   return_value=[{"name": "r1"}]):
            result = list_read_replicas()
            assert result["count"] == 1

    def test_check_replica_health_node(self, mock_session):
        from common_lib.modules.project_management.read_replica.nodes import check_replica_health
        with patch("common_lib.modules.project_management.read_replica.service.PmReadReplicaService.check_replica_health",
                   return_value={"healthy": True, "name": "r1"}):
            result = check_replica_health(name="r1")
            assert result["healthy"] is True

    def test_get_replica_health_summary_node(self, mock_session):
        from common_lib.modules.project_management.read_replica.nodes import get_replica_health_summary
        with patch("common_lib.modules.project_management.read_replica.service.PmReadReplicaService.get_health_summary",
                   return_value={"total_replicas": 2, "healthy_replicas": 2}):
            result = get_replica_health_summary()
            assert result["total_replicas"] == 2

    def test_get_read_replica_stats_node(self, mock_session):
        from common_lib.modules.project_management.read_replica.nodes import get_read_replica_stats
        with patch("common_lib.modules.project_management.read_replica.service.PmReadReplicaService.get_stats",
                   return_value={"replica_count": 1}):
            result = get_read_replica_stats()
            assert result["replica_count"] == 1

    def test_remove_read_replica_node(self, mock_session):
        from common_lib.modules.project_management.read_replica.nodes import remove_read_replica
        with patch("common_lib.modules.project_management.read_replica.service.PmReadReplicaService.remove_replica",
                   return_value=True):
            result = remove_read_replica(name="r1")
            assert result["success"] is True
