"""Tests for RBAC Hardening Submodule (SSOT 28).

Verifies PrivilegeEscalationGuard and ThreatDetectionService for
privilege escalation prevention and threat detection.
"""


from tests.rbac.conftest import roles_table, user_roles_table, role_inheritance_table

import pytest
from datetime import datetime, timedelta, timezone

def _seed_roles(db):
    """Seed test roles."""
    now = datetime.utcnow()
    for rid, name in [(1, "viewer"), (2, "editor"), (3, "admin"), (4, "super_admin")]:
        db.execute(roles_table.insert().values(id=rid, name=name, created_at=now, updated_at=now))
    db.commit()

def _seed_user_roles(db, assignments):
    """Seed user-role assignments. assignments = [(user_id, role_id)]"""
    now = datetime.utcnow()
    for uid, rid in assignments:
        db.execute(user_roles_table.insert().values(user_id=uid, role_id=rid, is_active=True, granted_at=now))
    db.commit()

def _seed_inheritance(db, parent_id, child_id):
    now = datetime.utcnow()
    db.execute(role_inheritance_table.insert().values(parent_role_id=parent_id, child_role_id=child_id, created_at=now))
    db.commit()

class TestPrivilegeEscalationGuard:
    """Test PrivilegeEscalationGuard: self-grant, hierarchy cycles, escalation."""

    def test_self_grant_admin_blocked(self, sqlmodel_db):
        _seed_roles(sqlmodel_db)
        from common_lib.modules.rbac.hardening import PrivilegeEscalationGuard
        guard = PrivilegeEscalationGuard(sqlmodel_db)
        allowed, reason = guard.check_role_grant(10, 10, 4, "super_admin")
        assert allowed is False
        assert "Self-granting" in reason

    def test_self_grant_non_privileged_allowed(self, sqlmodel_db):
        _seed_roles(sqlmodel_db)
        from common_lib.modules.rbac.hardening import PrivilegeEscalationGuard
        guard = PrivilegeEscalationGuard(sqlmodel_db)
        allowed, reason = guard.check_role_grant(10, 10, 1, "viewer")
        assert allowed is True

    def test_admin_granting_to_other_allowed(self, sqlmodel_db):
        _seed_roles(sqlmodel_db)
        _seed_user_roles(sqlmodel_db, [(100, 3)])  # user 100 is admin
        from common_lib.modules.rbac.hardening import PrivilegeEscalationGuard
        guard = PrivilegeEscalationGuard(sqlmodel_db)
        allowed, reason = guard.check_role_grant(100, 200, 4, "super_admin")
        assert allowed is True

    def test_non_admin_granting_admin_blocked(self, sqlmodel_db):
        _seed_roles(sqlmodel_db)
        _seed_user_roles(sqlmodel_db, [(100, 1)])  # user 100 is viewer only
        from common_lib.modules.rbac.hardening import PrivilegeEscalationGuard
        guard = PrivilegeEscalationGuard(sqlmodel_db)
        allowed, reason = guard.check_role_grant(100, 200, 3, "admin")
        assert allowed is False
        assert "Only admin" in reason

    def test_role_accumulation_blocked(self, sqlmodel_db):
        _seed_roles(sqlmodel_db)
        for rid in range(1, 5):
            _seed_user_roles(sqlmodel_db, [(50, rid)])
        from common_lib.modules.rbac.hardening import PrivilegeEscalationGuard
        guard = PrivilegeEscalationGuard(sqlmodel_db)
        guard.MAX_ROLES_PER_USER = 4
        allowed, reason = guard.check_role_grant(100, 50, 1, "viewer")
        assert allowed is False
        assert "already has" in reason

    def test_cycle_detection(self, sqlmodel_db):
        _seed_roles(sqlmodel_db)
        _seed_inheritance(sqlmodel_db, 1, 2)
        _seed_inheritance(sqlmodel_db, 2, 3)
        from common_lib.modules.rbac.hardening import PrivilegeEscalationGuard
        guard = PrivilegeEscalationGuard(sqlmodel_db)
        allowed, reason = guard.check_role_hierarchy_change(3, 1)
        assert allowed is False
        assert "cycle" in reason.lower()

    def test_no_cycle_without_existing_chain(self, sqlmodel_db):
        _seed_roles(sqlmodel_db)
        from common_lib.modules.rbac.hardening import PrivilegeEscalationGuard
        guard = PrivilegeEscalationGuard(sqlmodel_db)
        allowed, reason = guard.check_role_hierarchy_change(1, 2)
        assert allowed is True

class TestThreatDetectionService:
    """Test ThreatDetectionService: bulk operation detection, anomaly detection."""

    def test_bulk_operation_allowed_under_threshold(self, sqlmodel_db):
        from common_lib.modules.rbac.hardening import ThreatDetectionService
        svc = ThreatDetectionService(sqlmodel_db)
        allowed, reason = svc.check_bulk_operation("role_grant", 5, 100)
        assert allowed is True

    def test_bulk_operation_throttled(self, sqlmodel_db):
        from common_lib.modules.rbac.hardening import ThreatDetectionService
        svc = ThreatDetectionService(sqlmodel_db)
        allowed, reason = svc.check_bulk_operation("role_grant", 100, 100)
        assert allowed is False
        assert "exceeds" in reason.lower()

    def test_role_change_recording(self, sqlmodel_db):
        from common_lib.modules.rbac.hardening import ThreatDetectionService
        svc = ThreatDetectionService(sqlmodel_db)
        svc.record_role_change(100, "grant")
        stats = svc.get_change_stats(user_id=100)
        assert stats["changes_last_hour"] == 1

    def test_change_stats_all_users(self, sqlmodel_db):
        from common_lib.modules.rbac.hardening import ThreatDetectionService
        svc = ThreatDetectionService(sqlmodel_db)
        svc.record_role_change(100, "grant")
        svc.record_role_change(200, "revoke")
        stats = svc.get_change_stats()
        assert stats["total_users_with_changes"] == 2
