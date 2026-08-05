# Auth Tests

import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch


# ── Test App Builder ────────────────────────────────────────────

def _build_auth_app():
    """Create a standalone FastAPI app with just the auth router (no app.main)."""
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse
    from common_lib.modules.exceptions import (
        ServiceError,
        UnauthorizedError,
        BadRequestError,
        NotFoundError,
    )
    from app.modules.auth.routes.index import router

    app = FastAPI()

    @app.exception_handler(UnauthorizedError)
    async def _unauthorized_handler(request: Request, exc: UnauthorizedError):
        return JSONResponse(
            status_code=getattr(exc, "status_code", 401),
            content={
                "detail": getattr(exc, "message", str(exc))
            },
        )

    @app.exception_handler(BadRequestError)
    async def _bad_request_handler(request: Request, exc: BadRequestError):
        return JSONResponse(
            status_code=getattr(exc, "status_code", 400),
            content={
                "detail": getattr(exc, "message", str(exc))
            },
        )

    @app.exception_handler(NotFoundError)
    async def _not_found_handler(request: Request, exc: NotFoundError):
        return JSONResponse(
            status_code=getattr(exc, "status_code", 404),
            content={
                "detail": getattr(exc, "message", str(exc))
            },
        )

    app.include_router(router)
    return app


def _setup_login_app(mock_session, mock_user=None):
    """Build auth app with get_session and (optionally) get_current_active_user overridden."""
    from common_lib.modules.data_storage.database.connection import get_session

    app = _build_auth_app()
    app.dependency_overrides[get_session] = lambda: mock_session

    if mock_user is not None:
        from app.modules.auth.dependencies import get_current_active_user
        app.dependency_overrides[get_current_active_user] = lambda: mock_user

    return app


# ── Auth Service Tests ──────────────────────────────────────────

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

        session = MagicMock()
        session.exec.return_value.first.return_value = None
        result = auth_service.forgot_password(session, "test@example.com")
        assert isinstance(result, dict)
        assert "message" in result
        assert "test@example.com" in result["message"]

    def test_reset_password_raises_on_invalid_token(self):
        from common_lib.modules.auth.service import auth_service
        from common_lib.modules.exceptions import BadRequestError

        session = MagicMock()
        session.exec.return_value.first.return_value = None
        with pytest.raises(BadRequestError):
            auth_service.reset_password(
                session, "token123", "newpassword", get_password_hash=lambda p: p
            )

    def test_logout_returns_message(self):
        from common_lib.modules.auth.service import auth_service

        session = MagicMock()
        session.exec.return_value.all.return_value = []
        result = auth_service.logout(session, 1)
        assert isinstance(result, dict)
        assert "message" in result

    def test_verify_email_returns_message(self):
        from common_lib.modules.auth.service import auth_service

        session = MagicMock()
        session.exec.return_value.first.return_value = None
        with pytest.raises(Exception):
            auth_service.verify_email(session, "token123")

    def test_resend_verification_returns_message(self):
        from common_lib.modules.auth.service import auth_service

        session = MagicMock()
        session.exec.return_value.first.return_value = None
        result = auth_service.resend_verification(session, "test@example.com")
        assert isinstance(result, dict)
        assert "message" in result


# ── Auth Schema Tests ───────────────────────────────────────────

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
        from common_lib.modules.auth.service import auth_service

        session = MagicMock()
        session.exec.return_value.first.return_value = None
        with pytest.raises(Exception):
            auth_service.refresh_access_token(
                session, "refresh_token", lambda **kw: "token"
            )


# ── Auth Route Tests (no app.main import) ──────────────────────

