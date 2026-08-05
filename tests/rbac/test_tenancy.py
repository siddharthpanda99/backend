"""Tests for Tenancy submodule — Organizations, Teams, Org Policies.

Uses a SQLModelSession wrapper to make raw SQLAlchemy sessions work
with services that call session.exec() (SQLModel-specific).
"""


import pytest
from datetime import datetime

# ===========================================================================
# Organization Tests
# ===========================================================================

class TestOrganization:
    def test_create_org(self, sqlmodel_db):
        from common_lib.modules.rbac.tenant_service import OrganizationService
        svc = OrganizationService(sqlmodel_db)
        org = svc.create(name="Acme Corp", slug="acme", created_by=1)
        assert org.id is not None
        assert org.name == "Acme Corp"
        assert org.slug == "acme"

    def test_get_org_by_slug(self, sqlmodel_db):
        from common_lib.modules.rbac.tenant_service import OrganizationService
        svc = OrganizationService(sqlmodel_db)
        svc.create(name="Acme Corp", slug="acme")
        found = svc.get_by_slug("acme")
        assert found is not None
        assert found.name == "Acme Corp"

    def test_add_and_list_members(self, sqlmodel_db):
        from common_lib.modules.rbac.tenant_service import OrganizationService
        svc = OrganizationService(sqlmodel_db)
        org = svc.create(name="Acme", slug="acme")
        svc.add_member(org.id, user_id=1, role="owner")
        svc.add_member(org.id, user_id=2, role="member")
        members = svc.list_members(org.id)
        assert len(members) == 2
        roles_map = {m.user_id: m.role for m in members}
        assert roles_map[1] == "owner"
        assert roles_map[2] == "member"

    def test_remove_member(self, sqlmodel_db):
        from common_lib.modules.rbac.tenant_service import OrganizationService
        svc = OrganizationService(sqlmodel_db)
        org = svc.create(name="Acme", slug="acme")
        svc.add_member(org.id, user_id=1)
        success = svc.remove_member(org.id, user_id=1)
        assert success is True
        members = svc.list_members(org.id)
        assert len(members) == 0

    def test_list_user_orgs(self, sqlmodel_db):
        from common_lib.modules.rbac.tenant_service import OrganizationService
        svc = OrganizationService(sqlmodel_db)
        org1 = svc.create(name="Acme", slug="acme")
        org2 = svc.create(name="Globex", slug="globex")
        svc.add_member(org1.id, user_id=1)
        svc.add_member(org2.id, user_id=1)
        user_orgs = svc.list_user_orgs(user_id=1)
        assert len(user_orgs) == 2

# ===========================================================================
# Team Tests
# ===========================================================================

class TestTeam:
    def test_create_team(self, sqlmodel_db):
        from common_lib.modules.rbac.tenant_service import TeamServiceRBAC
        svc = TeamServiceRBAC(sqlmodel_db)
        team = svc.create(name="Backend", slug="backend", created_by=1)
        assert team.id is not None
        assert team.name == "Backend"

    def test_add_and_list_team_members(self, sqlmodel_db):
        from common_lib.modules.rbac.tenant_service import TeamServiceRBAC
        svc = TeamServiceRBAC(sqlmodel_db)
        team = svc.create(name="Backend", slug="backend")
        svc.add_member(team.id, user_id=1, role="admin")
        svc.add_member(team.id, user_id=2, role="member")
        members = svc.list_members(team.id)
        assert len(members) == 2

    def test_list_user_teams(self, sqlmodel_db):
        from common_lib.modules.rbac.tenant_service import TeamServiceRBAC
        svc = TeamServiceRBAC(sqlmodel_db)
        t1 = svc.create(name="Backend", slug="backend")
        t2 = svc.create(name="Frontend", slug="frontend")
        svc.add_member(t1.id, user_id=1)
        svc.add_member(t2.id, user_id=1)
        teams = svc.list_user_teams(user_id=1)
        assert len(teams) == 2

    def test_list_teams_by_org(self, sqlmodel_db):
        from common_lib.modules.rbac.tenant_service import TeamServiceRBAC
        svc = TeamServiceRBAC(sqlmodel_db)
        svc.create(name="Backend", slug="backend", org_id=10)
        svc.create(name="Frontend", slug="frontend", org_id=10)
        svc.create(name="DevOps", slug="devops", org_id=20)
        teams = svc.list_teams(org_id=10)
        assert len(teams) == 2

# ===========================================================================
# Org Policy Tests
# ===========================================================================

class TestOrgPolicy:
    def test_create_policy(self, sqlmodel_db):
        from common_lib.modules.rbac.organization_policy_service import OrganizationPolicyService
        svc = OrganizationPolicyService(sqlmodel_db)
        policy = svc.create_or_update_policy("org-1", {"max_roles_per_user": 5, "allow_guests": False})
        assert policy.org_id == "org-1"
        assert policy.max_roles_per_user == 5
        assert policy.allow_guests is False

    def test_deny_permission(self, sqlmodel_db):
        from common_lib.modules.rbac.organization_policy_service import OrganizationPolicyService
        svc = OrganizationPolicyService(sqlmodel_db)
        policy = svc.deny_permission("org-1", "project.delete")
        assert "project.delete" in policy.denied_permissions
        assert svc.is_permission_denied("org-1", "project.delete") is True

    def test_allow_permission_removes_from_deny(self, sqlmodel_db):
        from common_lib.modules.rbac.organization_policy_service import OrganizationPolicyService
        svc = OrganizationPolicyService(sqlmodel_db)
        svc.deny_permission("org-1", "project.delete")
        policy = svc.allow_permission("org-1", "project.delete")
        assert "project.delete" not in (policy.denied_permissions or [])

    def test_policy_summary(self, sqlmodel_db):
        from common_lib.modules.rbac.organization_policy_service import OrganizationPolicyService
        svc = OrganizationPolicyService(sqlmodel_db)
        svc.create_or_update_policy("org-1", {"max_roles_per_user": 3})
        summary = svc.get_org_policy_summary("org-1")
        assert summary["has_policy"] is True
        assert summary["max_roles_per_user"] == 3
