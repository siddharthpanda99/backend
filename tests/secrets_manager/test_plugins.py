"""Tests for Plugin service (SSOT §23)."""

import pytest
from sqlmodel import Session, create_engine, SQLModel
from common_lib.modules.secrets_manager.plugins.service import PluginService
from common_lib.modules.secrets_manager.plugins.models import PluginManifest, PluginExecution


@pytest.fixture
def session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    sm_tables = [t for n, t in SQLModel.metadata.tables.items() if n.startswith("sm_")]
    SQLModel.metadata.create_all(engine, tables=sm_tables)
    s = Session(engine)
    yield s
    s.close()


class TestPlugins:
    def test_register_plugin(self, session):
        svc = PluginService(session)
        result = svc.register_plugin(name="test-engine", version="1.0.0",
                                      plugin_type="secrets_engine", binary_path="/tmp/test.so",
                                      description="Test engine")
        assert result["name"] == "test-engine"
        assert result["version"] == "1.0.0"

    def test_list_plugins(self, session):
        svc = PluginService(session)
        svc.register_plugin("engine-a", "1.0", "secrets_engine", "/tmp/a.so")
        svc.register_plugin("engine-b", "1.0", "secrets_engine", "/tmp/b.so")
        plugins = svc.list_plugins()
        assert len(plugins) >= 2

    def test_get_plugin(self, session):
        svc = PluginService(session)
        created = svc.register_plugin("test", "1.0", "secrets_engine", "/tmp/test.so")
        result = svc.get_plugin(created["id"])
        assert result["name"] == "test"

    def test_enable_disable_plugin(self, session):
        svc = PluginService(session)
        created = svc.register_plugin("test", "1.0", "secrets_engine", "/tmp/test.so")
        assert svc.disable_plugin(created["id"]) is True
        result = svc.get_plugin(created["id"])
        assert result["is_enabled"] is False
        assert svc.enable_plugin(created["id"]) is True

    def test_record_execution(self, session):
        svc = PluginService(session)
        created = svc.register_plugin("test", "1.0", "secrets_engine", "/tmp/test.so")
        exec_rec = svc.record_execution(plugin_id=created["id"], operation="handle_request",
                                         success=True, duration_ms=42)
        assert exec_rec["operation"] == "handle_request"
        assert exec_rec["success"] is True

    def test_verify_integrity_no_binary(self, session):
        svc = PluginService(session)
        created = svc.register_plugin("test", "1.0", "secrets_engine", "/tmp/nonexistent.so")
        result = svc.verify_plugin_integrity(created["id"])
        assert result["verified"] is False
