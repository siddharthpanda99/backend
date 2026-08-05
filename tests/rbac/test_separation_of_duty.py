"""Tests for SeparationOfDutyService — the genuinely new functionality in the roles submodule."""


from tests.rbac.conftest import roles, user_roles, permissions, role_permissions, rbac_sod_rules, rbac_sod_violations

import pytest
from datetime import datetime
from sqlalchemy import MetaData, Table, Column, Integer, String, Boolean, DateTime, ForeignKey, text
from sqlmodel import Session, create_engine
from sqlmodel.pool import StaticPool

from common_lib.modules.rbac.roles.service import SeparationOfDutyService

@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # Create only the tables we need — avoid importing all SQLModel metadata
    # which may reference tables (users, etc.) that don't exist in test DB
    metadata = MetaData()
    Table(
        "roles", metadata,
        Column("id", Integer, primary_key=True),
        Column("name", String, unique=True),
        Column("description", String),
        Column("is_system", Boolean, default=False),
        Column("priority", Integer, default=0),
        Column("created_at", DateTime),
        Column("updated_at", DateTime),
    )
    Table(
        "permissions", metadata,
        Column("id", Integer, primary_key=True),
        Column("name", String, unique=True),
        Column("description", String),
        Column("resource", String),
        Column("action", String),
        Column("scope", String),
        Column("created_at", DateTime),
        Column("updated_at", DateTime),
    )
    Table(
        "role_permissions", metadata,
        Column("role_id", Integer, ForeignKey("roles.id"), primary_key=True),
        Column("permission_id", Integer, ForeignKey("permissions.id"), primary_key=True),
    )
    Table(
        "user_roles", metadata,
        Column("user_id", Integer, primary_key=True),
        Column("role_id", Integer, ForeignKey("roles.id"), primary_key=True),
        Column("granted_by", Integer),
        Column("granted_at", DateTime),
        Column("expires_at", DateTime),
        Column("org_id", String),
        Column("team_id", String),
        Column("is_active", Boolean, default=True),
        Column("revoked_at", DateTime),
        Column("revoke_reason", String),
    )
    Table(
        "rbac_separation_of_duty_rules", metadata,
        Column("id", Integer, primary_key=True),
        Column("role_a_id", Integer, ForeignKey("roles.id")),
        Column("role_b_id", Integer, ForeignKey("roles.id")),
        Column("rule_type", String, default="static"),
        Column("description", String),
        Column("is_active", Boolean, default=True),
        Column("created_at", DateTime),
    )
    metadata.create_all(engine)
    with Session(engine) as session:
        yield session

@pytest.fixture(name="seed_roles")
def seed_roles_fixture(session: Session):
    """Create 4 roles with permissions for testing using raw SQL inserts."""
    role_ids = []
    for name in ["admin", "auditor", "developer", "viewer"]:
        session.execute(
            text("INSERT INTO roles (name, description) VALUES (:name, :desc)"),
            {"name": name, "desc": f"{name} role"}
        )
        session.commit()
        # Query back the inserted role ID
        result = session.execute(
            text("SELECT id FROM roles WHERE name = :name"), {"name": name}
        )
        role_id = result.scalar_one()
        role_ids.append(role_id)

    return role_ids

class TestSeparationOfDutyRules:
    def test_create_rule(self, session: Session, seed_roles):
        admin_id, auditor_id, developer_id, viewer_id = seed_roles
        svc = SeparationOfDutyService(session)

        rule = svc.create_rule(admin_id, auditor_id, description="Admin cannot also be auditor")
        assert rule.id is not None
        assert rule.role_a_id == admin_id
        assert rule.role_b_id == auditor_id
        assert rule.is_active is True

    def test_create_rule_same_role_raises(self, session: Session, seed_roles):
        admin_id = seed_roles[0]
        svc = SeparationOfDutyService(session)

        with pytest.raises(ValueError, match="same role"):
            svc.create_rule(admin_id, admin_id)

    def test_list_rules(self, session: Session, seed_roles):
        admin_id, auditor_id, developer_id, viewer_id = seed_roles
        svc = SeparationOfDutyService(session)

        svc.create_rule(admin_id, auditor_id)
        svc.create_rule(developer_id, viewer_id)

        rules = svc.list_rules()
        assert len(rules) == 2

    def test_deactivate_rule(self, session: Session, seed_roles):
        admin_id, auditor_id, _, _ = seed_roles
        svc = SeparationOfDutyService(session)

        rule = svc.create_rule(admin_id, auditor_id)
        assert svc.deactivate_rule(rule.id) is True

        rules = svc.list_rules()
        assert len(rules) == 0

        rules_all = svc.list_rules(include_inactive=True)
        assert len(rules_all) == 1

class TestSeparationOfDutyViolations:
    def _insert_user_role(self, session: Session, user_id: int, role_id: int, is_active: bool = True):
        """Insert a user-role assignment using raw SQL."""
        session.execute(
            text("INSERT INTO user_roles (user_id, role_id, is_active, granted_at) VALUES (:uid, :rid, :active, :now)"),
            {"uid": user_id, "rid": role_id, "active": is_active, "now": datetime.utcnow()}
        )
        session.commit()

    def test_no_violation_when_holding_one_role(self, session: Session, seed_roles):
        admin_id, auditor_id, _, _ = seed_roles
        svc = SeparationOfDutyService(session)

        svc.create_rule(admin_id, auditor_id)
        self._insert_user_role(session, user_id=1, role_id=admin_id)

        violations = svc.check_violation(user_id=1)
        assert len(violations) == 0

    def test_violation_when_holding_both_roles(self, session: Session, seed_roles):
        admin_id, auditor_id, _, _ = seed_roles
        svc = SeparationOfDutyService(session)

        svc.create_rule(admin_id, auditor_id)
        self._insert_user_role(session, user_id=1, role_id=admin_id)
        self._insert_user_role(session, user_id=1, role_id=auditor_id)

        violations = svc.check_violation(user_id=1)
        assert len(violations) == 1
        assert violations[0]["role_a_id"] == admin_id
        assert violations[0]["role_b_id"] == auditor_id

    def test_revoked_role_not_violation(self, session: Session, seed_roles):
        admin_id, auditor_id, _, _ = seed_roles
        svc = SeparationOfDutyService(session)

        svc.create_rule(admin_id, auditor_id)
        self._insert_user_role(session, user_id=1, role_id=admin_id, is_active=True)
        self._insert_user_role(session, user_id=1, role_id=auditor_id, is_active=False)

        violations = svc.check_violation(user_id=1)
        assert len(violations) == 0

    def test_multiple_violations(self, session: Session, seed_roles):
        admin_id, auditor_id, developer_id, viewer_id = seed_roles
        svc = SeparationOfDutyService(session)

        svc.create_rule(admin_id, auditor_id)
        svc.create_rule(developer_id, viewer_id)

        for rid in [admin_id, auditor_id, developer_id, viewer_id]:
            self._insert_user_role(session, user_id=1, role_id=rid)

        violations = svc.check_violation(user_id=1)
        assert len(violations) == 2

    def test_deactivated_rule_not_enforced(self, session: Session, seed_roles):
        admin_id, auditor_id, _, _ = seed_roles
        svc = SeparationOfDutyService(session)

        rule = svc.create_rule(admin_id, auditor_id)
        svc.deactivate_rule(rule.id)

        self._insert_user_role(session, user_id=1, role_id=admin_id)
        self._insert_user_role(session, user_id=1, role_id=auditor_id)

        violations = svc.check_violation(user_id=1)
        assert len(violations) == 0
