"""Tests for RBAC Ownership Submodule (SSOT 09).

Verifies OwnershipService re-export + new @node wrappers work correctly.
Uses raw SQLAlchemy sessions with SQLModelSession wrapper.
"""


from tests.rbac.conftest import resource_ownership

import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine, MetaData, Table, Column, String, Integer, DateTime, Text
from sqlalchemy.orm import Session as RawSession

class TestOwnershipReExport:
    """Verify OwnershipService works when imported from the submodule."""

    def test_import_from_submodule(self):
        from common_lib.modules.rbac.ownership import OwnershipService as Sub
        from common_lib.modules.rbac.ownership_service import OwnershipService as Orig
        assert Sub is Orig

    def test_register_and_get(self, db):
        from common_lib.modules.rbac.ownership import OwnershipService
        svc = OwnershipService(db)
        result = svc.register(
            resource_type="project", resource_id="proj-1",
            owner_user_id=100,
        )
        assert result.resource_type == "project"
        assert result.resource_id == "proj-1"
        assert result.owner_user_id == 100

    def test_is_owner(self, db):
        from common_lib.modules.rbac.ownership import OwnershipService
        svc = OwnershipService(db)
        svc.register(resource_type="issue", resource_id="iss-1", owner_user_id=200)
        assert svc.is_owner("issue", "iss-1", owner_user_id=200) is True
        assert svc.is_owner("issue", "iss-1", owner_user_id=999) is False

    def test_transfer(self, db):
        from common_lib.modules.rbac.ownership import OwnershipService
        svc = OwnershipService(db)
        svc.register(resource_type="doc", resource_id="doc-1", owner_user_id=300)
        result = svc.transfer("doc", "doc-1", new_owner_user_id=400)
        assert result is not None
        assert result.owner_user_id == 400
        assert result.transferred_at is not None

    def test_list_by_owner(self, db):
        from common_lib.modules.rbac.ownership import OwnershipService
        svc = OwnershipService(db)
        svc.register(resource_type="project", resource_id="p1", owner_user_id=500)
        svc.register(resource_type="project", resource_id="p2", owner_user_id=500)
        svc.register(resource_type="issue", resource_id="i1", owner_user_id=500)
        results = svc.list_by_owner(owner_user_id=500, resource_type="project")
        assert len(results) == 2
        all_results = svc.list_by_owner(owner_user_id=500)
        assert len(all_results) == 3

    def test_delete(self, db):
        from common_lib.modules.rbac.ownership import OwnershipService
        svc = OwnershipService(db)
        svc.register(resource_type="x", resource_id="x-1", owner_user_id=1)
        assert svc.delete("x", "x-1") is True
        assert svc.get_owner("x", "x-1") is None
        assert svc.delete("x", "x-1") is False
