# Users Tests
import pytest


class TestUserService:
    """Tests for UserService"""

    def test_service_imports(self):
        from common_lib.modules.auth.users.service import UserService

        assert UserService is not None

    def test_service_has_get_user_by_email_method(self):
        from common_lib.modules.auth.users.service import UserService

        assert hasattr(UserService, "get_user_by_email")

    def test_service_has_create_user_method(self):
        from common_lib.modules.auth.users.service import UserService

        assert hasattr(UserService, "create_user")

    def test_service_has_update_user_method(self):
        from common_lib.modules.auth.users.service import UserService

        assert hasattr(UserService, "update_user")

    def test_service_has_delete_user_method(self):
        from common_lib.modules.auth.users.service import UserService

        assert hasattr(UserService, "delete_user")

    def test_service_has_get_user_method(self):
        from common_lib.modules.auth.users.service import UserService

        assert hasattr(UserService, "get_user")


class TestUserSchemas:
    """Tests for User schemas"""

    def test_user_create_imports(self):
        from common_lib.modules.auth.users.schemas import UserCreate

        assert UserCreate is not None

    def test_user_update_imports(self):
        from common_lib.modules.auth.users.schemas import UserUpdate

        assert UserUpdate is not None


class TestUserModels:
    """Tests for User models"""

    def test_user_model_imports(self):
        from common_lib.modules.auth.users.models import User

        assert User is not None


class TestUserServiceBehavior:
    """Tests for User service behavior"""

    def test_user_service_requires_session(self):
        from common_lib.modules.auth.users.service import UserService

        service = UserService(session=None)
        assert service.session is None
