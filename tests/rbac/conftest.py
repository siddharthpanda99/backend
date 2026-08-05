"""Shared fixtures and helpers for RBAC test suite.

Eliminates duplicate SQLModelSession class, table definitions, and seed
helpers across all 18 RBAC test files. All tables registered under a single
metadata object to prevent "no such table" errors.

Usage:
    from tests.rbac.conftest import SQLModelSession, db

    class TestMyFeature:
        def test_something(self, db):
            db.execute(roles.insert().values(...))
            db.commit()
"""

import uuid
from datetime import datetime, timedelta
from sqlalchemy import create_engine, MetaData, Table, Column, String, Boolean, DateTime, Integer, JSON
from sqlalchemy.orm import Session
import pytest


# ===========================================================================
# SQLModelSession Wrapper
# ===========================================================================

class SQLModelSession:
    """Thin wrapper that adds .exec() to a raw SQLAlchemy Session.

    SQLModel uses session.exec(select(...)) instead of session.execute(...).
    This wrapper makes raw SQLAlchemy sessions compatible with services that
    use the SQLModel pattern.
    """

    def __init__(self, raw: Session):
        self._raw = raw

    def exec(self, stmt):
        return self._raw.execute(stmt).scalars()

    def get(self, model, id):
        return self._raw.get(model, id)

    def add(self, obj):
        self._raw.add(obj)

    def commit(self):
        self._raw.commit()

    def refresh(self, obj):
        self._raw.refresh(obj)

    def delete(self, obj):
        self._raw.delete(obj)

    def close(self):
        self._raw.close()

    def add_all(self, objs):
        self._raw.add_all(objs)

    def execute(self, stmt):
        return self._raw.execute(stmt)

    def __getattr__(self, name):
        return getattr(self._raw, name)


# ===========================================================================
# Core RBAC Tables
# ===========================================================================

metadata = MetaData()

permissions = Table(
    "permissions", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String, unique=True, nullable=False),
    Column("description", String),
    Column("resource", String, nullable=False),
    Column("action", String, nullable=False),
    Column("scope", String, default="global"),
    Column("created_at", DateTime),
    Column("updated_at", DateTime),
)

roles = Table(
    "roles", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String, unique=True, nullable=False),
    Column("description", String),
    Column("is_system", Boolean, default=False),
    Column("priority", Integer, default=0),
    Column("created_at", DateTime),
    Column("updated_at", DateTime),
)

role_permissions = Table(
    "role_permissions", metadata,
    Column("role_id", Integer, nullable=False),
    Column("permission_id", Integer, nullable=False),
)

user_roles = Table(
    "user_roles", metadata,
    Column("user_id", Integer, nullable=False),
    Column("role_id", Integer, nullable=False),
    Column("granted_by", Integer),
    Column("granted_at", DateTime),
    Column("expires_at", DateTime),
    Column("org_id", String),
    Column("team_id", String),
    Column("is_active", Boolean, default=True),
    Column("revoked_at", DateTime),
    Column("revoke_reason", String),
    Column("created_at", DateTime),
    Column("updated_at", DateTime),
)

role_inheritance = Table(
    "role_inheritance", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("parent_role_id", Integer, nullable=False),
    Column("child_role_id", Integer, nullable=False),
    Column("created_at", DateTime),
)

resource_ownership = Table(
    "resource_ownership", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("resource_type", String, index=True),
    Column("resource_id", String, index=True),
    Column("owner_user_id", Integer),
    Column("owner_team_id", String),
    Column("owner_org_id", String),
    Column("created_at", DateTime),
    Column("transferred_at", DateTime),
)

users = Table(
    "users", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("username", String),
    Column("email", String),
)


# ===========================================================================
# Policy Engine Tables
# ===========================================================================

