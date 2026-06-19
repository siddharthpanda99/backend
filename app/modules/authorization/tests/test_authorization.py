# Authorization (RBAC) Tests
import pytest


class TestRoleService:
    """Tests for RoleService"""

    def test_role_service_imports(self):
        from common_lib.modules.rbac.service import RoleService

        assert RoleService is not None

    def test_role_service_has_list_roles_method(self):
        from common_lib.modules.rbac.service import RoleService

        assert hasattr(RoleService, "list_roles")

    def test_role_service_has_get_role_method(self):
        from common_lib.modules.rbac.service import RoleService

        assert hasattr(RoleService, "get_role")

    def test_role_service_has_create_role_method(self):
        from common_lib.modules.rbac.service import RoleService

        assert hasattr(RoleService, "create_role")

    def test_role_service_has_update_role_method(self):
        from common_lib.modules.rbac.service import RoleService

        assert hasattr(RoleService, "update_role")

    def test_role_service_has_delete_role_method(self):
        from common_lib.modules.rbac.service import RoleService

        assert hasattr(RoleService, "delete_role")


class TestPermissionService:
    """Tests for PermissionService"""

    def test_permission_service_imports(self):
        from common_lib.modules.rbac.service import PermissionService

        assert PermissionService is not None

    def test_permission_service_has_list_permissions_method(self):
        from common_lib.modules.rbac.service import PermissionService

        assert hasattr(PermissionService, "list_permissions")

    def test_permission_service_has_get_permission_method(self):
        from common_lib.modules.rbac.service import PermissionService

        assert hasattr(PermissionService, "get_permission")

    def test_permission_service_has_create_permission_method(self):
        from common_lib.modules.rbac.service import PermissionService

        assert hasattr(PermissionService, "create_permission")

    def test_permission_service_has_assign_permission_method(self):
        from common_lib.modules.rbac.service import PermissionService

        assert hasattr(PermissionService, "assign_permission")


class TestRBACSchemas:
    """Tests for RBAC schemas"""

    def test_role_create_imports(self):
        from common_lib.modules.rbac.schemas import RoleCreate

        assert RoleCreate is not None

    def test_role_update_imports(self):
        from common_lib.modules.rbac.schemas import RoleUpdate

        assert RoleUpdate is not None

    def test_role_read_imports(self):
        from common_lib.modules.rbac.schemas import RoleRead

        assert RoleRead is not None

    def test_permission_create_imports(self):
        from common_lib.modules.rbac.schemas import PermissionCreate

        assert PermissionCreate is not None

    def test_permission_read_imports(self):
        from common_lib.modules.rbac.schemas import PermissionRead

        assert PermissionRead is not None


class TestRBACModels:
    """Tests for RBAC models"""

    def test_role_model_imports(self):
        from common_lib.modules.rbac.models import Role

        assert Role is not None

    def test_permission_model_imports(self):
        from common_lib.modules.rbac.models import Permission

        assert Permission is not None

    def test_role_permission_model_imports(self):
        from common_lib.modules.rbac.models import RolePermission

        assert RolePermission is not None


class TestRBACServiceBehavior:
    """Tests for RBAC service behavior"""

    def test_role_service_requires_session(self):
        from common_lib.modules.rbac.service import RoleService

        service = RoleService(session=None)
        assert service.session is None

    def test_permission_service_requires_session(self):
        from common_lib.modules.rbac.service import PermissionService

        service = PermissionService(session=None)
        assert service.session is None


