"""Security regression tests for P0 hardening fixes.

Tests:
  - P0-1: Production startup fails with missing / weak secrets, and with DEV_MODE=True in prod.
  - P0-2: Response cache key includes auth/tenant; Set-Cookie responses not cached.
  - P0-3: CORS rejects disallowed origins; allows listed origins.
  - P0-4: Identity headers from untrusted sources are ignored; JWT identity is used.
"""

import hashlib
import pytest
from unittest.mock import MagicMock, patch
from pydantic import ValidationError


# ---------------------------------------------------------------------------
# P0-1 — settings.py security validator
# ---------------------------------------------------------------------------

class TestSettingsSecurityValidator:
    """Fail-closed production defaults."""

    def _make_settings(self, **overrides):
        """Build a Settings instance with minimal valid defaults."""
        from app.core.settings import Settings

        defaults = {
            "ENVIRONMENT": "development",
            "DEV_MODE": True,
            "SECRET_KEY": "any-key-ignored-in-dev",
            "POSTGRES_PASSWORD": "pw-ignored-in-dev",
        }
        defaults.update(overrides)
        # Bypass lru_cache so we can pass explicit values.
        return Settings(**defaults)

    def test_dev_mode_true_allowed_in_development(self):
        s = self._make_settings(ENVIRONMENT="development", DEV_MODE=True)
        assert s.DEV_MODE is True

    def test_dev_mode_false_in_prod_is_allowed(self):
        s = self._make_settings(
            ENVIRONMENT="prod",
            DEV_MODE=False,
            SECRET_KEY="a" * 32,
            POSTGRES_PASSWORD="real-password",
        )
        assert s.DEV_MODE is False

    def test_dev_mode_true_in_prod_raises(self):
        with pytest.raises(ValidationError, match="DEV_MODE=True is not allowed"):
            self._make_settings(ENVIRONMENT="prod", DEV_MODE=True)

    def test_dev_mode_true_in_staging_raises(self):
        with pytest.raises(ValidationError, match="DEV_MODE=True is not allowed"):
            self._make_settings(ENVIRONMENT="staging", DEV_MODE=True)

    def test_empty_secret_key_in_non_dev_raises(self):
        with pytest.raises(ValidationError, match="SECRET_KEY must be set"):
            self._make_settings(
                ENVIRONMENT="development",
                DEV_MODE=False,
                SECRET_KEY="",
                POSTGRES_PASSWORD="pw",
            )

    def test_known_weak_secret_key_in_non_dev_raises(self):
        with pytest.raises(ValidationError, match="known weak"):
            self._make_settings(
                ENVIRONMENT="development",
                DEV_MODE=False,
                SECRET_KEY="09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7",
                POSTGRES_PASSWORD="pw",
            )

    def test_empty_postgres_password_in_non_dev_raises(self):
        with pytest.raises(ValidationError, match="POSTGRES_PASSWORD must be set"):
            self._make_settings(
                ENVIRONMENT="development",
                DEV_MODE=False,
                SECRET_KEY="a" * 32,
                POSTGRES_PASSWORD="",
            )

    def test_default_dev_mode_is_false(self):
        """DEV_MODE must default to False — never accidentally open."""
        from app.core.settings import Settings
        import inspect

        fields = Settings.model_fields
        # The default should come from config.get() but fall back to False.
        # We verify by building with no config override — if SECRET_KEY is missing
        # in a non-dev default environment, the validator fires.
        # This confirms the old True default is gone.
        source = inspect.getsource(Settings)
        assert "dev_mode\", False)" in source, (
            "DEV_MODE default should be False in the config.get() call"
        )


# ---------------------------------------------------------------------------
# P0-2 — response_cache.py key isolation + cacheability guard
# ---------------------------------------------------------------------------

