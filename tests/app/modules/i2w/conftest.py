"""Shared pytest fixtures for the I2W Phase 7 router tests.

The tests are **pure-router** tests — they mount the I2W router on a
minimal FastAPI app, mock the underlying ``i2w_*`` wrapper calls, and
exercise the auth + RBAC + rate-limit + feature-flag contract.

We do NOT spin up the platform's full app (which would require
Postgres, Redis, etc.). The I2W router is purely a transport layer;
its behaviour is observable from a TestClient.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Enable test auth bypass BEFORE any imports that touch settings.
os.environ.setdefault("DISABLE_AUTH", "true")
# Also flip the I2W master flag on so endpoints are not 404'd.
os.environ.setdefault("I2W_ENABLED", "true")


@pytest.fixture
def i2w_app() -> FastAPI:
    """Return a FastAPI app with the I2W router mounted at /api/v1/i2w."""
    from app.modules.i2w import router as i2w_router

    app = FastAPI()
    app.include_router(i2w_router, prefix="/api/v1/i2w")
    return app


@pytest.fixture
def client(i2w_app: FastAPI) -> TestClient:
    """TestClient for the I2W app.

    Returns a plain client. Tests that hit endpoints requiring
    auth should use ``client_authenticated`` instead, which
    bypasses the platform's DB-backed auth dependency.
    """
    return TestClient(i2w_app)


@pytest.fixture(autouse=True)
def mock_i2w_nodes():
    """Patch every i2w_* wrapper invocation with a controllable mock.


    The mock returns ``{"status": "ok", "wrapper": <name>, "echo": <body>}``
    by default. Tests can override the return per-wrapper by adding
    entries to ``mock_i2w_nodes.by_name[<name>]``.

    Implementation note: each sub-router module imports
    ``invoke_i2w`` at module load, so patching
    ``_helpers.invoke_i2w`` does not rebind the local name in the
    sub-router. We therefore patch the symbol in every caller's
    namespace, which is what FastAPI will look up at request time.
    """
    import sys
    from app.modules.i2w.routes import _helpers
    from app.modules.i2w.routes import (
        dispatch,
        executions,
        generate,
        health,
        ingest,
        plan,
        reason,
        search,
        training,
        workflows,
    )

    class _Registry:
        def __init__(self) -> None:
            self.by_name: Dict[str, Any] = {}
            self.calls: List[Dict[str, Any]] = []

        def set(self, name: str, value: Any) -> None:
            self.by_name[name] = value

        def __call__(self, name: str, **kwargs: Any) -> Dict[str, Any]:
            self.calls.append({"name": name, "kwargs": kwargs})
            if name in self.by_name:
                value = self.by_name[name]
                if callable(value):
                    return value(**kwargs)
                return value
            return {
                "status": "ok",
                "wrapper": name,
                "echo": kwargs,
            }

    reg = _Registry()

    def fake_invoke(name: str, defaults=None, **kwargs):
        payload: Dict[str, Any] = {}
        if defaults:
            payload.update(defaults)
        payload.update(kwargs)
        return reg(name, **payload)

    modules = [
        _helpers,
        dispatch,
        executions,
        generate,
        health,
        ingest,
        plan,
        reason,
        search,
        training,
        workflows,
    ]
    # Snapshot the original ``invoke_i2w`` symbols so we can restore
    originals = {m: m.invoke_i2w for m in modules}
    for m in modules:
        m.invoke_i2w = fake_invoke
    try:
        yield reg
    finally:
        for m, original in originals.items():
            m.invoke_i2w = original


@pytest.fixture
def enable_i2w_flag():
    """Patch the I2W feature flag to return True.

    The flag is enabled by default for all I2W tests; the
    ``disable_i2w_flag`` fixture overrides this for the
    specific tests that verify the 404 path.
    """
    from app.modules.i2w.routes import dependencies
    from app.modules.i2w.routes import health

    with (
        patch.object(
            dependencies,
            "_master_or_sub_enabled",
            return_value=True,
        ),
        patch.object(health, "_is_i2w_enabled", return_value=True),
    ):
        yield


@pytest.fixture(autouse=True)
def _enable_i2w_flag_by_default(enable_i2w_flag):
    """Auto-enable the I2W feature flag for every test.

    The default behaviour of the I2W router is to return 404
    when the flag is off. The test suite is only meaningful
    when the flag is on, so we enable it by default. The
    ``disable_i2w_flag`` fixture can be requested explicitly
    to test the 404 path.
    """
    yield


@pytest.fixture
def disable_i2w_flag():
    """Patch the I2W feature flag to return False (404 mode)."""
    from app.modules.i2w.routes import dependencies
    from app.modules.i2w.routes import health

    with (
        patch.object(
            dependencies,
            "_master_or_sub_enabled",
            return_value=False,
        ),
        patch.object(health, "_is_i2w_enabled", return_value=False),
    ):
        yield


@pytest.fixture
def mock_identity_dep():
    """Bypass the platform's auth dependency in the I2W TestClient.

    The I2W router uses ``get_current_identity`` (from
    ``app.modules.auth.dependencies.authz``) via the
    ``i2w_identity`` wrapper. We override the dependency at the
    FastAPI app level (``app.dependency_overrides[get_current_identity]``)
    so every route that asks for it gets our fake identity. This
    is more reliable than module-attribute patching because the
    route handlers' ``Depends(...)`` references are captured at
    route-definition time.
    """
    from unittest.mock import MagicMock

    from app.modules.i2w.routes.dependencies import i2w_identity
    from app.modules.auth.dependencies.authz import get_current_identity
    from app.modules.auth.dependencies.index import get_current_identity as gci_idx

    identity = MagicMock()
    identity.subject_id = "test-user"
    identity.tenant_id = "default"
    identity.scopes = [
        "i2w.read",
        "i2w.write",
        "i2w.execute",
        "i2w.training.admin",
    ]
    identity.is_admin = False

    async def _fake_identity(*args, **kwargs):
        return identity

    return identity


@pytest.fixture
def client_authenticated(i2w_app, mock_identity_dep, request) -> TestClient:
    """TestClient that bypasses real auth via FastAPI's dependency_overrides.

    This is the workhorse fixture for most tests. It registers a
    fake identity in ``app.dependency_overrides`` for both
    ``get_current_identity`` (platform) and ``i2w_identity`` (I2W
    thin wrapper) so every route sees the fake.
    """
    from unittest.mock import MagicMock

    from app.modules.i2w.routes.dependencies import i2w_identity
    from app.modules.auth.dependencies.authz import get_current_identity

    identity = MagicMock()
    identity.subject_id = "test-user"
    identity.tenant_id = "default"
    identity.scopes = [
        "i2w.read",
        "i2w.write",
        "i2w.execute",
        "i2w.training.admin",
    ]
    identity.is_admin = False

    async def _fake_identity(*args, **kwargs):
        return identity

    # Both names must be overridden — the rate-limit dep also
    # references i2w_identity.
    i2w_app.dependency_overrides[get_current_identity] = _fake_identity
    i2w_app.dependency_overrides[i2w_identity] = _fake_identity
    yield TestClient(i2w_app)
    i2w_app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def reset_rate_limit_windows():
    """Clear the in-process rate-limit sliding-window store between tests.

    The windows dict lives at module level; without this fixture
    state from a prior test would carry over and cause spurious
    429 responses.
    """
    from app.modules.i2w.routes import dependencies

    dependencies._windows.clear()
    yield
    dependencies._windows.clear()