rbac_policy_rules = Table(
    "rbac_policy_rules", metadata,
    Column("id", String, primary_key=True),
    Column("name", String, nullable=False),
    Column("description", String),
    Column("enabled", Boolean, default=True),
    Column("effect", String, default="allow"),
    Column("subject_type", String),
    Column("subject_ids", JSON),
    Column("resource_type", String),
    Column("resource_ids", JSON),
    Column("resource_pattern", String),
    Column("actions", JSON),
    Column("scope", String),
    Column("conditions_logic", String, default="and"),
    Column("condition_ids", JSON),
    Column("priority", Integer, default=100),
    Column("org_id", String),
    Column("version", Integer, default=1),
    Column("tags", JSON),
    Column("created_at", DateTime),
    Column("updated_at", DateTime),
    Column("created_by", String),
)

rbac_abac_conditions = Table(
    "rbac_abac_conditions", metadata,
    Column("id", String, primary_key=True),
    Column("name", String, nullable=False),
    Column("description", String),
    Column("attribute_source", String, default="subject"),
    Column("attribute_name", String, nullable=False),
    Column("operator", String, default="equals"),
    Column("value", String),
    Column("value_type", String, default="string"),
    Column("value2", String),
    Column("enabled", Boolean, default=True),
    Column("created_at", DateTime),
    Column("updated_at", DateTime),
)

rbac_rebac_relations = Table(
    "rbac_rebac_relations", metadata,
    Column("id", String, primary_key=True),
    Column("subject_type", String, nullable=False),
    Column("subject_id", String, nullable=False),
    Column("relation", String, nullable=False),
    Column("object_type", String, nullable=False),
    Column("object_id", String, nullable=False),
    Column("org_id", String),
    Column("transitive", Boolean, default=False),
    Column("expires_at", DateTime),
    Column("granted_by", String),
    Column("granted_at", DateTime),
    Column("revoked_at", DateTime),
    Column("revoked_reason", String),
)


# ===========================================================================
# Tenancy Tables
# ===========================================================================

organizations_rbac = Table(
    "organizations_rbac", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String, nullable=False),
    Column("slug", String, unique=True, nullable=False),
    Column("description", String),
    Column("logo_url", String),
    Column("settings", JSON),
    Column("is_active", Boolean, default=True),
    Column("created_by", Integer),
    Column("created_at", DateTime),
    Column("updated_at", DateTime),
)

org_memberships = Table(
    "org_memberships", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("org_id", Integer, nullable=False),
    Column("user_id", Integer, nullable=False),
    Column("role", String, default="member"),
    Column("is_active", Boolean, default=True),
    Column("invited_by", Integer),
    Column("joined_at", DateTime),
    Column("created_at", DateTime),
    Column("updated_at", DateTime),
)

teams_rbac = Table(
    "teams_rbac", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String, nullable=False),
    Column("slug", String, unique=True, nullable=False),
    Column("description", String),
    Column("org_id", Integer),
    Column("is_active", Boolean, default=True),
    Column("created_by", Integer),
    Column("settings", JSON),
    Column("created_at", DateTime),
    Column("updated_at", DateTime),
)

team_memberships = Table(
    "team_memberships", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("team_id", Integer, nullable=False),
    Column("user_id", Integer, nullable=False),
    Column("role", String, default="member"),
    Column("is_active", Boolean, default=True),
    Column("joined_at", DateTime),
    Column("created_at", DateTime),
    Column("updated_at", DateTime),
)


# ===========================================================================
# Org Policy Tables
# ===========================================================================

rbac_org_policies = Table(
    "rbac_org_policies", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("org_id", String, unique=True, nullable=False),
    Column("default_role_ids", JSON),
    Column("enforce_role_inheritance", Boolean, default=True),
    Column("max_roles_per_user", Integer, default=0),
    Column("allow_guests", Boolean, default=True),
    Column("allow_custom_roles", Boolean, default=True),
    Column("denied_permissions", JSON),
    Column("created_at", DateTime),
    Column("updated_at", DateTime),
    Column("created_by", Integer),
)

