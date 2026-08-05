"""Tests for RBAC Delegation & Impersonation Submodule (SSOT 13).

Verifies DelegationService and ImpersonationService with time-based
delegation, revocation, impersonation lifecycle, and audit logging.
"""


import pytest
from datetime import datetime, timedelta, timezone

def _future(days=7):
    return datetime.now(timezone.utc) + timedelta(days=days)

class TestDelegationService:
    """Test DelegationService: create, revoke, expire, query."""

    def test_create_delegation(self, sqlmodel_db):
        from common_lib.modules.rbac.delegation import DelegationService
        svc = DelegationService(sqlmodel_db)
        record = svc.create_delegation(
            delegator_user_id=1, delegatee_user_id=2,
            expires_at=_future(7), reason="vacation cover",
        )
        assert record.delegation_id is not None
        assert record.is_active is True
        assert record.scope_type == "all"

    def test_cannot_self_delegate(self, sqlmodel_db):
        from common_lib.modules.rbac.delegation import DelegationService
        svc = DelegationService(sqlmodel_db)
        with pytest.raises(ValueError, match="yourself"):
            svc.create_delegation(1, 1, expires_at=_future(7))

    def test_revoke_delegation(self, sqlmodel_db):
        from common_lib.modules.rbac.delegation import DelegationService
        svc = DelegationService(sqlmodel_db)
        record = svc.create_delegation(1, 2, expires_at=_future(7))
        success = svc.revoke_delegation(record.delegation_id, reason="no longer needed")
        assert success is True
        # Should no longer be active
        active = svc.get_active_delegations_for_user(2)
        assert len(active) == 0

    def test_get_active_delegations(self, sqlmodel_db):
        from common_lib.modules.rbac.delegation import DelegationService
        svc = DelegationService(sqlmodel_db)
        svc.create_delegation(1, 2, expires_at=_future(7))
        svc.create_delegation(3, 2, expires_at=_future(14))
        active = svc.get_active_delegations_for_user(2)
        assert len(active) == 2

    def test_get_delegations_from_user(self, sqlmodel_db):
        from common_lib.modules.rbac.delegation import DelegationService
        svc = DelegationService(sqlmodel_db)
        svc.create_delegation(1, 2, expires_at=_future(7))
        svc.create_delegation(1, 3, expires_at=_future(14))
        from_user = svc.get_delegations_from_user(1)
        assert len(from_user) == 2

    def test_is_delegated(self, sqlmodel_db):
        from common_lib.modules.rbac.delegation import DelegationService
        svc = DelegationService(sqlmodel_db)
        svc.create_delegation(1, 2, expires_at=_future(7))
        assert svc.is_delegated(1, 2) is True
        assert svc.is_delegated(2, 1) is False

    def test_get_delegation_summary(self, sqlmodel_db):
        from common_lib.modules.rbac.delegation import DelegationService
        svc = DelegationService(sqlmodel_db)
        svc.create_delegation(1, 2, expires_at=_future(7))
        svc.create_delegation(3, 1, expires_at=_future(14))
        summary = svc.get_delegation_summary(1)
        assert summary["active_as_delegator"] == 1
        assert summary["active_as_delegatee"] == 1

class TestImpersonationService:
    """Test ImpersonationService: start, end, query, audit."""

    def test_start_impersonation(self, sqlmodel_db):
        from common_lib.modules.rbac.delegation import ImpersonationService
        svc = ImpersonationService(sqlmodel_db)
        log = svc.start_impersonation(admin_user_id=10, target_user_id=20, reason="debug issue #123")
        assert log.session_id is not None
        assert log.is_active is True
        assert log.admin_user_id == 10
        assert log.target_user_id == 20

    def test_cannot_self_impersonate(self, sqlmodel_db):
        from common_lib.modules.rbac.delegation import ImpersonationService
        svc = ImpersonationService(sqlmodel_db)
        with pytest.raises(ValueError, match="yourself"):
            svc.start_impersonation(10, 10, reason="test")

    def test_requires_reason(self, sqlmodel_db):
        from common_lib.modules.rbac.delegation import ImpersonationService
        svc = ImpersonationService(sqlmodel_db)
        with pytest.raises(ValueError, match="mandatory"):
            svc.start_impersonation(10, 20, reason="")
        with pytest.raises(ValueError, match="mandatory"):
            svc.start_impersonation(10, 20, reason="   ")

    def test_end_impersonation(self, sqlmodel_db):
        from common_lib.modules.rbac.delegation import ImpersonationService
        svc = ImpersonationService(sqlmodel_db)
        log = svc.start_impersonation(10, 20, reason="debug")
        success = svc.end_impersonation(log.session_id)
        assert success is True
        assert svc.get_active_impersonation(10) is None

    def test_new_impersonation_ends_previous(self, sqlmodel_db):
        from common_lib.modules.rbac.delegation import ImpersonationService
        svc = ImpersonationService(sqlmodel_db)
        log1 = svc.start_impersonation(10, 20, reason="first")
        log2 = svc.start_impersonation(10, 30, reason="second")
        # First should be ended
        active = svc.get_active_impersonation(10)
        assert active.session_id == log2.session_id

    def test_list_impersonation_logs(self, sqlmodel_db):
        from common_lib.modules.rbac.delegation import ImpersonationService
        svc = ImpersonationService(sqlmodel_db)
        svc.start_impersonation(10, 20, reason="debug1")
        svc.start_impersonation(10, 30, reason="debug2")
        logs = svc.list_impersonation_logs(admin_user_id=10)
        assert len(logs) == 2
        target_logs = svc.list_impersonation_logs(target_user_id=20)
        assert len(target_logs) == 1

    def test_get_delegation_summary(self, sqlmodel_db):
        from common_lib.modules.rbac.delegation import DelegationService
        svc = DelegationService(sqlmodel_db)
        svc.create_delegation(1, 2, expires_at=_future(7))
        summary = svc.get_delegation_summary(1)
        assert summary["user_id"] == 1
        assert summary["active_as_delegator"] == 1
