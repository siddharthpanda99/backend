"""Tests for roles/ submodule re-export pattern.

Verifies that importing from common_lib.modules.rbac.roles.* gives the
same objects as importing from the original locations, and that the
re-exported services are functionally equivalent.
"""


from tests.rbac.conftest import roles_table
import pytest
from datetime import datetime


# ===========================================================================
# Import Identity Tests
# ===========================================================================

class TestImportIdentity:
    """Verify that re-exports resolve to the same objects as original imports."""

    def test_user_role_service_is_same_class(self):
        """roles.UserRoleService should be the exact same class as user_role_service.UserRoleService."""
        from common_lib.modules.rbac.roles import UserRoleService as RolesUSR
        from common_lib.modules.rbac.user_role_service import UserRoleService as OrigUSR
        assert RolesUSR is OrigUSR, "roles.UserRoleService should be the same object as user_role_service.UserRoleService"

    def test_role_service_is_same_class(self):
        """roles.RoleService should be the exact same class as service.RoleService."""
        from common_lib.modules.rbac.roles import RoleService as RolesRS
        from common_lib.modules.rbac.service import RoleService as OrigRS
        assert RolesRS is OrigRS, "roles.RoleService should be the same object as service.RoleService"

    def test_user_role_model_is_same(self):
        """roles.UserRole should be the exact same model as models.UserRole."""
        from common_lib.modules.rbac.roles import UserRole as RolesUR
        from common_lib.modules.rbac.models import UserRole as OrigUR
        assert RolesUR is OrigUR

    def test_role_model_is_same(self):
        """roles.Role should be the exact same model as models.Role."""
        from common_lib.modules.rbac.roles import Role as RolesR
        from common_lib.modules.rbac.models import Role as OrigR
        assert RolesR is OrigR

    def test_permission_model_is_same(self):
        """roles.Permission should be the exact same model as models.Permission."""
        from common_lib.modules.rbac.roles import Permission as RolesP
        from common_lib.modules.rbac.models import Permission as OrigP
        assert RolesP is OrigP

    def test_role_inheritance_model_is_same(self):
        """roles.RoleInheritance should be the exact same model as models.RoleInheritance."""
        from common_lib.modules.rbac.roles import RoleInheritance as RolesRI
        from common_lib.modules.rbac.models import RoleInheritance as OrigRI
        assert RolesRI is OrigRI

    def test_role_permission_model_is_same(self):
        """roles.RolePermission should be the exact same model as models.RolePermission."""
        from common_lib.modules.rbac.roles import RolePermission as RolesRP
        from common_lib.modules.rbac.models import RolePermission as OrigRP
        assert RolesRP is OrigRP

    def test_scope_enum_is_same(self):
        """roles.ScopeEnum should be the exact same enum as models.ScopeEnum."""
        from common_lib.modules.rbac.roles import ScopeEnum as RolesSE
        from common_lib.modules.rbac.models import ScopeEnum as OrigSE
        assert RolesSE is OrigSE

    def test_separation_of_duty_service_exists(self):
        """SeparationOfDutyService should be importable from roles submodule."""
        from common_lib.modules.rbac.roles import SeparationOfDutyService
        assert SeparationOfDutyService is not None
        assert callable(SeparationOfDutyService)

    def test_separation_of_duty_rule_model_exists(self):
        """SeparationOfDutyRule should be importable from roles submodule."""
        from common_lib.modules.rbac.roles import SeparationOfDutyRule
        assert SeparationOfDutyRule is not None

# ===========================================================================
# Functional Equivalence Tests
# ===========================================================================

