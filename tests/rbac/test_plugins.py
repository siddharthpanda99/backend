"""Tests for RBAC Plugin Dynamic Permission Discovery (SSOT 31).

Verifies DynamicPermissionDiscoveryService for runtime permission
registration, auto-discovery, and manifest tracking.
"""


from tests.rbac.conftest import permissions, roles, user_roles, role_permissions, role_inheritance

import pytest
from datetime import datetime
from sqlalchemy import create_engine, MetaData, Table, Column, String, Integer, DateTime, Boolean
from sqlalchemy.orm import Session as RawSession, Session

class TestDynamicPermissionDiscoveryService:
    """Test DynamicPermissionDiscoveryService: registration, discovery, coverage."""

    def test_register_new_permissions(self, db):
        from common_lib.modules.rbac.plugins.service import DynamicPermissionDiscoveryService
        svc = DynamicPermissionDiscoveryService(db)
        perms = [
            {"name": "project:read", "resource": "project", "action": "read", "description": "Read projects"},
            {"name": "project:write", "resource": "project", "action": "write", "description": "Write projects"},
        ]
        count = svc.register_plugin_permissions("test_plugin", "1.0", perms)
        assert count == 2

    def test_register_duplicate_skipped(self, db):
        from common_lib.modules.rbac.plugins.service import DynamicPermissionDiscoveryService
        svc = DynamicPermissionDiscoveryService(db)
        perms = [{"name": "project:read", "resource": "project", "action": "read", "description": ""}]
        svc.register_plugin_permissions("p1", "1.0", perms)
        count = svc.register_plugin_permissions("p2", "1.0", perms)
        assert count == 0  # Duplicate, skipped

    def test_register_multiple_plugins(self, db):
        from common_lib.modules.rbac.plugins.service import DynamicPermissionDiscoveryService
        svc = DynamicPermissionDiscoveryService(db)
        svc.register_plugin_permissions("pm", "1.0", [
            {"name": "issue:create", "resource": "issue", "action": "create", "description": ""},
        ])
        svc.register_plugin_permissions("auth", "2.0", [
            {"name": "user:read", "resource": "user", "action": "read", "description": ""},
        ])
        plugins = svc.list_registered_plugins()
        assert "pm" in plugins
        assert "auth" in plugins

    def test_get_permission_coverage(self, db):
        from common_lib.modules.rbac.plugins.service import DynamicPermissionDiscoveryService
        svc = DynamicPermissionDiscoveryService(db)
        perms = [{"name": f"res:{i}", "resource": "res", "action": str(i), "description": ""} for i in range(5)]
        svc.register_plugin_permissions("p1", "1.0", perms)
        coverage = svc.get_permission_coverage()
        assert coverage["plugin_count"] == 1
        assert coverage["total_in_db"] == 5

    def test_discover_module_permissions(self, db):
        from common_lib.modules.rbac.plugins.service import DynamicPermissionDiscoveryService
        svc = DynamicPermissionDiscoveryService(db)
        discovered = svc.discover_module_permissions(
            "common_lib.modules.rbac.policies.service",
            plugin_name="rbac_policies",
        )
        assert isinstance(discovered, list)

    def test_get_plugin_manifest(self, db):
        from common_lib.modules.rbac.plugins.service import DynamicPermissionDiscoveryService
        svc = DynamicPermissionDiscoveryService(db)
        perms = [{"name": "test:read", "resource": "test", "action": "read", "description": "test"}]
        svc.register_plugin_permissions("p1", "1.0", perms)
        manifest = svc.get_plugin_manifest("p1")
        assert manifest is not None
        assert manifest.plugin_name == "p1"
        assert manifest.plugin_version == "1.0"

    def test_sync_discovered_to_db(self, db):
        from common_lib.modules.rbac.plugins.service import DynamicPermissionDiscoveryService
        svc = DynamicPermissionDiscoveryService(db)
        result = svc.sync_discovered_to_db([
            "common_lib.modules.rbac.policies.service",
        ])
        assert result["discovered"] >= 0
        assert result["registered"] >= 0
