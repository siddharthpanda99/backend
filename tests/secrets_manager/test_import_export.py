"""Tests for Import/Export service (SSOT §27)."""

import json
import pytest
from sqlmodel import Session, create_engine, SQLModel
from common_lib.modules.secrets_manager.import_export.service import ImportExportService
from common_lib.modules.secrets_manager.vault.models import Secret


@pytest.fixture
def session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    sm_tables = [t for n, t in SQLModel.metadata.tables.items() if n.startswith("sm_")]
    SQLModel.metadata.create_all(engine, tables=sm_tables)
    s = Session(engine)
    yield s
    s.close()


class TestExport:
    def test_export_secrets_empty(self, session):
        svc = ImportExportService(session)
        exported = svc.export_secrets_to_json()
        data = json.loads(exported)
        assert "exported_at" in data
        assert "secrets" in data

    def test_export_policies_empty(self, session):
        svc = ImportExportService(session)
        exported = svc.export_policies_to_json()
        data = json.loads(exported)
        assert "policies" in data

    def test_export_audit_log(self, session):
        svc = ImportExportService(session)
        exported = svc.export_audit_log(since_hours=168)
        data = json.loads(exported)
        assert "entries" in data
        assert data["since_hours"] == 168


class TestImport:
    def test_import_from_json_empty(self, session):
        svc = ImportExportService(session)
        result = svc.import_from_json('{"secrets": [], "policies": []}')
        assert result["secrets_imported"] == 0
        assert result["policies_imported"] == 0

    def test_import_secrets(self, session):
        svc = ImportExportService(session)
        data = json.dumps({
            "secrets": [{"path": "/test/secret1"}, {"path": "/test/secret2"}],
            "policies": [{"name": "test-policy", "path": "test/*", "capabilities": ["read"]}],
        })
        result = svc.import_from_json(data)
        assert result["secrets_imported"] == 2
        assert result["policies_imported"] == 1
