# Sync Module Tests
import pytest


class TestSyncRouter:
    """Tests for Sync router"""

    def test_sync_router_imports(self):
        from app.modules.sync.routes.index import router

        assert router is not None


class TestSyncReport:
    """Tests for SyncReport model"""

    def test_sync_report_has_required_fields(self):
        from app.modules.sync.routes.index import SyncReport

        report = SyncReport(
            files_imported=5,
            files_exported=3,
            entities_created=10,
            entities_processed=8,
        )
        assert report.files_imported == 5
        assert report.files_exported == 3
        assert report.entities_created == 10
        assert report.entities_processed == 8

    def test_sync_report_has_optional_fields(self):
        from app.modules.sync.routes.index import SyncReport

        report = SyncReport(
            files_imported=1, imported_ids=["id1", "id2"], errors=["error1"]
        )
        assert report.imported_ids == ["id1", "id2"]
        assert report.errors == ["error1"]


class TestSyncService:
    """Tests for sync service functions"""

    def test_sync_entities_function_imports(self):
        from app.modules.sync.routes.index import sync_entities

        assert callable(sync_entities)

    def test_sync_files_function_imports(self):
        from app.modules.sync.routes.index import sync_files

        assert callable(sync_files)

    def test_get_sync_status_function_imports(self):
        from app.modules.sync.routes.index import get_sync_status

        assert callable(get_sync_status)


class TestSyncOperations:
    """Tests for sync operations"""

    def test_get_entity_types_function_imports(self):
        from app.modules.sync.routes.index import get_entity_types

        assert callable(get_entity_types)

    def test_sync_by_type_function_imports(self):
        from app.modules.sync.routes.index import sync_by_type

        assert callable(sync_by_type)

    def test_list_synced_entities_function_imports(self):
        from app.modules.sync.routes.index import list_synced_entities

        assert callable(list_synced_entities)

    def test_get_entity_sync_status_function_imports(self):
        from app.modules.sync.routes.index import get_entity_sync_status

        assert callable(get_entity_sync_status)


class TestSyncRoutes:
    """Tests for sync routes exist"""

    def test_sync_endpoint_exists(self):
        from app.modules.sync.routes.index import router

        routes = [r.path for r in router.routes]
        assert len(routes) > 0


class TestSyncUtilities:
    """Tests for sync utilities"""

    def test_format_sync_report_imports(self):
        from app.modules.sync.routes.index import format_sync_report

        assert callable(format_sync_report)

    def test_validate_sync_config_imports(self):
        from app.modules.sync.routes.index import validate_sync_config

        assert callable(validate_sync_config)
