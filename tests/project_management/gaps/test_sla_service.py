"""Tests for SLA Management (Module 13)."""

import pytest
from datetime import datetime, timedelta
from sqlmodel import Session, create_engine, SQLModel
from common_lib.modules.project_management.sla.service import SLAService, DEFAULT_PRIORITY_TARGETS
from common_lib.modules.project_management.sla.models import SLAConfig, SLAViolation


@pytest.fixture
def session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    # Create ALL pm_* tables to satisfy FK references
    pm_tables = [
        t for name, t in SQLModel.metadata.tables.items()
        if name.startswith("pm_")
    ]
    SQLModel.metadata.create_all(engine, tables=pm_tables)
    s = Session(engine)
    yield s
    s.close()


class TestSLAConfig:
    def test_create_config(self, session):
        svc = SLAService(session)
        result = svc.create_config("P0 SLA", sla_type="time_to_resolution")
        assert result["name"] == "P0 SLA"
        assert result["sla_type"] == "time_to_resolution"
        assert "id" in result

    def test_create_config_with_custom_targets(self, session):
        svc = SLAService(session)
        targets = [{"priority": "urgent", "resolution_mins": 120}]
        result = svc.create_config("Custom SLA", priority_targets=targets)
        assert result["priority_targets"] == targets

    def test_get_config(self, session):
        svc = SLAService(session)
        created = svc.create_config("Test SLA")
        result = svc.get_config(created["id"])
        assert result is not None
        assert result["name"] == "Test SLA"

    def test_get_config_not_found(self, session):
        svc = SLAService(session)
        assert svc.get_config("nonexistent") is None

    def test_list_configs(self, session):
        svc = SLAService(session)
        svc.create_config("SLA 1")
        svc.create_config("SLA 2")
        configs = svc.list_configs()
        assert len(configs) >= 2

    def test_update_config(self, session):
        svc = SLAService(session)
        created = svc.create_config("Old Name")
        updated = svc.update_config(created["id"], {"name": "New Name"})
        assert updated["name"] == "New Name"

    def test_delete_config(self, session):
        svc = SLAService(session)
        created = svc.create_config("Delete Me")
        assert svc.delete_config(created["id"]) is True
        assert svc.get_config(created["id"]) is None


class TestSLABreach:
    def test_no_breach_within_target(self, session):
        svc = SLAService(session)
        config = svc.create_config("Test SLA")
        result = svc.check_and_record_breach(
            config_id=config["id"],
            issue_id="issue-1",
            sla_type="time_to_resolution",
            elapsed_minutes=10,
            priority="urgent",
        )
        assert result is None  # Within SLA (10 min < 240 min)

    def test_breach_exceeds_target(self, session):
        svc = SLAService(session)
        targets = [{"priority": "urgent", "resolution_mins": 5}]
        config = svc.create_config("Strict SLA", priority_targets=targets)
        result = svc.check_and_record_breach(
            config_id=config["id"],
            issue_id="issue-1",
            sla_type="time_to_resolution",
            elapsed_minutes=10,
            priority="urgent",
        )
        assert result is not None
        assert result["severity"] in ("warning", "critical")
        assert result["exceeded_by_minutes"] == 5

    def test_breach_critical_when_double(self, session):
        svc = SLAService(session)
        targets = [{"priority": "urgent", "resolution_mins": 5}]
        config = svc.create_config("Very Strict SLA", priority_targets=targets)
        result = svc.check_and_record_breach(
            config_id=config["id"],
            issue_id="issue-1",
            sla_type="time_to_resolution",
            elapsed_minutes=15,
            priority="urgent",
        )
        assert result is not None
        assert result["severity"] == "critical"  # 15 > 5*2

    def test_list_violations(self, session):
        svc = SLAService(session)
        targets = [{"priority": "medium", "resolution_mins": 1}]
        config = svc.create_config("Test", priority_targets=targets)
        svc.check_and_record_breach(config["id"], "issue-1", "time_to_resolution", 10)
        violations = svc.list_violations(issue_id="issue-1")
        assert len(violations) >= 1

    def test_resolve_violation(self, session):
        svc = SLAService(session)
        targets = [{"priority": "medium", "resolution_mins": 1}]
        config = svc.create_config("Test", priority_targets=targets)
        breach = svc.check_and_record_breach(config["id"], "issue-1",
                                               "time_to_resolution", 10)
        resolved = svc.resolve_violation(breach["id"], resolved_by="admin",
                                          notes="Acknowledged")
        assert resolved["resolved_by"] == "admin"


class TestSLACompliance:
    def test_compliance_report(self, session):
        svc = SLAService(session)
        targets = [{"priority": "medium", "resolution_mins": 1}]
        config = svc.create_config("Test", priority_targets=targets)
        svc.check_and_record_breach(config["id"], "issue-1", "time_to_resolution", 10)
        report = svc.get_compliance_report(days=30)
        assert report["total_violations"] >= 1

    def test_issue_sla_status_no_config(self, session):
        svc = SLAService(session)
        status = svc.get_issue_sla_status("issue-1")
        assert status["status"] == "no_sla"
