"""Tests for Secrets Manager Engines submodule (SSOT §12)."""

from __future__ import annotations

from common_lib.modules.secrets_manager.engines.service import EngineRegistryService


class TestEngineRegistryService:
    """Test secret engine provider registration and lifecycle."""

    def test_register_engine(self, db):
        svc = EngineRegistryService(session=db)
        result = svc.register_engine(
            name="postgresql",
            engine_type="database",
            mount_path="/v1/database/",
            description="PostgreSQL secret engine",
        )
        assert result["name"] == "postgresql"
        assert result["mount_path"] == "/v1/database/"

    def test_register_engine_duplicate(self, db):
        svc = EngineRegistryService(session=db)
        svc.register_engine(
            name="mysql", engine_type="database", mount_path="/v1/mysql/"
        )
        result = svc.register_engine(
            name="mysql", engine_type="database", mount_path="/v1/mysql2/"
        )
        assert "error" in result

    def test_get_engine_by_id(self, db):
        svc = EngineRegistryService(session=db)
        created = svc.register_engine(
            name="redis", engine_type="database", mount_path="/v1/redis/"
        )
        engine = svc.get_engine(engine_id=created["id"])
        assert engine is not None
        assert engine["name"] == "redis"

    def test_get_engine_by_name(self, db):
        svc = EngineRegistryService(session=db)
        svc.register_engine(
            name="mongodb", engine_type="database", mount_path="/v1/mongo/"
        )
        engine = svc.get_engine(name="mongodb")
        assert engine is not None
        assert engine["engine_type"] == "database"

    def test_get_engine_not_found(self, db):
        svc = EngineRegistryService(session=db)
        assert svc.get_engine(engine_id="nonexistent") is None
        assert svc.get_engine(name="nonexistent") is None

    def test_list_engines(self, db):
        svc = EngineRegistryService(session=db)
        svc.register_engine(name="eng-1", engine_type="database", mount_path="/v1/e1/")
        svc.register_engine(name="eng-2", engine_type="cloud", mount_path="/v1/e2/")
        engines = svc.list_engines()
        assert len(engines) >= 2

    def test_list_engines_filter_by_type(self, db):
        svc = EngineRegistryService(session=db)
        svc.register_engine(name="db-1", engine_type="database", mount_path="/v1/d1/")
        svc.register_engine(name="cloud-1", engine_type="cloud", mount_path="/v1/c1/")
        dbs = svc.list_engines(engine_type="database")
        assert len(dbs) == 1
        assert dbs[0]["name"] == "db-1"

    def test_enable_engine(self, db):
        svc = EngineRegistryService(session=db)
        created = svc.register_engine(
            name="disable-test", engine_type="database", mount_path="/v1/dt/"
        )
        svc.disable_engine(created["id"])
        assert svc.enable_engine(created["id"]) is True

    def test_disable_engine(self, db):
        svc = EngineRegistryService(session=db)
        created = svc.register_engine(
            name="disable-me", engine_type="database", mount_path="/v1/dm/"
        )
        assert svc.disable_engine(created["id"]) is True

    def test_disable_engine_not_found(self, db):
        svc = EngineRegistryService(session=db)
        assert svc.disable_engine("nonexistent") is False

    def test_remove_engine(self, db):
        svc = EngineRegistryService(session=db)
        created = svc.register_engine(
            name="remove-me", engine_type="database", mount_path="/v1/rm/"
        )
        assert svc.remove_engine(created["id"]) is True
        assert svc.get_engine(engine_id=created["id"]) is None

    def test_record_health_healthy(self, db):
        svc = EngineRegistryService(session=db)
        created = svc.register_engine(
            name="healthy-eng", engine_type="database", mount_path="/v1/he/"
        )
        result = svc.record_health(created["id"], is_healthy=True)
        assert result["is_healthy"] is True
        assert result["circuit_breaker_open"] is False

    def test_record_health_circuit_breaking(self, db):
        svc = EngineRegistryService(session=db)
        created = svc.register_engine(
            name="cb-eng", engine_type="database", mount_path="/v1/cb/"
        )
        # 3 failures opens circuit
        svc.record_health(created["id"], is_healthy=False)
        svc.record_health(created["id"], is_healthy=False)
        result = svc.record_health(created["id"], is_healthy=False)
        assert result["circuit_breaker_open"] is True
        assert result["circuit_breaker_attempts"] == 3

    def test_get_engine_health(self, db):
        svc = EngineRegistryService(session=db)
        created = svc.register_engine(
            name="health-check", engine_type="database", mount_path="/v1/hc/"
        )
        svc.record_health(created["id"], is_healthy=True, latency_ms=12.5)
        health = svc.get_engine_health(created["id"])
        assert health is not None
        assert health["is_healthy"] is True
        assert health["latency_ms"] == 12.5
