"""Tests for RBAC Guest Access submodule.

Verifies GuestAccessService through the guest/ submodule and @node wrappers.
"""


from tests.rbac.conftest import roles, user_roles

import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine, MetaData, Table, Column, String, Integer, DateTime, Boolean
from sqlalchemy.orm import Session as RawSession

class TestGuestAccessSubmodule:
    """Test guest access through the guest/ submodule."""

    def test_import_from_submodule(self):
        from common_lib.modules.rbac.guest import GuestAccessService
        assert GuestAccessService is not None

    def test_grant_guest_requires_guest_role(self, db):
        from common_lib.modules.rbac.guest_access_service import GuestAccessService
        svc = GuestAccessService(db)
        with pytest.raises(ValueError, match="Guest role not found"):
            svc.grant_guest_access(user_id=50, workspace_id="ws_1")

    def test_guest_services_exist(self):
        from common_lib.modules.rbac.guest import nodes
        assert hasattr(nodes, "grant_guest_access")
        assert hasattr(nodes, "revoke_guest_access")
        assert hasattr(nodes, "list_guest_access")
        assert hasattr(nodes, "check_is_guest_user")
