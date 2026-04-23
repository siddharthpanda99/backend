# Auth Tests
import pytest
from datetime import datetime


class TestAuthService:
    """Tests for AuthService"""

    def test_service_has_authenticate_user_method(self):
        from common_lib.modules.auth.service import auth_service

        assert hasattr(auth_service, "authenticate_user")
        assert callable(auth_service.authenticate_user)

    def test_service_has_register_user_method(self):
        from common_lib.modules.auth.service import auth_service

        assert hasattr(auth_service, "register_user")
        assert callable(auth_service.register_user)

    def test_service_has_refresh_access_token_method(self):
        from common_lib.modules.auth.service import auth_service

        assert hasattr(auth_service, "refresh_access_token")
        assert callable(auth_service.refresh_access_token)

    def test_service_has_forgot_password_method(self):
        from common_lib.modules.auth.service import auth_service

        assert hasattr(auth_service, "forgot_password")
        assert callable(auth_service.forgot_password)

    def test_service_has_reset_password_method(self):
        from common_lib.modules.auth.service import auth_service

        assert hasattr(auth_service, "reset_password")
        assert callable(auth_service.reset_password)

    def test_service_has_logout_method(self):
        from common_lib.modules.auth.service import auth_service

        assert hasattr(auth_service, "logout")
        assert callable(auth_service.logout)

    def test_service_has_change_password_method(self):
        from common_lib.modules.auth.service import auth_service

        assert hasattr(auth_service, "change_password")
        assert callable(auth_service.change_password)

    def test_service_has_verify_email_method(self):
        from common_lib.modules.auth.service import auth_service

        assert hasattr(auth_service, "verify_email")
        assert callable(auth_service.verify_email)

    def test_service_has_resend_verification_method(self):
        from common_lib.modules.auth.service import auth_service

        assert hasattr(auth_service, "resend_verification")
        assert callable(auth_service.resend_verification)

    def test_forgot_password_returns_message(self):
        from common_lib.modules.auth.service import auth_service

        result = auth_service.forgot_password("test@example.com")
        assert isinstance(result, dict)
        assert "message" in result
        assert "test@example.com" in result["message"]

    def test_reset_password_returns_message(self):
        from common_lib.modules.auth.service import auth_service

        result = auth_service.reset_password("token123", "newpassword")
        assert isinstance(result, dict)
        assert "message" in result

    def test_logout_returns_message(self):
        from common_lib.modules.auth.service import auth_service

        result = auth_service.logout("user-123")
        assert isinstance(result, dict)
        assert "message" in result

    def test_verify_email_returns_message(self):
        from common_lib.modules.auth.service import auth_service

        result = auth_service.verify_email("token123")
        assert isinstance(result, dict)
        assert "message" in result

    def test_resend_verification_returns_message(self):
        from common_lib.modules.auth.service import auth_service

        result = auth_service.resend_verification("test@example.com")
        assert isinstance(result, dict)
        assert "message" in result


class TestAuthSchemas:
    """Tests for Auth schemas"""

    def test_login_request_schema_imports(self):
        from common_lib.modules.auth.schemas import LoginRequest

        assert LoginRequest is not None

    def test_register_request_schema_imports(self):
        from common_lib.modules.auth.schemas import RegisterRequest

        assert RegisterRequest is not None

    def test_token_response_schema_imports(self):
        from common_lib.modules.auth.schemas import TokenResponse

        assert TokenResponse is not None

    def test_user_response_schema_imports(self):
        from common_lib.modules.auth.schemas import UserResponse

        assert UserResponse is not None


class TestAuthSchemasFields:
    """Tests for Auth schema fields"""

    def test_login_request_has_email_and_password(self):
        from common_lib.modules.auth.schemas import LoginRequest

        login = LoginRequest(email="test@example.com", password="password123")
        assert login.email == "test@example.com"
        assert login.password == "password123"

    def test_register_request_has_required_fields(self):
        from common_lib.modules.auth.schemas import RegisterRequest

        register = RegisterRequest(
            email="test@example.com",
            username="testuser",
            password="password123",
            full_name="Test User",
            confirm_password="password123",
        )
        assert register.email == "test@example.com"
        assert register.username == "testuser"
        assert register.password == "password123"
        assert register.full_name == "Test User"

    def test_token_response_has_required_fields(self):
        from common_lib.modules.auth.schemas import TokenResponse

        token = TokenResponse(
            access_token="abc123", refresh_token="xyz789", expires_in=1800
        )
        assert token.access_token == "abc123"
        assert token.refresh_token == "xyz789"
        assert token.expires_in == 1800


class TestAuthServiceErrors:
    """Tests for error handling in auth service"""

    def test_refresh_access_token_raises_not_implemented(self):
        from common_lib.modules.auth.service import auth_service
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            auth_service.refresh_access_token("refresh_token")
        assert exc_info.value.status_code == 501