class TestAuthzIntegration:
    """Integration tests for RBAC-gated CRUD helpers"""

    def test_sync_role_to_authz_creates_role(self):
        from common_lib.modules.auth.authorization import (
            sync_role_to_authz,
            remove_role_from_authz,
            role_service,
        )

        rid = sync_role_to_authz(name="test_integration_role")
        assert rid is not None
        role = role_service.get_role(rid)
        assert role is not None
        assert role.name == "test_integration_role"
        remove_role_from_authz(name="test_integration_role")
        assert role_service.get_role(rid) is None

    def test_sync_role_to_authz_idempotent(self):
        from common_lib.modules.auth.authorization import (
            sync_role_to_authz,
            remove_role_from_authz,
        )

        r1 = sync_role_to_authz(name="idempotent_role")
        r2 = sync_role_to_authz(name="idempotent_role")
        assert r1 == r2
        remove_role_from_authz(name="idempotent_role")

    def test_sync_permission_to_authz_creates_permission(self):
        from common_lib.modules.auth.authorization import (
            sync_permission_to_authz,
            remove_permission_from_authz,
            permission_service,
        )

        pid = sync_permission_to_authz(action="test.integration")
        assert pid is not None
        perms = permission_service.find_by_action("test.integration")
        assert len(perms) == 1
        remove_permission_from_authz(action="test.integration")
        assert len(permission_service.find_by_action("test.integration")) == 0

    def _make_identity(self, subject_id="user1", tenant_id="default", role_ids=None):
        from common_lib.modules.auth.authorization import (
            PlatformIdentity,
            SubjectType,
            SubjectStatus,
        )
        from datetime import datetime, timezone

        return PlatformIdentity(
            subject_id=subject_id,
            subject_type=SubjectType.HUMAN,
            display_name="Test User",
            tenant_id=tenant_id,
            role_ids=role_ids or [],
            created_at=datetime.now(timezone.utc),
            created_by="system",
            status=SubjectStatus.ACTIVE,
        )

    def test_verify_tenant_isolation_allows_same_tenant(self):
        from common_lib.modules.auth.authorization import verify_tenant_isolation

        identity = self._make_identity(tenant_id="tenant_a")
        result = verify_tenant_isolation(identity, resource_tenant_id="tenant_a")
        assert result == "tenant_a"

    def test_verify_tenant_isolation_blocks_cross_tenant(self):
        from common_lib.modules.auth.authorization import verify_tenant_isolation

        identity = self._make_identity(tenant_id="tenant_a")
        with pytest.raises(PermissionError):
            verify_tenant_isolation(identity, resource_tenant_id="tenant_b")

    def test_check_hitl_before_destructive_high_risk_action(self):
        from common_lib.modules.auth.authorization import (
            check_hitl_before_destructive,
            SubjectType,
        )

        result = check_hitl_before_destructive(
            subject_id="user1",
            subject_type=SubjectType.HUMAN,
            action="role.delete",
            resource_id="role_123",
            resource_type="role",
            tenant_id="default",
        )
        assert result is not None
        assert result["status"] == "pending_approval"

    def test_check_hitl_before_destructive_low_risk_action(self):
        from common_lib.modules.auth.authorization import (
            check_hitl_before_destructive,
            SubjectType,
        )

        result = check_hitl_before_destructive(
            subject_id="user1",
            subject_type=SubjectType.HUMAN,
            action="role.read",
            resource_id="role_123",
            resource_type="role",
            tenant_id="default",
        )
        assert result is None

    def test_verify_role_membership_happy_path(self):
        from common_lib.modules.auth.authorization import (
            verify_role_membership,
            sync_role_to_authz,
            remove_role_from_authz,
        )

        role_name = "test_membership_role"
        rid = sync_role_to_authz(name=role_name)
        identity = self._make_identity(tenant_id="default", role_ids=[rid])
        assert verify_role_membership(identity, [role_name]) is True
        assert verify_role_membership(identity, ["nonexistent"]) is False
        remove_role_from_authz(name=role_name)

    def test_log_crud_mutation_creates_audit_entry(self):
        from common_lib.modules.auth.authorization import (
            log_crud_mutation,
            audit_service,
            SubjectType,
        )

        before = len(audit_service._entries)
        log_crud_mutation(
            subject_id="user1",
            subject_type=SubjectType.HUMAN,
            action="role.create",
            resource_id="42",
            resource_type="role",
            tenant_id="default",
        )
        after = len(audit_service._entries)
        assert after == before + 1
        last = audit_service._entries[-1]
        assert last.action == "role.create"
        assert last.resource_id == "42"

    def test_check_permission_validates_via_authz_checker(self):
        from common_lib.modules.auth.authorization import (
            check_permission,
            build_authz_checker,
            SubjectType,
        )

        checker = build_authz_checker(
            subject_id="user1",
            subject_type=SubjectType.HUMAN,
            tenant_id="default",
        )
        with pytest.raises(PermissionError):
            check_permission(checker, "nonexistent.action", "res_1", "test")
