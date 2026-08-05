"""Tests for API submodule — Permission Check, Simulate, Explain, Matrix.

Uses a SQLModelSession wrapper for raw SQLAlchemy compatibility.
"""


from tests.rbac.conftest import permissions, roles, user_roles, role_permissions, role_inheritance, rbac_policy_rules, rbac_abac_conditions

import pytest
from datetime import datetime
from sqlalchemy import create_engine, MetaData, Table, Column, String, Boolean, DateTime, Integer, JSON
from sqlalchemy.orm import Session

def _seed_data(db):
    """Seed roles, permissions, and assignments for tests."""
    db.execute(roles.insert().values(id=1, name="admin", is_system=True))
    db.execute(roles.insert().values(id=2, name="viewer"))
    db.execute(permissions.insert().values(id=1, name="project.read", resource="project", action="read"))
    db.execute(permissions.insert().values(id=2, name="project.write", resource="project", action="write"))
    db.execute(permissions.insert().values(id=3, name="project.delete", resource="project", action="delete"))
    db.execute(permissions.insert().values(id=4, name="issue.read", resource="issue", action="read"))
    db.execute(role_permissions.insert().values(role_id=1, permission_id=1))
    db.execute(role_permissions.insert().values(role_id=1, permission_id=2))
    db.execute(role_permissions.insert().values(role_id=1, permission_id=3))
    db.execute(role_permissions.insert().values(role_id=1, permission_id=4))
    db.execute(role_permissions.insert().values(role_id=2, permission_id=1))
    db.execute(role_permissions.insert().values(role_id=2, permission_id=4))
    db.execute(user_roles.insert().values(user_id=1, role_id=1, is_active=True))
    db.execute(user_roles.insert().values(user_id=2, role_id=2, is_active=True))
    db.commit()

# ===========================================================================
# Check Tests
# ===========================================================================

class TestCheck:
    def test_check_allowed(self, db):
        _seed_data(db)
        from common_lib.modules.rbac.api.service import PermissionCheckService
        svc = PermissionCheckService(db)
        result = svc.check(user_id=1, resource="project", action="read")
        assert result["allowed"] is True

    def test_check_denied(self, db):
        _seed_data(db)
        from common_lib.modules.rbac.api.service import PermissionCheckService
        svc = PermissionCheckService(db)
        result = svc.check(user_id=2, resource="project", action="delete")
        assert result["allowed"] is False

    def test_check_many(self, db):
        _seed_data(db)
        from common_lib.modules.rbac.api.service import PermissionCheckService
        svc = PermissionCheckService(db)
        checks = [
            {"resource": "project", "action": "read"},
            {"resource": "project", "action": "delete"},
            {"resource": "issue", "action": "read"},
        ]
        results = svc.check_many(user_id=2, checks=checks)
        assert len(results) == 3
        assert results[0]["allowed"] is True  # viewer can read project
        assert results[1]["allowed"] is False  # viewer can't delete project
        assert results[2]["allowed"] is True  # viewer can read issue

# ===========================================================================
# Simulate Tests
# ===========================================================================

class TestSimulate:
    def test_simulate_returns_reasoning(self, db):
        _seed_data(db)
        from common_lib.modules.rbac.api.service import PermissionCheckService
        svc = PermissionCheckService(db)
        result = svc.simulate(user_id=1, resource="project", action="read")
        assert "reasoning" in result
        assert "matching_permissions" in result
        assert len(result["reasoning"]) > 0

    def test_simulate_shows_total_permissions(self, db):
        _seed_data(db)
        from common_lib.modules.rbac.api.service import PermissionCheckService
        svc = PermissionCheckService(db)
        result = svc.simulate(user_id=1, resource="project", action="read")
        assert result["total_permissions"] > 0

# ===========================================================================
# Explain Tests
# ===========================================================================

class TestExplain:
    def test_explain_allowed(self, db):
        _seed_data(db)
        from common_lib.modules.rbac.api.service import PermissionCheckService
        svc = PermissionCheckService(db)
        result = svc.explain(user_id=1, resource="project", action="read")
        assert result["allowed"] is True
        assert len(result["sections"]) >= 3

    def test_explain_denied(self, db):
        _seed_data(db)
        from common_lib.modules.rbac.api.service import PermissionCheckService
        svc = PermissionCheckService(db)
        result = svc.explain(user_id=2, resource="project", action="delete")
        assert result["allowed"] is False
        # Should include "How to Grant Access" section
        titles = [s["title"] for s in result["sections"]]
        assert any("Grant" in t for t in titles)

# ===========================================================================
# Matrix Tests
# ===========================================================================

class TestMatrix:
    def test_get_permission_matrix(self, db):
        _seed_data(db)
        from common_lib.modules.rbac.api.service import PermissionCheckService
        svc = PermissionCheckService(db)
        matrix = svc.get_permission_matrix()
        assert len(matrix["roles"]) == 2
        assert len(matrix["permissions"]) == 4
        assert len(matrix["matrix"]) == 2

    def test_matrix_filtered_by_resource(self, db):
        _seed_data(db)
        from common_lib.modules.rbac.api.service import PermissionCheckService
        svc = PermissionCheckService(db)
        matrix = svc.get_permission_matrix(resource_filter="project")
        assert len(matrix["permissions"]) == 3  # project.read, project.write, project.delete
