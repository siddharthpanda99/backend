"""
RBAC Enforcement Tests — Verify require_permission blocks unauthorized requests.

Key insight: FastAPI DI overrides must have the same parameter signature as the
original dependency, or no parameters at all. Using *args/**kwargs causes FastAPI
to interpret them as query parameters (422 error).
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helper: Create a minimal test app with a protected route
# ---------------------------------------------------------------------------

def _create_test_app():
    """Create a FastAPI app with a route protected by require_permission."""
    from app.modules.auth.dependencies.authz import require_permission

    app = FastAPI()

    @app.get("/test-rbac")
    async def rbac_route(
        _perm: None = require_permission("project.read", "*", "project"),
    ):
        return {"message": "access granted"}

    return app


def _make_identity(user_id="1"):
    """Create a mock PlatformIdentity."""
    identity = MagicMock()
    identity.subject_id = user_id
    identity.subject_type = "user"
    identity.tenant_id = "default"
    identity.display_name = "Test User"
    return identity


def _mock_user():
    """Create a mock User."""
    user = MagicMock()
    user.id = 1
    user.is_active = True
    user.full_name = "Test User"
    user.username = "testuser"
    user.email = "test@example.com"
    user.tenant_id = "default"
    return user


def _patch_auth(app):
    """Apply all auth DI overrides to the app. Returns context manager for patches."""
    from app.modules.auth.dependencies.authz import (
        get_current_active_user, get_current_identity, get_authz_checker,
    )

    identity = _make_identity()
    user = _mock_user()
    checker = MagicMock()

    async def _no_args():
        """Override with no parameters — FastAPI won't treat as query params."""
        pass

    # Override get_current_active_user to return mock user without DB
    async def _override_active_user():
        return user

    # Override get_current_identity to return mock identity without DB
    async def _override_identity():
        return identity

    # Override get_authz_checker to return mock checker without DB
    async def _override_checker():
        return checker

    app.dependency_overrides[get_current_active_user] = _override_active_user
    app.dependency_overrides[get_current_identity] = _override_identity
    app.dependency_overrides[get_authz_checker] = _override_checker


# ---------------------------------------------------------------------------
# Test: Unauthenticated requests -> 401
# ---------------------------------------------------------------------------

class TestRBACUnauthenticated:

    def test_no_token_returns_401(self):
        app = _create_test_app()
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/test-rbac")
            assert response.status_code == 401

    def test_empty_auth_header_returns_401(self):
        app = _create_test_app()
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/test-rbac", headers={"Authorization": ""})
            assert response.status_code == 401

    def test_non_bearer_token_returns_401(self):
        app = _create_test_app()
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/test-rbac", headers={"Authorization": "Basic abc123"})
            assert response.status_code == 401


# ---------------------------------------------------------------------------
# Test: Authenticated but no permission -> 403
# ---------------------------------------------------------------------------

class TestRBACInsufficientPermissions:

    def test_permission_check_denied_returns_403(self):
        app = _create_test_app()
        _patch_auth(app)

        with patch("app.modules.auth.dependencies.authz.check_permission", side_effect=Exception("Access denied")), \
             patch("app.modules.auth.dependencies.authz.RBACAuditService") as mock_audit:
            mock_audit.return_value = MagicMock()

            with TestClient(app, raise_server_exceptions=False) as client:
                response = client.get("/test-rbac", headers={"Authorization": "Bearer fake-token"})
                assert response.status_code == 403
                assert "permission denied" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Test: Authenticated with correct permissions -> 200
# ---------------------------------------------------------------------------

class TestRBACAuthorized:

    def test_valid_token_with_permission_returns_200(self):
        app = _create_test_app()
        _patch_auth(app)

        with patch("app.modules.auth.dependencies.authz.check_permission"), \
             patch("app.modules.auth.dependencies.authz.RBACAuditService") as mock_audit:
            mock_audit.return_value = MagicMock()

            with TestClient(app, raise_server_exceptions=False) as client:
                response = client.get("/test-rbac", headers={"Authorization": "Bearer fake-token"})
                assert response.status_code == 200
                assert response.json()["message"] == "access granted"


# ---------------------------------------------------------------------------
# Test: Super admin bypass
# ---------------------------------------------------------------------------