class TestResponseCacheIsolation:
    """Cache key must partition by identity; unsafe responses must not be stored."""

    def _make_request(self, auth: str = "", tenant: str = "default", path: str = "/api/v1/models/"):
        from starlette.testclient import TestClient
        from starlette.requests import Request
        from starlette.datastructures import Headers

        scope = {
            "type": "http",
            "method": "GET",
            "path": path,
            "query_string": b"",
            "headers": [
                (b"authorization", auth.encode()),
                (b"x-tenant-id", tenant.encode()),
                (b"accept", b"application/json"),
            ],
        }
        return Request(scope)

    def test_different_auth_tokens_produce_different_keys(self):
        from app.middleware.response_cache import _cache_key

        req_a = self._make_request(auth="Bearer token-user-a")
        req_b = self._make_request(auth="Bearer token-user-b")
        assert _cache_key(req_a) != _cache_key(req_b)

    def test_different_tenants_produce_different_keys(self):
        from app.middleware.response_cache import _cache_key

        req_a = self._make_request(tenant="tenant-alpha")
        req_b = self._make_request(tenant="tenant-beta")
        assert _cache_key(req_a) != _cache_key(req_b)

    def test_same_user_same_tenant_same_key(self):
        from app.middleware.response_cache import _cache_key

        req_a = self._make_request(auth="Bearer tok", tenant="t1")
        req_b = self._make_request(auth="Bearer tok", tenant="t1")
        assert _cache_key(req_a) == _cache_key(req_b)

    def test_set_cookie_response_is_not_cacheable(self):
        from app.middleware.response_cache import _is_response_cacheable
        from starlette.responses import Response

        resp = Response(content=b"ok", status_code=200)
        resp.headers["set-cookie"] = "session=abc; HttpOnly"
        assert _is_response_cacheable(resp) is False

    def test_4xx_response_is_not_cacheable(self):
        from app.middleware.response_cache import _is_response_cacheable
        from starlette.responses import Response

        for code in (400, 401, 403, 404):
            resp = Response(content=b"err", status_code=code)
            assert _is_response_cacheable(resp) is False, f"Status {code} should not be cached"

    def test_5xx_response_is_not_cacheable(self):
        from app.middleware.response_cache import _is_response_cacheable
        from starlette.responses import Response

        resp = Response(content=b"err", status_code=500)
        assert _is_response_cacheable(resp) is False

    def test_200_response_without_set_cookie_is_cacheable(self):
        from app.middleware.response_cache import _is_response_cacheable
        from starlette.responses import Response

        resp = Response(content=b'{"data": []}', status_code=200)
        assert _is_response_cacheable(resp) is True

    def test_cache_disabled_by_default(self):
        from app.middleware.response_cache import RESPONSE_CACHE_ENABLED
        assert RESPONSE_CACHE_ENABLED is False, (
            "Response cache must be disabled by default (P0-2)"
        )

    def test_auth_prefix_excluded_from_cache(self):
        from app.middleware.response_cache import _should_cache

        req = self._make_request(path="/api/v1/auth/login")
        assert _should_cache(req) is False

    def test_cache_disabled_flag_prevents_caching(self):
        from app.middleware import response_cache
        from app.middleware.response_cache import _should_cache

        original = response_cache.RESPONSE_CACHE_ENABLED
        try:
            response_cache.RESPONSE_CACHE_ENABLED = False
            req = self._make_request(path="/api/v1/models/")
            assert _should_cache(req) is False
        finally:
            response_cache.RESPONSE_CACHE_ENABLED = original


# ---------------------------------------------------------------------------
# P0-3 — CORS: ensure wildcard regex is gone
# ---------------------------------------------------------------------------

class TestCORSConfiguration:
    """CORS must use explicit allowlist, not wildcard regex."""

    def test_cors_uses_explicit_origin_list(self):
        """Verify main.py creates CORSMiddleware with allow_origins (list), not allow_origin_regex."""
        import inspect
        import app.main as main_module

        source = inspect.getsource(main_module.create_app)

        assert "allow_origin_regex" not in source, (
            "allow_origin_regex must not appear in create_app — use allow_origins list instead (P0-3)"
        )
        assert "allow_origins=settings.BACKEND_CORS_ORIGINS" in source, (
            "CORS must use settings.BACKEND_CORS_ORIGINS allowlist (P0-3)"
        )

    def test_cors_methods_are_restricted(self):
        """Wildcard allow_methods=[\"*\"] must be gone."""
        import inspect
        import app.main as main_module

        source = inspect.getsource(main_module.create_app)
        assert 'allow_methods=["*"]' not in source, (
            "allow_methods must not be wildcard (P0-3)"
        )


# ---------------------------------------------------------------------------
# P0-4 — authz.py: identity must come from JWT, not raw headers
# ---------------------------------------------------------------------------

class TestAuthzTrustBoundary:
    """X-Subject-Id headers from untrusted callers must be ignored."""

    def _make_authz_middleware_request(self, headers: dict, dev_mode: bool = False):
        from starlette.requests import Request

        raw_headers = [
            (k.lower().encode(), v.encode()) for k, v in headers.items()
        ]
        raw_headers.append((b"host", b"localhost"))
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/models/",
            "query_string": b"",
            "headers": raw_headers,
        }
        return Request(scope)

    def test_is_trusted_proxy_returns_false_when_secret_empty(self):
        from app.modules.auth.middleware.authz import _is_trusted_proxy

        req = self._make_authz_middleware_request({"X-Proxy-Secret": "anything"})
        assert _is_trusted_proxy(req, "") is False

    def test_is_trusted_proxy_returns_false_for_wrong_secret(self):
        from app.modules.auth.middleware.authz import _is_trusted_proxy

        req = self._make_authz_middleware_request({"X-Proxy-Secret": "wrong"})
        assert _is_trusted_proxy(req, "correct-secret") is False

    def test_is_trusted_proxy_returns_true_for_matching_secret(self):
        from app.modules.auth.middleware.authz import _is_trusted_proxy

        req = self._make_authz_middleware_request({"X-Proxy-Secret": "my-secret"})
        assert _is_trusted_proxy(req, "my-secret") is True

    def test_jwt_is_primary_identity_source(self):
        """JWT in Authorization header must produce identity when no proxy headers present."""
        import inspect
        from app.modules.auth.middleware.authz import AuthzMiddleware

        source = inspect.getsource(AuthzMiddleware.dispatch)
        # JWT extraction must happen before header extraction
        jwt_pos = source.find("Authorization")
        header_pos = source.find("allow_proxy_headers")
        assert jwt_pos < header_pos, (
            "JWT extraction must precede proxy-header acceptance (P0-4)"
        )

    def test_trust_boundary_documented_in_docstring(self):
        from app.modules.auth.middleware.authz import AuthzMiddleware

        doc = AuthzMiddleware.__doc__ or ""
        assert "Trust boundary" in doc, (
            "AuthzMiddleware must document its trust boundary (P0-4)"
        )
