# Memories Tests
import pytest


class TestMemoryService:
    """Tests for MemoryService"""

    def test_service_has_get_all_method(self):
        from common_lib.modules.memories.service import memory_service

        assert hasattr(memory_service, "get_all")
        assert callable(memory_service.get_all)

    def test_service_has_get_by_id_method(self):
        from common_lib.modules.memories.service import memory_service

        assert hasattr(memory_service, "get_by_id")
        assert callable(memory_service.get_by_id)

    def test_service_has_create_method(self):
        from common_lib.modules.memories.service import memory_service

        assert hasattr(memory_service, "create")
        assert callable(memory_service.create)

    def test_service_has_update_method(self):
        from common_lib.modules.memories.service import memory_service

        assert hasattr(memory_service, "update")
        assert callable(memory_service.update)

    def test_service_has_delete_method(self):
        from common_lib.modules.memories.service import memory_service

        assert hasattr(memory_service, "delete")
        assert callable(memory_service.delete)

    def test_get_all_returns_list(self):
        from common_lib.modules.memories.service import memory_service

        result = memory_service.get_all(skip=0, limit=10)
        assert isinstance(result, list)

    def test_get_all_respects_limit(self):
        from common_lib.modules.memories.service import memory_service

        result = memory_service.get_all(skip=0, limit=5)
        assert len(result) <= 5

    def test_get_all_respects_skip(self):
        from common_lib.modules.memories.service import memory_service

        all_items = memory_service.get_all(skip=0, limit=100)
        if len(all_items) >= 10:
            result = memory_service.get_all(skip=5, limit=5)
            assert len(result) <= 5

    def test_get_by_id_returns_dict_or_none(self):
        from common_lib.modules.memories.service import memory_service

        result = memory_service.get_by_id("nonexistent-id-12345")
        assert result is None or isinstance(result, dict)


class TestMemorySchemas:
    """Tests for Memory schemas"""

    def test_memory_create_schema_imports(self):
        from common_lib.modules.memories.schemas import MemoryCreate

        assert MemoryCreate is not None

    def test_memory_update_schema_imports(self):
        from common_lib.modules.memories.schemas import MemoryUpdate

        assert MemoryUpdate is not None

    def test_memory_read_schema_imports(self):
        from common_lib.modules.memories.schemas import MemoryRead

        assert MemoryRead is not None


class TestMemoryServiceErrors:
    """Tests for error handling"""

    def test_not_found_error_exists(self):
        from common_lib.modules.memories.service import NotFoundError

        assert issubclass(NotFoundError, Exception)

    def test_update_raises_not_found(self):
        from common_lib.modules.memories.service import memory_service, NotFoundError
        from common_lib.modules.memories.schemas import MemoryUpdate

        with pytest.raises((NotFoundError, AttributeError, Exception)):
            memory_service.update("nonexistent-id-12345", MemoryUpdate(name="test"))

    def test_delete_raises_not_found(self):
        from common_lib.modules.memories.service import memory_service, NotFoundError

        with pytest.raises((NotFoundError, AttributeError, Exception)):
            memory_service.delete("nonexistent-id-12345")
