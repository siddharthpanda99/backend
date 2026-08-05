"""Tests for Monitoring service (SSOT §25)."""

import pytest
from sqlmodel import Session, create_engine, SQLModel
from common_lib.modules.secrets_manager.monitoring.service import MonitoringService


@pytest.fixture
def session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    sm_tables = [t for n, t in SQLModel.metadata.tables.items() if n.startswith("sm_")]
    SQLModel.metadata.create_all(engine, tables=sm_tables)
    s = Session(engine)
    yield s
    s.close()


class TestMonitoring:
    def test_get_cluster_health(self, session):
        svc = MonitoringService(session)
        health = svc.get_cluster_health()
        assert health["status"] == "healthy"
        assert "total_secrets" in health

    def test_get_seal_status(self, session):
        svc = MonitoringService(session)
        status = svc.get_seal_status()
        assert "sealed" in status
        assert "progress" in status

    def test_get_recent_errors_empty(self, session):
        svc = MonitoringService(session)
        errors = svc.get_recent_errors(hours=24)
        assert isinstance(errors, list)

    def test_get_perf_metrics(self, session):
        svc = MonitoringService(session)
        metrics = svc.get_perf_metrics()
        assert "vault_ops" in metrics
        assert "crypto_ops" in metrics

    def test_get_slo_compliance(self, session):
        svc = MonitoringService(session)
        slo = svc.get_slo_compliance()
        assert slo["api_availability"] >= 99.0

    def test_get_dashboard(self, session):
        svc = MonitoringService(session)
        dashboard = svc.get_dashboard()
        assert "health" in dashboard
        assert "seal_status" in dashboard
        assert "slo_compliance" in dashboard
