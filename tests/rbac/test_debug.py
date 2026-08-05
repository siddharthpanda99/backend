"""Tests for RBAC Debug/Diff Tools submodule.

Verifies PermissionDebugger and RoleDiffer for permission tracing,
role comparison, and user comparison.
"""


from tests.rbac.conftest import roles_table, permissions_table, role_permissions_table, role_inheritance_table

import pytest
from datetime import datetime


_now = datetime.utcnow

def _seed_roles(db):
    now = _now()
    for rid, name in [(1, "viewer"), (2, "editor"), (3, "admin")]:
        db.execute(roles_table.insert().values(id=rid, name=name, created_at=now, updated_at=now))
    db.commit()

def _seed_permissions(db):
    now = _now()
    for pid, name, resource, action in [
        (1, "project:read", "project", "read"),
        (2, "project:write", "project", "write"),
        (3, "admin:access", "admin", "access"),
    ]:
        db.execute(permissions_table.insert().values(
            id=pid, name=name, resource=resource, action=action,
            created_at=now, updated_at=now,
        ))
    db.commit()

def _seed_role_perms(db, role_perm_pairs):
    for rid, pid in role_perm_pairs:
        db.execute(role_permissions_table.insert().values(role_id=rid, permission_id=pid))
    db.commit()

class TestPermissionDebugger:
    """Test PermissionDebugger: trace, debug cache."""

    def test_trace_nonexistent_permission(self, sqlmodel_db):
        from common_lib.modules.rbac.debug.service import PermissionDebugger
        debugger = PermissionDebugger(sqlmodel_db)
        trace = debugger.trace_permission(1, "nonexistent:perm")
        assert trace.decision == "deny"
        assert "not found" in trace.reason.lower()

    def test_trace_no_active_roles(self, sqlmodel_db):
        _seed_permissions(sqlmodel_db)
        from common_lib.modules.rbac.debug.service import PermissionDebugger
        debugger = PermissionDebugger(sqlmodel_db)
        trace = debugger.trace_permission(1, "project:read")
        assert trace.decision == "deny"
        assert "no active role" in trace.reason.lower()

    def test_trace_with_roles(self, sqlmodel_db):
        _seed_roles(sqlmodel_db)
        _seed_permissions(sqlmodel_db)
        _seed_role_perms(sqlmodel_db, [(1, 1)])
        from common_lib.modules.rbac.debug.service import PermissionDebugger
        debugger = PermissionDebugger(sqlmodel_db)
        trace = debugger.trace_permission(1, "project:read")
        assert isinstance(trace.steps, list)
        assert len(trace.steps) > 0

class TestRoleDiffer:
    """Test RoleDiffer: diff_roles, diff_users."""

    def test_diff_roles_empty(self, sqlmodel_db):
        _seed_roles(sqlmodel_db)
        _seed_permissions(sqlmodel_db)
        from common_lib.modules.rbac.debug.service import RoleDiffer
        differ = RoleDiffer(sqlmodel_db)
        diff = differ.diff_roles(1, 2)
        assert diff.added == []
        assert diff.removed == []
        assert diff.common == []
        assert diff.source_role == "viewer"
        assert diff.target_role == "editor"

    def test_diff_roles_with_permissions(self, sqlmodel_db):
        _seed_roles(sqlmodel_db)
        _seed_permissions(sqlmodel_db)
        _seed_role_perms(sqlmodel_db, [(1, 1), (2, 1), (2, 2)])
        from common_lib.modules.rbac.debug.service import RoleDiffer
        differ = RoleDiffer(sqlmodel_db)
        diff = differ.diff_roles(1, 2)
        assert "project:read" in diff.common
        assert "project:write" in diff.removed
        assert len(diff.added) == 0

    def test_diff_users(self, sqlmodel_db):
        _seed_roles(sqlmodel_db)
        _seed_permissions(sqlmodel_db)
        _seed_role_perms(sqlmodel_db, [(1, 1), (2, 2)])
        from common_lib.modules.rbac.debug.service import RoleDiffer
        differ = RoleDiffer(sqlmodel_db)
        result = differ.diff_users(100, 200)
        assert "user_a_only" in result
        assert "user_b_only" in result
        assert "shared" in result
        assert len(result["user_a_only"]) == 0
        assert len(result["shared"]) == 0
