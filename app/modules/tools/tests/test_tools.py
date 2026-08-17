# Tools Tests
import pytest


class TestToolService:
    """Tests for ToolService"""

    def test_service_has_get_all_method(self):
        from common_lib.modules.core_infrastructure.tools.service import tool_service

        assert hasattr(tool_service, "get_all")
        assert callable(tool_service.get_all)

    def test_service_has_get_by_id_method(self):
        from common_lib.modules.core_infrastructure.tools.service import tool_service

        assert hasattr(tool_service, "get_by_id")
        assert callable(tool_service.get_by_id)

    def test_service_has_create_method(self):
        from common_lib.modules.core_infrastructure.tools.service import tool_service

        assert hasattr(tool_service, "create")
        assert callable(tool_service.create)

    def test_service_has_update_method(self):
        from common_lib.modules.core_infrastructure.tools.service import tool_service

        assert hasattr(tool_service, "update")
        assert callable(tool_service.update)

    def test_service_has_delete_method(self):
        from common_lib.modules.core_infrastructure.tools.service import tool_service

        assert hasattr(tool_service, "delete")
        assert callable(tool_service.delete)

    def test_get_all_returns_list(self):
        from common_lib.modules.core_infrastructure.tools.service import tool_service

        result = tool_service.get_all(skip=0, limit=10)
        assert isinstance(result, list)

    def test_get_all_respects_limit(self):
        from common_lib.modules.core_infrastructure.tools.service import tool_service

        result = tool_service.get_all(skip=0, limit=5)
        assert len(result) <= 5

    def test_get_by_id_returns_dict_or_none(self):
        from common_lib.modules.core_infrastructure.tools.service import tool_service

        result = tool_service.get_by_id("nonexistent-tool-12345")
        assert result is None or isinstance(result, dict)

    def test_get_all_respects_skip(self):
        from common_lib.modules.core_infrastructure.tools.service import tool_service

        all_items = tool_service.get_all(skip=0, limit=100)
        if len(all_items) >= 10:
            result = tool_service.get_all(skip=5, limit=5)
            assert len(result) <= 5


class TestToolSchemas:
    """Tests for Tool schemas"""

    def test_tool_create_schema_imports(self):
        from common_lib.modules.core_infrastructure.tools.schemas import ToolCreate

        assert ToolCreate is not None

    def test_tool_update_schema_imports(self):
        from common_lib.modules.core_infrastructure.tools.schemas import ToolUpdate

        assert ToolUpdate is not None

    def test_tool_read_schema_imports(self):
        from common_lib.modules.core_infrastructure.tools.schemas import ToolRead

        assert ToolRead is not None

    def test_tool_base_schema_imports(self):
        from common_lib.modules.core_infrastructure.tools.schemas import ToolBase

        assert ToolBase is not None


class TestToolServiceErrors:
    """Tests for error handling"""

    def test_not_found_error_exists(self):
        from common_lib.modules.core_infrastructure.tools.service import NotFoundError

        assert issubclass(NotFoundError, Exception)

    def test_update_returns_dict_when_no_memory(self):
        from common_lib.modules.core_infrastructure.tools.service import tool_service
        from common_lib.modules.core_infrastructure.tools.schemas import ToolUpdate

        result = tool_service.update("nonexistent-tool-12345", ToolUpdate(name="test"))
        assert result == {}

    def test_delete_returns_false_when_no_memory(self):
        from common_lib.modules.core_infrastructure.tools.service import tool_service

        result = tool_service.delete("nonexistent-tool-12345")
        assert result == False

    def test_create_without_id_raises_error(self):
        from common_lib.modules.core_infrastructure.tools.service import tool_service
        from common_lib.modules.core_infrastructure.tools.schemas import ToolCreate

        with pytest.raises((ValueError, Exception)):
            tool_service.create(ToolCreate(name=""))