rbac_org_role_overrides = Table(
    "rbac_org_role_overrides", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("org_id", String, nullable=False),
    Column("role_id", Integer, nullable=False),
    Column("additional_permission_names", JSON),
    Column("removed_permission_names", JSON),
    Column("created_at", DateTime),
    Column("updated_at", DateTime),
)


# ===========================================================================
# Field Security Tables
# ===========================================================================

field_security_rules = Table(
    "field_security_rules", metadata,
    Column("id", String, primary_key=True),
    Column("workspace_id", String),
    Column("project_id", String),
    Column("resource_type", String, nullable=False),
    Column("field_key", String, nullable=False),
    Column("role_name", String, nullable=False),
    Column("access_level", String, default="editable"),
    Column("conditions", JSON),
    Column("is_active", Boolean, default=True),
    Column("created_by", String),
    Column("created_at", DateTime),
    Column("updated_at", DateTime),
)

field_security_overrides = Table(
    "field_security_overrides", metadata,
    Column("id", String, primary_key=True),
    Column("rule_id", String),
    Column("user_id", Integer, nullable=False),
    Column("resource_type", String, nullable=False),
    Column("field_key", String, nullable=False),
    Column("access_level", String, default="editable"),
    Column("is_active", Boolean, default=True),
    Column("expires_at", DateTime),
    Column("granted_by", Integer),
    Column("reason", String),
    Column("created_at", DateTime),
)


# ===========================================================================
# Separation of Duty Tables
# ===========================================================================

rbac_sod_rules = Table(
    "rbac_sod_rules", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String, unique=True, nullable=False),
    Column("description", String),
    Column("conflicting_role_ids", JSON),
    Column("conflicting_permission_names", JSON),
    Column("is_active", Boolean, default=True),
    Column("created_at", DateTime),
    Column("updated_at", DateTime),
)

rbac_sod_violations = Table(
    "rbac_sod_violations", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("rule_id", Integer),
    Column("user_id", Integer, nullable=False),
    Column("description", String),
    Column("is_resolved", Boolean, default=False),
    Column("created_at", DateTime),
    Column("resolved_at", DateTime),
)

rbac_separation_of_duty_rules = Table(
    "rbac_separation_of_duty_rules", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("role_a_id", Integer, nullable=False),
    Column("role_b_id", Integer, nullable=False),
    Column("rule_type", String, default="static"),
    Column("description", String),
    Column("is_active", Boolean, default=True),
    Column("created_at", DateTime),
)


# ===========================================================================
# Session & MFA Tables
# ===========================================================================

user_sessions = Table(
    "user_sessions", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_id", Integer, nullable=False),
    Column("session_token_hash", String, unique=True, nullable=False),
    Column("ip_address", String),
    Column("user_agent", String),
    Column("device_info", JSON),
    Column("is_active", Boolean, default=True),
    Column("last_activity_at", DateTime),
    Column("expires_at", DateTime),
    Column("revoked_at", DateTime),
    Column("revoke_reason", String),
    Column("created_at", DateTime),
    Column("updated_at", DateTime),
)

mfa_secrets = Table(
    "mfa_secrets", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_id", Integer, nullable=False, unique=True),
    Column("totp_secret", String, nullable=False),
    Column("totp_algorithm", String, default="SHA1"),
    Column("totp_digits", Integer, default=6),
    Column("totp_period", Integer, default=30),
    Column("is_enabled", Boolean, default=False),
    Column("verified_at", DateTime),
    Column("backup_codes_hash", String),
    Column("last_used_at", DateTime),
    Column("created_at", DateTime),
    Column("updated_at", DateTime),
)

mfa_backup_codes = Table(
    "mfa_backup_codes", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_id", Integer, nullable=False),
    Column("code_hash", String, nullable=False),
    Column("used_at", DateTime),
    Column("created_at", DateTime),
    Column("updated_at", DateTime),
)


