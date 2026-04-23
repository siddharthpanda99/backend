# System Tests
import pytest


class TestSystemService:
    """Tests for SystemService"""

    def test_service_instance_exists(self):
        from common_lib.modules.system.service import system_service

        assert system_service is not None

    def test_service_has_get_raw_config_method(self):
        from common_lib.modules.system.service import system_service

        assert hasattr(system_service, "get_raw_config")
        assert callable(system_service.get_raw_config)

    def test_service_has_update_raw_config_method(self):
        from common_lib.modules.system.service import system_service

        assert hasattr(system_service, "update_raw_config")
        assert callable(system_service.update_raw_config)

    def test_service_has_get_structured_config_method(self):
        from common_lib.modules.system.service import system_service

        assert hasattr(system_service, "get_structured_config")
        assert callable(system_service.get_structured_config)

    def test_service_has_update_structured_config_method(self):
        from common_lib.modules.system.service import system_service

        assert hasattr(system_service, "update_structured_config")
        assert callable(system_service.update_structured_config)

    def test_service_has_get_services_method(self):
        from common_lib.modules.system.service import system_service

        assert hasattr(system_service, "get_services")
        assert callable(system_service.get_services)

    def test_service_has_toggle_service_method(self):
        from common_lib.modules.system.service import system_service

        assert hasattr(system_service, "toggle_service")
        assert callable(system_service.toggle_service)


class TestSystemServiceConfiguration:
    """Tests for System service configuration"""

    def test_service_has_repo_root(self):
        from common_lib.modules.system.service import system_service

        assert hasattr(system_service, "repo_root")

    def test_service_has_deploy_dir(self):
        from common_lib.modules.system.service import system_service

        assert hasattr(system_service, "deploy_dir")

    def test_service_has_config_path(self):
        from common_lib.modules.system.service import system_service

        assert hasattr(system_service, "config_path")

    def test_service_has_infra_manager(self):
        from common_lib.modules.system.service import system_service

        assert hasattr(system_service, "infra_manager")


class TestSystemServiceBehavior:
    """Tests for System service behavior"""

    def test_get_raw_config_returns_string(self):
        from common_lib.modules.system.service import system_service

        result = system_service.get_raw_config()
        assert isinstance(result, str)

    def test_get_structured_config_returns_dict(self):
        from common_lib.modules.system.service import system_service

        result = system_service.get_structured_config()
        assert isinstance(result, dict)

    def test_get_services_returns_list(self):
        from common_lib.modules.system.service import system_service

        result = system_service.get_services()
        assert isinstance(result, list)


class TestSystemServiceValidation:
    """Validation tests"""

    def test_update_raw_config_method_exists(self):
        from common_lib.modules.system.service import system_service

        assert hasattr(system_service, "update_raw_config")

    def test_update_structured_config_method_exists(self):
        from common_lib.modules.system.service import system_service

        assert hasattr(system_service, "update_structured_config")

    def test_toggle_service_method_exists(self):
        from common_lib.modules.system.service import system_service

        assert hasattr(system_service, "toggle_service")
