"""Tests for Scanning service (SSOT §13)."""

import pytest
from sqlmodel import Session, create_engine, SQLModel
from common_lib.modules.secrets_manager.scanning.service import ScanningService


@pytest.fixture
def session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    sm_tables = [t for n, t in SQLModel.metadata.tables.items() if n.startswith("sm_")]
    SQLModel.metadata.create_all(engine, tables=sm_tables)
    s = Session(engine)
    yield s
    s.close()


class TestScanTargets:
    def test_register_target(self, session):
        svc = ScanningService(session)
        result = svc.register_target(
            target_type="git_repo",
            uri="https://github.com/org/repo.git",
            name="Test Repo",
        )
        assert result["target_type"] == "git_repo"
        assert result["name"] == "Test Repo"

    def test_list_targets(self, session):
        svc = ScanningService(session)
        svc.register_target("git_repo", "uri1")
        svc.register_target("container", "uri2")
        targets = svc.list_targets()
        assert len(targets) >= 2

    def test_delete_target(self, session):
        svc = ScanningService(session)
        t = svc.register_target("git_repo", "uri3")
        assert svc.delete_target(t["id"]) is True


class TestScanning:
    def test_scan_detects_aws_key(self, session):
        svc = ScanningService(session)
        t = svc.register_target("text", "inline")
        findings = svc.scan_text(
            target_id=t["id"], text="My AWS key is AKIAIOSFODNN7EXAMPLE3"
        )
        aws_findings = [f for f in findings if "AWS" in f.get("provider", "")]
        assert len(aws_findings) >= 1

    def test_scan_detects_private_key(self, session):
        svc = ScanningService(session)
        t = svc.register_target("text", "inline")
        findings = svc.scan_text(
            target_id=t["id"], text="-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKC"
        )
        pk_findings = [
            f for f in findings if "Private Key" in f.get("matched_pattern", "")
        ]
        assert len(pk_findings) >= 1

    def test_scan_clean_text(self, session):
        svc = ScanningService(session)
        t = svc.register_target("text", "inline")
        findings = svc.scan_text(
            target_id=t["id"], text="This is a clean text with no secrets"
        )
        assert len(findings) == 0

    def test_list_findings(self, session):
        svc = ScanningService(session)
        t = svc.register_target("text", "inline")
        svc.scan_text(target_id=t["id"], text="AKIAIOSFODNN7EXAMPLE3")
        findings = svc.list_findings()
        assert len(findings) >= 1


class TestRemediation:
    def test_remediate_finding(self, session):
        svc = ScanningService(session)
        t = svc.register_target("text", "inline")
        findings = svc.scan_text(
            target_id=t["id"], text="ghp_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        )
        f_id = findings[0]["id"]
        result = svc.remediate_finding(finding_id=f_id, action_type="rotate")
        assert result["status"] == "remediated"

    def test_update_finding_status(self, session):
        svc = ScanningService(session)
        t = svc.register_target("text", "inline")
        findings = svc.scan_text(target_id=t["id"], text="AKIAIOSFODNN7EXAMPLE3")
        f_id = findings[0]["id"]
        result = svc.update_finding_status(finding_id=f_id, status="false_positive")
        assert result["status"] == "false_positive"
