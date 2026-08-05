"""
Tests for Secrets Manager Audit submodule (SSOT 14).

Tests audit logging, querying, filtering, and export.
"""
from __future__ import annotations

import pytest
from common_lib.modules.secrets_manager.audit.service import AuditService
from common_lib.modules.secrets_manager.audit.models import AuditEventType


class TestAuditService:
    """Test audit trail operations."""

    def test_log_entry(self, db):
        svc = AuditService(session=db)
        entry_id = svc.log(
            event_type=AuditEventType.SECRET_CREATED.value,
            action="create",
            resource_type="secret",
            resource_id="secret-123",
            resource_name="my-secret",
            actor_id="user-1",
            actor_type="user",
            tenant_id="tenant-1",
            success=True,
        )
        assert entry_id is not None
        assert len(entry_id) > 0

    def test_log_access_granted(self, db):
        svc = AuditService(session=db)
        entry_id = svc.log_access(
            action="read_value",
            resource_type="secret",
            resource_name="api-key",
            actor_id="user-1",
            success=True,
        )
        assert entry_id is not None

    def test_log_access_denied(self, db):
        svc = AuditService(session=db)
        entry_id = svc.log_access(
            action="delete",
            resource_type="secret",
            resource_name="protected-key",
            actor_id="user-2",
            success=False,
        )
        assert entry_id is not None

    def test_query_all(self, db):
        svc = AuditService(session=db)
        svc.log(event_type="test.event", action="test", resource_type="secret",
                resource_id="r1", actor_id="u1")
        svc.log(event_type="test.event", action="test", resource_type="secret",
                resource_id="r2", actor_id="u2")

        result = svc.query()
        assert result["total"] == 2
        assert len(result["items"]) == 2

    def test_query_filter_by_resource_type(self, db):
        svc = AuditService(session=db)
        svc.log(event_type="e1", action="a", resource_type="secret", resource_id="r1", actor_id="u1")
        svc.log(event_type="e2", action="b", resource_type="policy", resource_id="r2", actor_id="u1")

        result = svc.query(resource_type="secret")
        assert result["total"] == 1
        assert result["items"][0]["resource_type"] == "secret"

    def test_query_filter_by_actor(self, db):
        svc = AuditService(session=db)
        svc.log(event_type="e1", action="a", resource_type="secret", resource_id="r1", actor_id="alice")
        svc.log(event_type="e2", action="b", resource_type="secret", resource_id="r2", actor_id="bob")

        result = svc.query(actor_id="alice")
        assert result["total"] == 1
        assert result["items"][0]["actor_id"] == "alice"

    def test_query_filter_by_event_type(self, db):
        svc = AuditService(session=db)
        svc.log(event_type="secret.created", action="create", resource_type="secret",
                resource_id="r1", actor_id="u1")
        svc.log(event_type="secret.read", action="read", resource_type="secret",
                resource_id="r1", actor_id="u2")

        result = svc.query(event_type="secret.created")
        assert result["total"] == 1
        assert result["items"][0]["event_type"] == "secret.created"

    def test_query_filter_by_success(self, db):
        svc = AuditService(session=db)
        svc.log(event_type="e1", action="a", resource_type="secret", resource_id="r1",
                actor_id="u1", success=True)
        svc.log(event_type="e2", action="b", resource_type="secret", resource_id="r2",
                actor_id="u1", success=False)

        result = svc.query(success=False)
        assert result["total"] == 1
        assert result["items"][0]["success"] is False

    def test_query_pagination(self, db):
        svc = AuditService(session=db)
        for i in range(5):
            svc.log(event_type=f"e{i}", action="a", resource_type="secret",
                    resource_id=f"r{i}", actor_id="u1")

        result = svc.query(limit=2)
        assert len(result["items"]) == 2
        assert result["total"] == 5

    def test_get_by_resource(self, db):
        svc = AuditService(session=db)
        svc.log(event_type="e1", action="a", resource_type="secret",
                resource_id="target-resource", actor_id="u1")
        svc.log(event_type="e2", action="b", resource_type="secret",
                resource_id="other-resource", actor_id="u1")

        entries = svc.get_by_resource(resource_id="target-resource")
        assert len(entries) == 1
        assert entries[0]["resource_id"] == "target-resource"

    def test_get_by_actor(self, db):
        svc = AuditService(session=db)
        svc.log(event_type="e1", action="a", resource_type="secret",
                resource_id="r1", actor_id="actor-1")
        svc.log(event_type="e2", action="b", resource_type="secret",
                resource_id="r2", actor_id="actor-1")
        svc.log(event_type="e3", action="c", resource_type="secret",
                resource_id="r3", actor_id="actor-2")

        entries = svc.get_by_actor(actor_id="actor-1")
        assert len(entries) == 2

    def test_get_stats(self, db):
        svc = AuditService(session=db)
        svc.log(event_type="e1", action="a", resource_type="secret", resource_id="r1",
                actor_id="u1", success=True)
        svc.log(event_type="e2", action="b", resource_type="secret", resource_id="r2",
                actor_id="u1", success=False)

        stats = svc.get_stats()
        assert stats["total_entries"] == 2
        assert stats["failed_operations"] == 1

    def test_export(self, db):
        svc = AuditService(session=db)
        svc.log(event_type="e1", action="a", resource_type="secret", resource_id="r1",
                actor_id="u1", success=True)

        from datetime import datetime, timedelta
        start = (datetime.utcnow() - timedelta(hours=1)).isoformat()
        end = (datetime.utcnow() + timedelta(hours=1)).isoformat()

        export = svc.export(start_time=start, end_time=end)
        assert export["count"] == 1
        assert len(export["entries"]) == 1
        assert "export_time" in export

    def test_no_plaintext_in_audit(self, db):
        """SSOT invariant: no plaintext secrets in audit logs."""
        svc = AuditService(session=db)
        entry_id = svc.log(
            event_type="secret.read",
            action="read_value",
            resource_type="secret",
            resource_id="secret-123",
            resource_name="my-api-key",
            actor_id="user-1",
            metadata={"key_id": "enc-key-1"},  # Only references, no values
        )
        result = svc.query(event_type="secret.read")
        assert len(result["items"]) == 1
        entry = result["items"][0]
        # Verify no value/blob in the audit entry
        assert "value" not in entry
        assert "plaintext" not in entry
        assert "data" not in entry