# ===========================================================================
# Machine Auth Tables
# ===========================================================================

api_keys = Table(
    "api_keys", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_id", Integer, nullable=False),
    Column("key_hash", String, unique=True, nullable=False),
    Column("name", String),
    Column("scopes", JSON),
    Column("is_active", Boolean, default=True),
    Column("expires_at", DateTime),
    Column("last_used_at", DateTime),
    Column("created_at", DateTime),
)

agent_credentials = Table(
    "agent_credentials", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("agent_id", String, unique=True, nullable=False),
    Column("name", String, nullable=False),
    Column("credential_hash", String),
    Column("permissions", JSON),
    Column("is_active", Boolean, default=True),
    Column("created_at", DateTime),
    Column("expires_at", DateTime),
)


# ===========================================================================
# Audit Tables
# ===========================================================================

rbac_audit_logs = Table(
    "rbac_audit_logs", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("action", String, nullable=False),
    Column("actor_id", Integer),
    Column("target_type", String),
    Column("target_id", String),
    Column("details", JSON),
    Column("ip_address", String),
    Column("created_at", DateTime),
)

rbac_access_reviews = Table(
    "rbac_access_reviews", metadata,
    Column("id", String, primary_key=True),
    Column("name", String, nullable=False),
    Column("review_type", String, default="role_assignment"),
    Column("scope_type", String),
    Column("scope_id", String),
    Column("status", String, default="pending"),
    Column("created_by", Integer),
    Column("reviewer_ids", JSON),
    Column("created_at", DateTime),
    Column("due_at", DateTime),
    Column("completed_at", DateTime),
)

rbac_access_review_items = Table(
    "rbac_access_review_items", metadata,
    Column("id", String, primary_key=True),
    Column("review_id", String, nullable=False),
    Column("user_id", Integer, nullable=False),
    Column("role_id", Integer),
    Column("decision", String),
    Column("decision_reason", String),
    Column("decided_by", Integer),
    Column("decided_at", DateTime),
    Column("created_at", DateTime),
)

rbac_entitlement_requests = Table(
    "rbac_entitlement_requests", metadata,
    Column("id", String, primary_key=True),
    Column("requester_id", Integer, nullable=False),
    Column("permission_name", String),
    Column("role_name", String),
    Column("reason", String),
    Column("status", String, default="pending"),
    Column("reviewer_ids", JSON),
    Column("approved_by", Integer),
    Column("approved_at", DateTime),
    Column("denied_reason", String),
    Column("created_at", DateTime),
    Column("expires_at", DateTime),
)


# ===========================================================================
# Delegation Tables
# ===========================================================================

rbac_delegations = Table(
    "rbac_delegations", metadata,
    Column("id", String, primary_key=True),
    Column("delegator_id", Integer, nullable=False),
    Column("delegate_id", Integer, nullable=False),
    Column("role_ids", JSON),
    Column("permission_names", JSON),
    Column("reason", String),
    Column("expires_at", DateTime),
    Column("is_active", Boolean, default=True),
    Column("revoked_at", DateTime),
    Column("created_at", DateTime),
)

rbac_impersonation_logs = Table(
    "rbac_impersonation_logs", metadata,
    Column("id", String, primary_key=True),
    Column("admin_id", Integer, nullable=False),
    Column("target_user_id", Integer, nullable=False),
    Column("reason", String),
    Column("started_at", DateTime),
    Column("ended_at", DateTime),
)


# ===========================================================================
# Cache Tables
# ===========================================================================

rbac_cache_entries = Table(
    "rbac_cache_entries", metadata,
    Column("cache_key", String, primary_key=True),
    Column("user_id", Integer),
    Column("permission_name", String),
    Column("result", Boolean),
    Column("ttl_seconds", Integer, default=300),
    Column("created_at", DateTime),
    Column("expires_at", DateTime),
    Column("invalidated_at", DateTime),
)