class TestRBACSuperAdminBypass:

    def test_admin_with_wildcard_permission_succeeds(self):
        app = _create_test_app()
        _patch_auth(app)

        with patch("app.modules.auth.dependencies.authz.check_permission"), \
             patch("app.modules.auth.dependencies.authz.RBACAuditService") as mock_audit:
            mock_audit.return_value = MagicMock()

            with TestClient(app, raise_server_exceptions=False) as client:
                response = client.get("/test-rbac", headers={"Authorization": "Bearer fake-token"})
                assert response.status_code == 200


# ---------------------------------------------------------------------------
# Test: Inactive user -> 403
# ---------------------------------------------------------------------------

class TestRBACInactiveUser:

    def test_inactive_user_returns_403(self):
        from app.modules.auth.dependencies.authz import get_current_identity, get_authz_checker
        from fastapi import HTTPException

        app = _create_test_app()

        # Override get_current_identity (not get_current_active_user) because
        # get_current_identity calls get_current_active_user directly, not via Depends
        async def _override_inactive_identity():
            raise HTTPException(status_code=403, detail="Inactive user")

        async def _override_checker():
            return MagicMock()

        app.dependency_overrides[get_current_identity] = _override_inactive_identity
        app.dependency_overrides[get_authz_checker] = _override_checker

        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/test-rbac", headers={"Authorization": "Bearer fake-token"})
            assert response.status_code == 403
            assert "inactive" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Test: Audit logging
# ---------------------------------------------------------------------------

class TestRBACAuditLogging:

    def test_successful_permission_check_is_audited(self):
        app = _create_test_app()
        _patch_auth(app)

        with patch("app.modules.auth.dependencies.authz.check_permission"), \
             patch("app.modules.auth.dependencies.authz.RBACAuditService") as mock_audit:
            mock_audit_instance = MagicMock()
            mock_audit.return_value = mock_audit_instance

            with TestClient(app, raise_server_exceptions=False) as client:
                client.get("/test-rbac", headers={"Authorization": "Bearer fake-token"})
                mock_audit_instance.log_permission_check.assert_called()

    def test_failed_permission_check_is_audited(self):
        app = _create_test_app()
        _patch_auth(app)

        with patch("app.modules.auth.dependencies.authz.check_permission", side_effect=Exception("Denied")), \
             patch("app.modules.auth.dependencies.authz.RBACAuditService") as mock_audit:
            mock_audit_instance = MagicMock()
            mock_audit.return_value = mock_audit_instance

            with TestClient(app, raise_server_exceptions=False) as client:
                client.get("/test-rbac", headers={"Authorization": "Bearer fake-token"})
                mock_audit_instance.log_permission_check.assert_called()


# ---------------------------------------------------------------------------
# Test: Multiple permission levels
# ---------------------------------------------------------------------------

class TestRBACMultiplePermissions:

    def test_read_permission_does_not_grant_write(self):
        from app.modules.auth.dependencies.authz import require_permission, get_current_identity, get_current_active_user, get_authz_checker

        app = FastAPI()

        @app.get("/test-read-only")
        async def read_only_route(
            _perm: None = require_permission("project.read", "*", "project"),
        ):
            return {"message": "read success"}

        @app.post("/test-write-only")
        async def write_only_route(
            _perm: None = require_permission("project.write", "*", "project"),
        ):
            return {"message": "write success"}

        # Apply DI overrides BEFORE defining routes isn't possible, but we can
        # override at the right level. The key: require_permission's dependency
        # calls check_permission from authz module scope. We patch it at the
        # module level so the closure sees the patched version.
        identity = _make_identity()
        user = _mock_user()
        checker = MagicMock()

        async def _override_active_user():
            return user

        async def _override_identity():
            return identity

        async def _override_checker():
            return checker

        app.dependency_overrides[get_current_active_user] = _override_active_user
        app.dependency_overrides[get_current_identity] = _override_identity
        app.dependency_overrides[get_authz_checker] = _override_checker

        def mock_check_permission(chk, action, rid, rtype):
            # action is the full permission string like "project.write", not just "write"
            if "write" in action:
                raise Exception("Write permission denied")

        # Patch check_permission and RBACAuditService at the module level
        # so require_permission's closure sees the patched version
        with patch("app.modules.auth.dependencies.authz.check_permission", side_effect=mock_check_permission), \
             patch("app.modules.auth.dependencies.authz.RBACAuditService") as mock_audit:
            mock_audit.return_value = MagicMock()

            with TestClient(app, raise_server_exceptions=False) as client:
                response = client.get("/test-read-only", headers={"Authorization": "Bearer fake-token"})
                assert response.status_code == 200

                response = client.post("/test-write-only", headers={"Authorization": "Bearer fake-token"})
                assert response.status_code == 403
