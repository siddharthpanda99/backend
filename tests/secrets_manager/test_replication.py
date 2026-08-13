"""Tests for Replication service (SSOT §15)."""

import pytest
from sqlmodel import Session, create_engine, SQLModel
from common_lib.modules.secrets_manager.replication.service import ReplicationService


@pytest.fixture
def session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    sm_tables = [t for n, t in SQLModel.metadata.tables.items() if n.startswith("sm_")]
    SQLModel.metadata.create_all(engine, tables=sm_tables)
    s = Session(engine)
    yield s
    s.close()


class TestReplication:
    def test_register_cluster(self, session):
        svc = ReplicationService(session)
        result = svc.register_cluster(
            "us-east-1",
            "https://vault-east.example.com",
            cluster_type="performance",
            is_primary=True,
        )
        assert result["cluster_name"] == "us-east-1"
        assert result["is_primary"] is True

    def test_list_clusters(self, session):
        svc = ReplicationService(session)
        svc.register_cluster("us-east-1", "https://vault-east.example.com")
        svc.register_cluster("us-west-2", "https://vault-west.example.com")
        clusters = svc.list_clusters()
        assert len(clusters) >= 2

    def test_record_lag(self, session):
        svc = ReplicationService(session)
        c = svc.register_cluster("us-east-1", "https://vault-east.example.com")
        lag = svc.record_lag(config_id=c["id"], lag_seconds=5, status="healthy")
        assert lag["lag_seconds"] == 5

    def test_get_cluster_health_no_data(self, session):
        svc = ReplicationService(session)
        c = svc.register_cluster("test", "https://test.example.com")
        health = svc.get_cluster_health(config_id=c["id"])
        assert health["status"] == "unknown"

    def test_heartbeat(self, session):
        svc = ReplicationService(session)
        c = svc.register_cluster("test", "https://test.example.com")
        assert svc.heartbeat(config_id=c["id"]) is True

    def test_heartbeat_not_found(self, session):
        svc = ReplicationService(session)
        assert svc.heartbeat(config_id="nonexistent") is False

    def test_promote_to_primary(self, session):
        svc = ReplicationService(session)
        svc.register_cluster("primary", "https://vault-a.example.com", is_primary=True)
        secondary = svc.register_cluster("secondary", "https://vault-b.example.com")
        promoted = svc.promote_to_primary(config_id=secondary["id"])
        assert promoted["is_primary"] is True