class TestFunctionalEquivalence:
    """Verify that re-exported services work identically to originals."""

    def _seed_role(self, db, role_id, name):
        now = datetime.utcnow()
        db.execute(roles_table.insert().values(id=role_id, name=name, created_at=now, updated_at=now))
        db.commit()

    def test_grant_via_reexport(self, sqlmodel_db):
        """UserRoleService.grant() works when imported from roles submodule."""
        self._seed_role(sqlmodel_db, 10, "admin")
        from common_lib.modules.rbac.roles import UserRoleService
        svc = UserRoleService(sqlmodel_db)
        assignment = svc.grant(user_id=1, role_id=10)
        assert assignment.user_id == 1
        assert assignment.role_id == 10
        assert assignment.is_active is True

    def test_revoke_via_reexport(self, sqlmodel_db):
        """UserRoleService.revoke() works when imported from roles submodule."""
        self._seed_role(sqlmodel_db, 11, "editor")
        from common_lib.modules.rbac.roles import UserRoleService
        svc = UserRoleService(sqlmodel_db)
        svc.grant(user_id=2, role_id=11)
        success = svc.revoke(user_id=2, role_id=11)
        assert success is True

    def test_list_user_roles_via_reexport(self, sqlmodel_db):
        """UserRoleService.list_user_roles() works when imported from roles submodule."""
        self._seed_role(sqlmodel_db, 12, "viewer")
        from common_lib.modules.rbac.roles import UserRoleService
        svc = UserRoleService(sqlmodel_db)
        svc.grant(user_id=3, role_id=12)
        roles = svc.list_user_roles(user_id=3)
        assert len(roles) == 1
        assert roles[0]["role_name"] == "viewer"

    def test_role_service_get_role_via_reexport(self, sqlmodel_db):
        """RoleService.get_role() works when imported from roles submodule."""
        self._seed_role(sqlmodel_db, 20, "team_lead")
        from common_lib.modules.rbac.roles import RoleService
        svc = RoleService(sqlmodel_db)
        role = svc.get_role(20)
        assert role is not None
        assert role.name == "team_lead"

    def test_role_service_list_roles_via_reexport(self, sqlmodel_db):
        """RoleService.list_roles() works when imported from roles submodule."""
        self._seed_role(sqlmodel_db, 21, "role_a")
        self._seed_role(sqlmodel_db, 22, "role_b")
        from common_lib.modules.rbac.roles import RoleService
        svc = RoleService(sqlmodel_db)
        roles = svc.list_roles()
        assert len(roles) >= 2

    def test_role_service_add_parent_role_via_reexport(self, sqlmodel_db):
        """RoleService.add_parent_role() works when imported from roles submodule."""
        self._seed_role(sqlmodel_db, 30, "parent_role")
        self._seed_role(sqlmodel_db, 31, "child_role")
        from common_lib.modules.rbac.roles import RoleService
        svc = RoleService(sqlmodel_db)
        success = svc.add_parent_role(child_role_id=31, parent_role_id=30)
        assert success is True
        parents = svc.get_parents(31)
        assert len(parents) == 1
        assert parents[0].name == "parent_role"

    def test_revoke_all_user_roles_via_reexport(self, sqlmodel_db):
        """UserRoleService.revoke_all_user_roles() works via re-export."""
        self._seed_role(sqlmodel_db, 40, "role_x")
        self._seed_role(sqlmodel_db, 41, "role_y")
        from common_lib.modules.rbac.roles import UserRoleService
        svc = UserRoleService(sqlmodel_db)
        svc.grant(user_id=5, role_id=40)
        svc.grant(user_id=5, role_id=41)
        count = svc.revoke_all_user_roles(user_id=5)
        assert count == 2

# ===========================================================================
# Separation of Duty Integration Tests
# ===========================================================================

class TestSoDViaRolesSubmodule:
    """Verify SeparationOfDutyService works through the roles submodule."""

    def test_create_sod_rule(self, sqlmodel_db):
        now = datetime.utcnow()
        sqlmodel_db.execute(roles_table.insert().values(id=50, name="auditor", created_at=now, updated_at=now))
        sqlmodel_db.execute(roles_table.insert().values(id=51, name="admin", created_at=now, updated_at=now))
        sqlmodel_db.commit()
        from common_lib.modules.rbac.roles import SeparationOfDutyService
        svc = SeparationOfDutyService(sqlmodel_db)
        rule = svc.create_rule(role_a_id=50, role_b_id=51, description="Auditor and admin conflict")
        assert rule.id is not None
        assert rule.role_a_id == 50
        assert rule.role_b_id == 51

    def test_check_violation(self, sqlmodel_db):
        now = datetime.utcnow()
        sqlmodel_db.execute(roles_table.insert().values(id=52, name="auditor2", created_at=now, updated_at=now))
        sqlmodel_db.execute(roles_table.insert().values(id=53, name="admin2", created_at=now, updated_at=now))
        sqlmodel_db.commit()
        from common_lib.modules.rbac.roles import SeparationOfDutyService, UserRoleService
        sod_svc = SeparationOfDutyService(sqlmodel_db)
        ur_svc = UserRoleService(sqlmodel_db)
        sod_svc.create_rule(role_a_id=52, role_b_id=53)
        ur_svc.grant(user_id=10, role_id=52)
        ur_svc.grant(user_id=10, role_id=53)
        violations = sod_svc.check_violation(user_id=10)
        assert len(violations) == 1
        assert violations[0]["role_a_id"] == 52
        assert violations[0]["role_b_id"] == 53

    def test_no_violation_when_holding_one_role(self, sqlmodel_db):
        now = datetime.utcnow()
        sqlmodel_db.execute(roles_table.insert().values(id=54, name="auditor3", created_at=now, updated_at=now))
        sqlmodel_db.execute(roles_table.insert().values(id=55, name="admin3", created_at=now, updated_at=now))
        sqlmodel_db.commit()
        from common_lib.modules.rbac.roles import SeparationOfDutyService, UserRoleService
        sod_svc = SeparationOfDutyService(sqlmodel_db)
        ur_svc = UserRoleService(sqlmodel_db)
        sod_svc.create_rule(role_a_id=54, role_b_id=55)
        ur_svc.grant(user_id=11, role_id=54)
        violations = sod_svc.check_violation(user_id=11)
        assert len(violations) == 0
