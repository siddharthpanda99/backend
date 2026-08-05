"""
Field Security Integration Tests -- Real DB, real models, real service logic.

Tests the complete field security pipeline:
- FieldSecurityRule CRUD in DB
- FieldSecurityOverride CRUD in DB
- FieldSecurityService.get_field_access() resolution logic
- filter_single_response / filter_list_response helper functions
- check_field_editable / reject_if_field_read_only
- strip_field_security_metadata
- _get_user_id / _get_user_roles

NOTE: We use an isolated SQLAlchemy MetaData (not SQLModel.metadata) because
SQLModel shares a single global metadata across ALL models. Importing any
SQLModel subclass (even field_security_models) triggers registration of every
platform model (governance, analytics, etc.) which fail on SQLite.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from sqlalchemy import MetaData, Table, Column, String, Boolean, DateTime, Integer, JSON
from sqlalchemy import create_engine as sa_create_engine
from sqlmodel import Session
from fastapi import HTTPException, Request

from common_lib.modules.rbac.field_security_service import FieldSecurityService
from common_lib.modules.rbac.field_security_models import FieldAccessLevel


# ---------------------------------------------------------------------------
# Isolated metadata -- only the 2 field security tables.
# ---------------------------------------------------------------------------

_test_meta = MetaData()

_table_rules = Table(
    "field_security_rules",
    _test_meta,
    Column("id", String, primary_key=True),
    Column("workspace_id", String, nullable=True),
    Column("project_id", String, nullable=True),
    Column("resource_type", String, nullable=False),
    Column("field_key", String, nullable=False),
    Column("role_name", String, nullable=False),
    Column("access_level", String, default="editable"),
    Column("conditions", JSON, default={}),
    Column("is_active", Boolean, default=True),
    Column("created_by", String, nullable=True),
    Column("created_at", DateTime, nullable=True),
    Column("updated_at", DateTime, nullable=True),
)

_table_overrides = Table(
    "field_security_overrides",
    _test_meta,
    Column("id", String, primary_key=True),
    Column("rule_id", String, nullable=True),
    Column("user_id", Integer, nullable=False),
    Column("resource_type", String, nullable=False),
    Column("field_key", String, nullable=False),
    Column("access_level", String, default="editable"),
    Column("is_active", Boolean, default=True),
    Column("expires_at", DateTime, nullable=True),
    Column("granted_by", Integer, nullable=True),
    Column("reason", String, nullable=True),
    Column("created_at", DateTime, nullable=True),
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(name="engine")
def engine_fixture():
    engine = sa_create_engine("sqlite://", connect_args={"check_same_thread": False})
    _test_meta.create_all(engine)
    yield engine
    _test_meta.drop_all(engine)


@pytest.fixture(name="session")
def session_fixture(engine):
    with Session(engine) as session:
        yield session


@pytest.fixture(name="svc")
def svc_fixture(session):
    return FieldSecurityService(session)


@pytest.fixture(name="mock_request")
def mock_request_fixture():
    """Create a mock Request with identity.state."""
    request = MagicMock(spec=Request)
    request.state = MagicMock()
    request.state.identity = MagicMock()
    request.state.identity.subject_id = 100
    request.state.identity.roles = ["contributor"]
    request.headers = {}
    return request


@pytest.fixture(name="no_auth_request")
def no_auth_request_fixture():
    """Create a mock Request with no identity (unauthenticated)."""
    request = MagicMock(spec=Request)
    request.state = MagicMock()
    request.state.identity = None
    request.headers = {}
    return request


@pytest.fixture(name="mock_permission_resolver")
def mock_permission_resolver_fixture():
    """Mock PermissionResolver so get_field_access resolves user roles without a real RBAC DB.

    Returns a context-manager factory: call mock_permission_resolver(roles=[...])
    to set which roles the mock resolver will return.
    """
    def _factory(roles=None):
        if roles is None:
            roles = ["contributor"]
        mock_resolver = MagicMock()
        mock_resolver.resolve_user_permissions.return_value = [
            MagicMock(role_name=r) for r in roles
        ]
        return patch(
            "common_lib.modules.rbac.field_security_service.PermissionResolver",
            return_value=mock_resolver,
        )
    return _factory


# ---------------------------------------------------------------------------
# Test: FieldSecurityRule CRUD
# ---------------------------------------------------------------------------

class TestFieldSecurityRuleCRUD:
    def test_create_rule(self, svc, session):
        rule = svc.create_rule({
            "resource_type": "issue",
            "field_key": "cost_estimate",
            "role_name": "contributor",
            "access_level": "hidden",
            "workspace_id": "ws-1",
        })
        assert rule.id is not None
        assert rule.resource_type == "issue"
        assert rule.field_key == "cost_estimate"
        assert rule.access_level == "hidden"
        assert rule.is_active is True

    def test_list_rules_filters_by_role(self, svc, session):
        svc.create_rule({"resource_type": "issue", "field_key": "budget", "role_name": "viewer", "access_level": "hidden"})
        svc.create_rule({"resource_type": "issue", "field_key": "budget", "role_name": "pm", "access_level": "read_only"})
        viewer_rules = svc.list_rules(role_name="viewer")
        assert len(viewer_rules) == 1
        assert viewer_rules[0].role_name == "viewer"

    def test_delete_rule(self, svc, session):
        rule = svc.create_rule({"resource_type": "issue", "field_key": "x", "role_name": "r", "access_level": "hidden"})
        assert svc.delete_rule(rule.id) is True
        assert svc.get_rule(rule.id) is None

    def test_delete_nonexistent_rule(self, svc):
        assert svc.delete_rule("nonexistent") is False

    def test_update_rule(self, svc, session):
        rule = svc.create_rule({"resource_type": "issue", "field_key": "x", "role_name": "r", "access_level": "hidden"})
        updated = svc.update_rule(rule.id, {"access_level": "read_only"})
        assert updated.access_level == "read_only"

    def test_list_rules_inactive_excluded(self, svc, session):
        rule = svc.create_rule({"resource_type": "issue", "field_key": "x", "role_name": "r", "access_level": "hidden"})
        rule.is_active = False
        session.add(rule)
        session.commit()
        assert len(svc.list_rules()) == 0


# ---------------------------------------------------------------------------
# Test: FieldSecurityOverride CRUD
# ---------------------------------------------------------------------------

class TestFieldSecurityOverrideCRUD:
    def test_create_override(self, svc):
        ov = svc.create_override({
            "user_id": 42,
            "resource_type": "issue",
            "field_key": "cost_estimate",
            "access_level": "editable",
        })
        assert ov.id is not None
        assert ov.user_id == 42

    def test_list_overrides_for_user(self, svc):
        svc.create_override({"user_id": 42, "resource_type": "issue", "field_key": "a", "access_level": "editable"})
        svc.create_override({"user_id": 99, "resource_type": "issue", "field_key": "b", "access_level": "hidden"})
        ovs = svc.list_overrides_for_user(42)
        assert len(ovs) == 1
        assert ovs[0].user_id == 42

    def test_delete_override(self, svc):
        ov = svc.create_override({"user_id": 42, "resource_type": "issue", "field_key": "x", "access_level": "editable"})
        assert svc.delete_override(ov.id) is True

    def test_list_overrides_inactive_excluded(self, svc, session):
        ov = svc.create_override({"user_id": 42, "resource_type": "issue", "field_key": "x", "access_level": "editable"})
        ov.is_active = False
        session.add(ov)
        session.commit()
        assert len(svc.list_overrides_for_user(42)) == 0


# ---------------------------------------------------------------------------
# Test: Field Access Resolution Logic
# ---------------------------------------------------------------------------

class TestFieldAccessResolution:
    def test_default_editable(self, svc):
        """No rules -> field is editable."""
        level = svc.get_field_access(user_id=1, resource_type="issue", field_key="story_points")
        assert level == "editable"

    def test_hidden_rule(self, svc):
        """Rule says hidden -> field is hidden."""
        svc.create_rule({"resource_type": "issue", "field_key": "cost_estimate", "role_name": "contributor", "access_level": "hidden"})
        level = svc.get_field_access(user_id=1, resource_type="issue", field_key="cost_estimate", user_roles=["contributor"])
        assert level == "hidden"

    def test_read_only_rule(self, svc):
        """Rule says read_only -> field is read_only."""
        svc.create_rule({"resource_type": "issue", "field_key": "priority", "role_name": "viewer", "access_level": "read_only"})
        level = svc.get_field_access(user_id=1, resource_type="issue", field_key="priority", user_roles=["viewer"])
        assert level == "read_only"

    def test_user_override_takes_precedence(self, svc):
        """User override overrides role rule."""
        svc.create_rule({"resource_type": "issue", "field_key": "cost_estimate", "role_name": "contributor", "access_level": "hidden"})
        svc.create_override({"user_id": 42, "resource_type": "issue", "field_key": "cost_estimate", "access_level": "editable"})
        level = svc.get_field_access(user_id=42, resource_type="issue", field_key="cost_estimate", user_roles=["contributor"])
        assert level == "editable"

    def test_expired_override_ignored(self, svc):
        """Expired override is ignored, role rule applies."""
        svc.create_rule({"resource_type": "issue", "field_key": "cost_estimate", "role_name": "contributor", "access_level": "hidden"})
        svc.create_override({
            "user_id": 42, "resource_type": "issue", "field_key": "cost_estimate",
            "access_level": "editable", "expires_at": datetime.utcnow() - timedelta(days=1),
        })
        level = svc.get_field_access(user_id=42, resource_type="issue", field_key="cost_estimate", user_roles=["contributor"])
        assert level == "hidden"

    def test_project_rule_over_workspace(self, svc):
        """Project-specific rule takes priority over workspace-wide."""
        svc.create_rule({"resource_type": "issue", "field_key": "budget", "role_name": "pm", "access_level": "read_only", "workspace_id": "ws-1"})
        svc.create_rule({"resource_type": "issue", "field_key": "budget", "role_name": "pm", "access_level": "hidden", "project_id": "proj-1"})
        level = svc.get_field_access(
            user_id=1, resource_type="issue", field_key="budget",
            workspace_id="ws-1", project_id="proj-1", user_roles=["pm"],
        )
        assert level == "hidden"

    def test_wrong_role_not_affected(self, svc):
        """Rule for viewer does not affect contributor."""
        svc.create_rule({"resource_type": "issue", "field_key": "cost_estimate", "role_name": "viewer", "access_level": "hidden"})
        level = svc.get_field_access(user_id=1, resource_type="issue", field_key="cost_estimate", user_roles=["contributor"])
        assert level == "editable"

    def test_filter_visible_fields(self, svc, mock_permission_resolver):
        """filter_visible_fields removes hidden fields and marks read_only."""
        svc.create_rule({"resource_type": "issue", "field_key": "cost_estimate", "role_name": "pm", "access_level": "hidden"})
        svc.create_rule({"resource_type": "issue", "field_key": "budget", "role_name": "pm", "access_level": "read_only"})
        fields = {"cost_estimate": 1000, "budget": 5000, "title": "Test"}
        with mock_permission_resolver(["pm"]):
            result = svc.filter_visible_fields(user_id=1, resource_type="issue", fields=fields)
        assert "cost_estimate" not in result["fields"]
        assert result["fields"]["budget"] == 5000
        assert result["fields"]["title"] == "Test"
        assert "cost_estimate" in result["hidden_fields"]
        assert "budget" in result["read_only_fields"]

    def test_get_resource_fields_access_batch(self, svc, mock_permission_resolver):
        """get_resource_fields_access returns map for multiple fields."""
        svc.create_rule({"resource_type": "issue", "field_key": "a", "role_name": "r", "access_level": "hidden"})
        svc.create_rule({"resource_type": "issue", "field_key": "b", "role_name": "r", "access_level": "read_only"})
        with mock_permission_resolver(["r"]):
            result = svc.get_resource_fields_access(user_id=1, resource_type="issue", field_keys=["a", "b", "c"])
        assert result["a"] == "hidden"
        assert result["b"] == "read_only"
        assert result["c"] == "editable"


# ---------------------------------------------------------------------------
# Test: filter_single_response
# ---------------------------------------------------------------------------

class TestFilterSingleResponse:
    def test_no_auth_passthrough(self, no_auth_request, session):
        from app.modules.project_management.field_security_deps import filter_single_response
        data = {"id": "1", "title": "T", "cost_estimate": 100}
        result = filter_single_response(no_auth_request, session, "issue", data)
        assert result == data  # Unauthenticated -> passthrough

    def test_hidden_fields_stripped(self, mock_request, session, mock_permission_resolver):
        from app.modules.project_management.field_security_deps import filter_single_response
        svc = FieldSecurityService(session)
        svc.create_rule({"resource_type": "issue", "field_key": "cost_estimate", "role_name": "contributor", "access_level": "hidden"})
        data = {"id": "1", "title": "T", "cost_estimate": 100, "budget": 500}
        with mock_permission_resolver(["contributor"]):
            result = filter_single_response(mock_request, session, "issue", data, project_id=None)
        assert "cost_estimate" not in result
        assert result["budget"] == 500
        assert "_field_security" in result
        assert "cost_estimate" in result["_field_security"]["hidden_fields"]

    def test_immutable_fields_preserved(self, mock_request, session, mock_permission_resolver):
        from app.modules.project_management.field_security_deps import filter_single_response
        svc = FieldSecurityService(session)
        svc.create_rule({"resource_type": "issue", "field_key": "id", "role_name": "contributor", "access_level": "hidden"})
        data = {"id": "1", "key": "ISS-1", "project_id": "p1", "title": "T"}
        with mock_permission_resolver(["contributor"]):
            result = filter_single_response(mock_request, session, "issue", data)
        # Immutable fields are never filtered
        assert result["id"] == "1"
        assert result["key"] == "ISS-1"
        assert result["project_id"] == "p1"

    def test_read_only_fields_marked_in_metadata(self, mock_request, session, mock_permission_resolver):
        from app.modules.project_management.field_security_deps import filter_single_response
        svc = FieldSecurityService(session)
        svc.create_rule({"resource_type": "issue", "field_key": "priority", "role_name": "contributor", "access_level": "read_only"})
        data = {"id": "1", "priority": "high"}
        with mock_permission_resolver(["contributor"]):
            result = filter_single_response(mock_request, session, "issue", data)
        assert result["priority"] == "high"  # Visible but marked read-only
        assert "priority" in result["_field_security"]["read_only_fields"]


# ---------------------------------------------------------------------------
# Test: filter_list_response
# ---------------------------------------------------------------------------

class TestFilterListResponse:
    def test_no_auth_passthrough(self, no_auth_request, session):
        from app.modules.project_management.field_security_deps import filter_list_response
        items = [{"id": "1", "cost_estimate": 100}, {"id": "2", "cost_estimate": 200}]
        result = filter_list_response(no_auth_request, session, "issue", items)
        assert len(result) == 2
        assert result[0]["cost_estimate"] == 100

    def test_hidden_fields_stripped_from_all(self, mock_request, session, mock_permission_resolver):
        from app.modules.project_management.field_security_deps import filter_list_response
        svc = FieldSecurityService(session)
        svc.create_rule({"resource_type": "issue", "field_key": "cost_estimate", "role_name": "contributor", "access_level": "hidden"})
        items = [
            {"id": "1", "title": "A", "cost_estimate": 100},
            {"id": "2", "title": "B", "cost_estimate": 200},
        ]
        with mock_permission_resolver(["contributor"]):
            result = filter_list_response(mock_request, session, "issue", items)
        assert len(result) == 2
        for item in result:
            assert "cost_estimate" not in item
            assert "title" in item


# ---------------------------------------------------------------------------
# Test: check_field_editable / reject_if_field_read_only
# ---------------------------------------------------------------------------

class TestCheckFieldEditable:
    def test_no_auth_returns_true(self, no_auth_request, session):
        from app.modules.project_management.field_security_deps import check_field_editable
        assert check_field_editable(no_auth_request, session, "issue", "cost_estimate") is True

    def test_editable_returns_true(self, mock_request, session):
        from app.modules.project_management.field_security_deps import check_field_editable
        # No rules -> default editable (PermissionResolver fails gracefully)
        assert check_field_editable(mock_request, session, "issue", "cost_estimate") is True

    def test_hidden_returns_false(self, mock_request, session, mock_permission_resolver):
        from app.modules.project_management.field_security_deps import check_field_editable
        svc = FieldSecurityService(session)
        svc.create_rule({"resource_type": "issue", "field_key": "cost_estimate", "role_name": "contributor", "access_level": "hidden"})
        with mock_permission_resolver(["contributor"]):
            assert check_field_editable(mock_request, session, "issue", "cost_estimate") is False

    def test_read_only_returns_false(self, mock_request, session, mock_permission_resolver):
        from app.modules.project_management.field_security_deps import check_field_editable
        svc = FieldSecurityService(session)
        svc.create_rule({"resource_type": "issue", "field_key": "priority", "role_name": "contributor", "access_level": "read_only"})
        with mock_permission_resolver(["contributor"]):
            assert check_field_editable(mock_request, session, "issue", "priority") is False


class TestRejectIfFieldReadOnly:
    def test_no_exception_when_editable(self, mock_request, session):
        from app.modules.project_management.field_security_deps import reject_if_field_read_only
        # No rules -> editable -> no exception
        reject_if_field_read_only(mock_request, session, "issue", "cost_estimate")

    def test_raises_403_when_hidden(self, mock_request, session, mock_permission_resolver):
        from app.modules.project_management.field_security_deps import reject_if_field_read_only
        svc = FieldSecurityService(session)
        svc.create_rule({"resource_type": "issue", "field_key": "cost_estimate", "role_name": "contributor", "access_level": "hidden"})
        with mock_permission_resolver(["contributor"]):
            with pytest.raises(HTTPException) as exc_info:
                reject_if_field_read_only(mock_request, session, "issue", "cost_estimate")
        assert exc_info.value.status_code == 403

    def test_raises_403_when_read_only(self, mock_request, session, mock_permission_resolver):
        from app.modules.project_management.field_security_deps import reject_if_field_read_only
        svc = FieldSecurityService(session)
        svc.create_rule({"resource_type": "issue", "field_key": "priority", "role_name": "contributor", "access_level": "read_only"})
        with mock_permission_resolver(["contributor"]):
            with pytest.raises(HTTPException) as exc_info:
                reject_if_field_read_only(mock_request, session, "issue", "priority")
        assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# Test: strip_field_security_metadata
# ---------------------------------------------------------------------------

class TestStripFieldSecurityMetadata:
    def test_removes_metadata(self):
        from app.modules.project_management.field_security_deps import strip_field_security_metadata
        data = {"id": "1", "title": "T", "_field_security": {"hidden_fields": ["x"]}}
        result = strip_field_security_metadata(data)
        assert "_field_security" not in result
        assert result["id"] == "1"

    def test_preserves_all_other_keys(self):
        from app.modules.project_management.field_security_deps import strip_field_security_metadata
        data = {"a": 1, "b": 2, "c": 3}
        result = strip_field_security_metadata(data)
        assert result == {"a": 1, "b": 2, "c": 3}

    def test_no_metadata_key(self):
        from app.modules.project_management.field_security_deps import strip_field_security_metadata
        data = {"id": "1"}
        result = strip_field_security_metadata(data)
        assert result == {"id": "1"}


# ---------------------------------------------------------------------------
# Test: _get_user_id / _get_user_roles
# ---------------------------------------------------------------------------

class TestHelperFunctions:
    def test_get_user_id_from_identity(self, mock_request):
        from app.modules.project_management.field_security_deps import _get_user_id
        assert _get_user_id(mock_request) == 100

    def test_get_user_id_no_identity(self, no_auth_request):
        from app.modules.project_management.field_security_deps import _get_user_id
        assert _get_user_id(no_auth_request) is None

    def test_get_user_roles_from_identity(self, mock_request):
        from app.modules.project_management.field_security_deps import _get_user_roles
        roles = _get_user_roles(mock_request)
        assert "contributor" in roles

    def test_get_user_roles_no_identity(self, no_auth_request):
        from app.modules.project_management.field_security_deps import _get_user_roles
        assert _get_user_roles(no_auth_request) == []
