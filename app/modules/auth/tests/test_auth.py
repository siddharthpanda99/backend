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
        from unittest.mock import MagicMock
        from common_lib.modules.auth.service import auth_service

        session = MagicMock()
        session.exec.return_value.first.return_value = None
        result = auth_service.forgot_password(session, "test@example.com")
        assert isinstance(result, dict)
        assert "message" in result
        assert "test@example.com" in result["message"]

    def test_reset_password_raises_on_invalid_token(self):
        from unittest.mock import MagicMock
        from common_lib.modules.auth.service import auth_service
        from common_lib.modules.exceptions import BadRequestError

        session = MagicMock()
        session.exec.return_value.first.return_value = None
        with pytest.raises(BadRequestError):
            auth_service.reset_password(
                session, "token123", "newpassword", get_password_hash=lambda p: p
            )

    def test_logout_returns_message(self):
        from unittest.mock import MagicMock
        from common_lib.modules.auth.service import auth_service

        session = MagicMock()
        session.exec.return_value.all.return_value = []
        result = auth_service.logout(session, 1)
        assert isinstance(result, dict)
        assert "message" in result

    def test_verify_email_returns_message(self):
        from unittest.mock import MagicMock
        from common_lib.modules.auth.service import auth_service

        session = MagicMock()
        session.exec.return_value.first.return_value = None
        with pytest.raises(Exception):
            auth_service.verify_email(session, "token123")

    def test_resend_verification_returns_message(self):
        from unittest.mock import MagicMock
        from common_lib.modules.auth.service import auth_service

        session = MagicMock()
        session.exec.return_value.first.return_value = None
        result = auth_service.resend_verification(session, "test@example.com")
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

    def test_refresh_access_token_raises_error(self):
        from unittest.mock import MagicMock
        from common_lib.modules.auth.service import auth_service

        session = MagicMock()
        session.exec.return_value.first.return_value = None
        with pytest.raises(Exception):
            auth_service.refresh_access_token(
                session, "refresh_token", lambda **kw: "token"
            )


from unittest.mock import patch

class TestAuthRoutes:
    """E2E/Integration tests for auth routes using TestClient."""

    @pytest.fixture(autouse=True)
    def setup_client(self):
        from fastapi.testclient import TestClient
        from app.main import app
        self.client = TestClient(app)

    @patch("common_lib.modules.auth.service.auth_service.authenticate_user")
    def test_login_route_success(self, mock_auth):
        from common_lib.modules.auth.schemas import TokenResponse
        mock_auth.return_value = TokenResponse(
            access_token="mock_access", refresh_token="mock_refresh", expires_in=1800
        )
        resp = self.client.post("/api/v1/auth/login", json={"email": "t@example.com", "password": "password"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["data"]["access_token"] == "mock_access"

    @patch("common_lib.modules.auth.service.auth_service.register_user")
    def test_register_route_success(self, mock_register):
        from common_lib.modules.auth.schemas import UserResponse
        mock_register.return_value = UserResponse(
            id="1", email="t@example.com", username="t", full_name="T", is_active=True
        )
        resp = self.client.post(
            "/api/v1/auth/register",
            json={
                "email": "t@example.com",
                "username": "t",
                "password": "password",
                "confirm_password": "password",
                "full_name": "T",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["data"]["email"] == "t@example.com"

    def test_register_password_mismatch(self):
        resp = self.client.post(
            "/api/v1/auth/register",
            json={
                "email": "t@example.com",
                "username": "t",
                "password": "password",
                "confirm_password": "mismatch",
                "full_name": "T",
            },
        )
        assert resp.status_code == 400
        assert "Passwords do not match" in (resp.json().get("detail") or resp.json().get("message") or "")

    @patch("common_lib.modules.auth.service.auth_service.refresh_access_token")
    def test_refresh_token_route(self, mock_refresh):
        from common_lib.modules.auth.schemas import TokenResponse
        mock_refresh.return_value = TokenResponse(
            access_token="new_access", refresh_token="new_refresh", expires_in=1800
        )
        resp = self.client.post("/api/v1/auth/refresh-token", json={"refresh_token": "old_refresh"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["access_token"] == "new_access"

    @patch("common_lib.modules.auth.service.auth_service.forgot_password")
    def test_forgot_password_route(self, mock_forgot):
        mock_forgot.return_value = {"message": "sent"}
        resp = self.client.post("/api/v1/auth/forgot-password", json={"email": "t@example.com"})
        assert resp.status_code == 200
        assert resp.json()["data"]["message"] == "sent"

    @patch("common_lib.modules.auth.service.auth_service.reset_password")
    def test_reset_password_route(self, mock_reset):
        mock_reset.return_value = {"message": "reset"}
        resp = self.client.post(
            "/api/v1/auth/reset-password",
            json={"token": "tok", "new_password": "pass", "confirm_password": "pass"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["message"] == "reset"

    @patch("common_lib.modules.auth.service.auth_service.verify_email")
    def test_verify_email_route(self, mock_verify):
        mock_verify.return_value = {"message": "verified"}
        resp = self.client.post("/api/v1/auth/verify-email", json={"token": "tok"})
        assert resp.status_code == 200
        assert resp.json()["data"]["message"] == "verified"

    @patch("common_lib.modules.auth.service.auth_service.resend_verification")
    def test_resend_verification_route(self, mock_resend):
        mock_resend.return_value = {"message": "resent"}
        resp = self.client.post("/api/v1/auth/resend-verification", json={"email": "t@example.com"})
        assert resp.status_code == 200
        assert resp.json()["data"]["message"] == "resent"

    def test_me_route_authenticated(self):
        from common_lib.modules.users.models import User
        from app.main import app
        from app.modules.auth.dependencies import get_current_active_user

        mock_user = User(
            id=42,
            email="me@example.com",
            username="me",
            full_name="Me",
            is_active=True,
        )
        app.dependency_overrides[get_current_active_user] = lambda: mock_user
        try:
            resp = self.client.get("/api/v1/auth/me")
            assert resp.status_code == 200
            data = resp.json()
            assert data["data"]["email"] == "me@example.com"
        finally:
            app.dependency_overrides.clear()