# ===========================================================================
# View & Dashboard Permission Tables
# ===========================================================================

rbac_view_permissions = Table(
    "rbac_view_permissions", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("view_id", String, nullable=False),
    Column("view_type", String, default="saved_filter"),
    Column("user_id", Integer),
    Column("role_id", Integer),
    Column("workspace_id", String),
    Column("access_level", String, default="read"),
    Column("granted_at", DateTime),
)

rbac_dashboard_permissions = Table(
    "rbac_dashboard_permissions", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("dashboard_id", String, nullable=False),
    Column("user_id", Integer),
    Column("role_id", Integer),
    Column("workspace_id", String),
    Column("access_level", String, default="read"),
    Column("granted_at", DateTime),
)


# ===========================================================================
# _table Suffixed Aliases (compatibility with existing test files)
# ===========================================================================

permissions_table = permissions
roles_table = roles
role_permissions_table = role_permissions
user_roles_table = user_roles
role_inheritance_table = role_inheritance
resource_ownership_table = resource_ownership
users_table = users
rbac_policy_rules_table = rbac_policy_rules
rbac_abac_conditions_table = rbac_abac_conditions
rbac_rebac_relations_table = rbac_rebac_relations
organizations_rbac_table = organizations_rbac
org_memberships_table = org_memberships
teams_rbac_table = teams_rbac
team_memberships_table = team_memberships
rbac_org_policies_table = rbac_org_policies
rbac_org_role_overrides_table = rbac_org_role_overrides
field_security_rules_table = field_security_rules
field_security_overrides_table = field_security_overrides
rbac_sod_rules_table = rbac_sod_rules
rbac_sod_violations_table = rbac_sod_violations
rbac_separation_of_duty_rules_table = rbac_separation_of_duty_rules
user_sessions_table = user_sessions
mfa_secrets_table = mfa_secrets
mfa_backup_codes_table = mfa_backup_codes
api_keys_table = api_keys
agent_credentials_table = agent_credentials
rbac_audit_logs_table = rbac_audit_logs
rbac_access_reviews_table = rbac_access_reviews
rbac_access_review_items_table = rbac_access_review_items
rbac_entitlement_requests_table = rbac_entitlement_requests
rbac_delegations_table = rbac_delegations
rbac_impersonation_logs_table = rbac_impersonation_logs
rbac_cache_entries_table = rbac_cache_entries
rbac_view_permissions_table = rbac_view_permissions
rbac_dashboard_permissions_table = rbac_dashboard_permissions

# Policy engine bare-name aliases
policy_rules = rbac_policy_rules
abac_conditions = rbac_abac_conditions
rebac_relations = rbac_rebac_relations


# ===========================================================================
# Base DB Fixture
# ===========================================================================

@pytest.fixture
def db():
    """Create an in-memory SQLite database with ALL RBAC tables (raw SQLAlchemy).

    For service-level tests that need SQLModel model tables, use the
    `sqlmodel_db` fixture instead.
    """
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    metadata.create_all(engine)
    with Session(engine) as raw:
        yield SQLModelSession(raw)