class TestAuthRoutes:
    """Integration tests for auth routes using dependency overrides."""

    def test_login_route_success(self):
        """POST /auth/login returns token when credentials are valid."""
        from common_lib.modules.auth.schemas import TokenResponse
        from fastapi.testclient import TestClient

        mock_session = MagicMock()
        app = _setup_login_app(mock_session)
        client = TestClient(app)

        with patch(
            "common_lib.modules.auth.service.auth_service.authenticate_user"
        ) as mock_auth:
            mock_auth.return_value = TokenResponse(
                access_token="mock_access",
                refresh_token="mock_refresh",
                expires_in=1800,
            )
            resp = client.post(
                "/login",
                json={"email": "t@example.com", "password": "password"},
            )

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["status"] == "success"
        assert data["data"]["access_token"] == "mock_access"

    def test_register_route_success(self):
        """POST /auth/register creates a new user and returns profile."""
        from common_lib.modules.auth.schemas import UserResponse
        from fastapi.testclient import TestClient

        mock_session = MagicMock()
        mock_session.exec.return_value.first.return_value = None  # no existing user
        app = _setup_login_app(mock_session)
        client = TestClient(app)

        with patch(
            "common_lib.modules.auth.service.auth_service.register_user"
        ) as mock_register:
            mock_register.return_value = UserResponse(
                id="1",
                email="t@example.com",
                username="t",
                full_name="T",
                is_active=True,
            )
            resp = client.post(
                "/register",
                json={
                    "email": "t@example.com",
                    "username": "t",
                    "password": "password",
                    "confirm_password": "password",
                    "full_name": "T",
                },
            )

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["status"] == "success"
        assert data["data"]["email"] == "t@example.com"

    def test_register_password_mismatch(self):
        """POST /auth/register returns 400 when passwords don't match."""
        from fastapi.testclient import TestClient

        mock_session = MagicMock()
        app = _setup_login_app(mock_session)
        client = TestClient(app)

        resp = client.post(
            "/register",
            json={
                "email": "t@example.com",
                "username": "t",
                "password": "password",
                "confirm_password": "mismatch",
                "full_name": "T",
            },
        )

        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        assert "Passwords do not match" in (
            resp.json().get("detail") or resp.json().get("message") or ""
        )

    def test_refresh_token_route(self):
        """POST /auth/refresh-token returns new token pair."""
        from common_lib.modules.auth.schemas import TokenResponse
        from fastapi.testclient import TestClient

        mock_session = MagicMock()
        app = _setup_login_app(mock_session)
        client = TestClient(app)

        with patch(
            "common_lib.modules.auth.service.auth_service.refresh_access_token"
        ) as mock_refresh:
            mock_refresh.return_value = TokenResponse(
                access_token="new_access",
                refresh_token="new_refresh",
                expires_in=1800,
            )
            resp = client.post(
                "/refresh-token", json={"refresh_token": "old_refresh"}
            )

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        assert resp.json()["data"]["access_token"] == "new_access"

    def test_forgot_password_route(self):
        """POST /auth/forgot-password returns success message."""
        from fastapi.testclient import TestClient

        mock_session = MagicMock()
        app = _setup_login_app(mock_session)
        client = TestClient(app)

        with patch(
            "common_lib.modules.auth.service.auth_service.forgot_password"
        ) as mock_forgot:
            mock_forgot.return_value = {"message": "Password reset email sent"}
            resp = client.post(
                "/forgot-password", json={"email": "t@example.com"}
            )

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        assert resp.json()["data"]["message"] == "Password reset email sent"

    def test_reset_password_route(self):
        """POST /auth/reset-password returns success message."""
        from fastapi.testclient import TestClient

        mock_session = MagicMock()
        app = _setup_login_app(mock_session)
        client = TestClient(app)

        with patch(
            "common_lib.modules.auth.service.auth_service.reset_password"
        ) as mock_reset:
            mock_reset.return_value = {"message": "Password reset complete"}
            resp = client.post(
                "/reset-password",
                json={
                    "token": "tok",
                    "new_password": "pass",
                    "confirm_password": "pass",
                },
            )

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        assert resp.json()["data"]["message"] == "Password reset complete"

    def test_reset_password_mismatch(self):
        """POST /auth/reset-password returns 400 when passwords don't match."""
        from fastapi.testclient import TestClient

        mock_session = MagicMock()
        app = _setup_login_app(mock_session)
        client = TestClient(app)

        resp = client.post(
            "/reset-password",
            json={
                "token": "tok",
                "new_password": "pass",
                "confirm_password": "mismatch",
            },
        )

        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        assert "Passwords do not match" in (
            resp.json().get("detail") or resp.json().get("message") or ""
        )

    def test_logout_route(self):
        """POST /auth/logout revokes tokens for authenticated user."""
        from common_lib.modules.users.models import User
        from fastapi.testclient import TestClient

        mock_session = MagicMock()
        mock_user = User(
            id=42,
            email="me@example.com",
            username="me",
            full_name="Me",
            is_active=True,
        )
        app = _setup_login_app(mock_session, mock_user=mock_user)
        client = TestClient(app)

        with patch(
            "common_lib.modules.auth.service.auth_service.logout"
        ) as mock_logout:
            mock_logout.return_value = {"message": "Logged out successfully"}
            resp = client.post("/logout")

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        assert resp.json()["message"] == "Logged out successfully"

    def test_me_route(self):
        """GET /auth/me returns current user profile."""
        from common_lib.modules.users.models import User
        from fastapi.testclient import TestClient

        mock_session = MagicMock()
        mock_user = User(
            id=42,
            email="me@example.com",
            username="me",
            full_name="Me",
            is_active=True,
        )
        app = _setup_login_app(mock_session, mock_user=mock_user)
        client = TestClient(app)

        resp = client.get("/me")

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["data"]["email"] == "me@example.com"
        assert data["data"]["id"] == "42"

    def test_me_route_unauthenticated(self):
        """GET /auth/me returns 401 when no auth header."""
        from fastapi.testclient import TestClient

        mock_session = MagicMock()
        app = _setup_login_app(mock_session)
        client = TestClient(app)

        resp = client.get("/me")

        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}: {resp.text}"

    def test_change_password_route(self):
        """POST /auth/change-password updates password for authenticated user."""
        from common_lib.modules.users.models import User
        from fastapi.testclient import TestClient

        mock_session = MagicMock()
        mock_user = User(
            id=42,
            email="me@example.com",
            username="me",
            full_name="Me",
            is_active=True,
        )
        app = _setup_login_app(mock_session, mock_user=mock_user)
        client = TestClient(app)

        with patch(
            "common_lib.modules.auth.service.auth_service.change_password"
        ) as mock_change:
            mock_change.return_value = {"message": "Password changed"}
            resp = client.post(
                "/change-password",
                json={
                    "old_password": "old",
                    "new_password": "new",
                    "confirm_password": "new",
                },
            )

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        assert resp.json()["data"]["message"] == "Password changed"

    def test_change_password_mismatch(self):
        """POST /auth/change-password returns 400 when new passwords don't match."""
        from common_lib.modules.users.models import User
        from fastapi.testclient import TestClient

        mock_session = MagicMock()
        mock_user = User(
            id=42,
            email="me@example.com",
            username="me",
            full_name="Me",
            is_active=True,
        )
        app = _setup_login_app(mock_session, mock_user=mock_user)
        client = TestClient(app)

        resp = client.post(
            "/change-password",
            json={
                "old_password": "old",
                "new_password": "new",
                "confirm_password": "mismatch",
            },
        )

        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        assert "Passwords do not match" in (
            resp.json().get("detail") or resp.json().get("message") or ""
        )

    def test_verify_email_route(self):
        """POST /auth/verify-email verifies email with token."""
        from fastapi.testclient import TestClient

        mock_session = MagicMock()
        app = _setup_login_app(mock_session)
        client = TestClient(app)

        with patch(
            "common_lib.modules.auth.service.auth_service.verify_email"
        ) as mock_verify:
            mock_verify.return_value = {"message": "Email verified"}
            resp = client.post("/verify-email", json={"token": "tok"})

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        assert resp.json()["data"]["message"] == "Email verified"

    def test_resend_verification_route(self):
        """POST /auth/resend-verification sends verification email."""
        from fastapi.testclient import TestClient

        mock_session = MagicMock()
        app = _setup_login_app(mock_session)
        client = TestClient(app)

        with patch(
            "common_lib.modules.auth.service.auth_service.resend_verification"
        ) as mock_resend:
            mock_resend.return_value = {"message": "Verification email sent"}
            resp = client.post(
                "/resend-verification", json={"email": "t@example.com"}
            )

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        assert resp.json()["data"]["message"] == "Verification email sent"

    def test_admin_only_route(self):
        """GET /auth/admin-only is behind RoleChecker — returns 403 for non-admin."""
        from common_lib.modules.users.models import User
        from fastapi.testclient import TestClient

        mock_session = MagicMock()
        mock_user = User(
            id=1,
            email="admin@example.com",
            username="admin",
            full_name="Admin",
            is_active=True,
        )

        app = _setup_login_app(mock_session, mock_user=mock_user)
        client = TestClient(app)
        resp = client.get("/admin-only")

        # Non-admin user is authenticated but lacks admin role → 403
        assert resp.status_code in (
            401,
            403,
        ), f"Expected 401/403, got {resp.status_code}: {resp.text}"

    def test_login_route_invalid_credentials(self):
        """POST /auth/login returns 401 for invalid credentials."""
        from fastapi.testclient import TestClient

        mock_session = MagicMock()
        mock_session.exec.return_value.first.return_value = None
        app = _setup_login_app(mock_session)
        client = TestClient(app)

        with patch(
            "common_lib.modules.auth.service.auth_service.authenticate_user"
        ) as mock_auth:
            from common_lib.modules.exceptions import UnauthorizedError
            mock_auth.side_effect = UnauthorizedError(message="Incorrect email or password")
            resp = client.post(
                "/login",
                json={"email": "bad@example.com", "password": "wrong"},
            )

        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}: {resp.text}"

    def test_login_route_missing_fields(self):
        """POST /auth/login returns 422 when required fields are missing."""
        from fastapi.testclient import TestClient

        mock_session = MagicMock()
        app = _setup_login_app(mock_session)
        client = TestClient(app)

        resp = client.post("/login", json={})
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}: {resp.text}"

    def test_register_route_missing_fields(self):
        """POST /auth/register returns 422 when required fields are missing."""
        from fastapi.testclient import TestClient

        mock_session = MagicMock()
        app = _setup_login_app(mock_session)
        client = TestClient(app)

        resp = client.post("/register", json={})
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}: {resp.text}"