@pytest.fixture
def sqlmodel_db():
    """Create an in-memory SQLite DB with SQLModel model tables.

    This fixture ONLY creates SQLModel model tables (not the conftest's
    raw Table objects). Service classes that use `session.add(SQLModel())`
    need these model tables. Raw `Table` objects from conftest (like
    `roles_table`) still work because they reference the same underlying
    SQLite table name.

    Use this fixture for test classes that instantiate service classes
    which internally use SQLModel models with session.add().
    """
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})

    # Import SQLModel models so they register with SQLModel.metadata
    # and create their tables (only these, not the raw conftest tables)
    from sqlmodel import SQLModel
    import common_lib.modules.rbac.models  # noqa: F401
    import common_lib.modules.rbac.agent_apikey_models  # noqa: F401
    import common_lib.modules.rbac.session_mfa_models  # noqa: F401
    import common_lib.modules.rbac.field_security_models  # noqa: F401
    import common_lib.modules.rbac.tenant_models  # noqa: F401
    import common_lib.modules.rbac.audit.access_reviews  # noqa: F401
    import common_lib.modules.rbac.audit.entitlement_requests  # noqa: F401
    import common_lib.modules.rbac.delegation.models  # noqa: F401
    import common_lib.modules.rbac.roles.models  # noqa: F401
    import common_lib.modules.rbac.policies.models  # noqa: F401
    # Import model classes directly — avoids triggering service-level module init
    # which may have external dependencies (DB connections, configs, etc.)
    from common_lib.modules.rbac.organization_policy_service import OrgPolicy, OrgRoleOverride
    from common_lib.modules.rbac.view_permission_service import ViewPermission, ViewACL
    from common_lib.modules.rbac.dashboard_permission_service import DashboardPermission
    # Create only tables with simple names (no schema-qualified names like governance.*)
    # SQLite doesn't support schemas, so dot-notation tables would cause:
    #   OperationalError: unknown database governance
    for name, table in list(SQLModel.metadata.tables.items()):
        if '.' not in name:
            try:
                table.create(engine, checkfirst=True)
            except Exception:
                pass

    with Session(engine) as raw:
        yield SQLModelSession(raw)


# ===========================================================================
# Seed Helpers
# ===========================================================================

def seed_role(db, role_id: int, role_name: str, description: str = ""):
    """Seed a single role."""
    db.execute(roles.insert().values(id=role_id, name=role_name, description=description, created_at=datetime.utcnow(), updated_at=datetime.utcnow()))
    db.commit()


def seed_roles(db, *role_tuples):
    """Seed multiple roles. Each tuple: (id, name[, description])."""
    for entry in role_tuples:
        rid, name = entry[0], entry[1]
        desc = entry[2] if len(entry) > 2 else ""
        seed_role(db, rid, name, desc)


def seed_user_role(db, user_id: int, role_id: int, is_active: bool = True):
    """Seed a single user-role assignment."""
    db.execute(user_roles.insert().values(user_id=user_id, role_id=role_id, is_active=is_active, granted_at=datetime.utcnow()))
    db.commit()


def seed_user_roles(db, assignments):
    """Seed multiple user-role assignments. assignments = [(user_id, role_id)]."""
    for uid, rid in assignments:
        seed_user_role(db, uid, rid)


def seed_permission(db, perm_id: int, name: str, resource: str = "", action: str = ""):
    """Seed a single permission."""
    db.execute(permissions.insert().values(id=perm_id, name=name, resource=resource, action=action, scope="global", created_at=datetime.utcnow(), updated_at=datetime.utcnow()))
    db.commit()


def seed_permissions(db, *perm_tuples):
    """Seed multiple permissions. Each tuple: (id, name[, resource, action])."""
    for entry in perm_tuples:
        pid, name = entry[0], entry[1]
        resource = entry[2] if len(entry) > 2 else name.split(":")[0] if ":" in name else name
        action = entry[3] if len(entry) > 3 else name.split(":")[1] if ":" in name else "read"
        seed_permission(db, pid, name, resource, action)


def seed_role_permission(db, role_id: int, permission_id: int):
    """Seed a role-permission assignment."""
    db.execute(role_permissions.insert().values(role_id=role_id, permission_id=permission_id))
    db.commit()


def seed_role_permissions(db, role_perm_pairs):
    """Seed multiple role-permission pairs. Each pair: (role_id, permission_id)."""
    for rid, pid in role_perm_pairs:
        seed_role_permission(db, rid, pid)


def seed_inheritance(db, parent_id: int, child_id: int):
    """Seed a role inheritance edge."""
    db.execute(role_inheritance.insert().values(parent_role_id=parent_id, child_role_id=child_id, created_at=datetime.utcnow()))
    db.commit()
