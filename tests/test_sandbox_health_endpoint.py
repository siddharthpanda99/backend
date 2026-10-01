"""The sandbox health endpoint must not lie about *why* it is unhealthy.

`initialize()` now raises `SandboxIsolationError` rather than silently substituting a weaker
provider, which is the correct behaviour -- but it means every route that initialises the service
now raises on a host without a Docker daemon. `/health` is the one route that must NOT turn that
into an opaque 500: an orchestrator reading 500 concludes "the whole service is broken" and
restarts it, when the truth is "this one subsystem cannot honour the isolation it was asked for".

Three distinct signals, and conflating them causes the wrong operational response:

| status | what an orchestrator concludes | truth here |
|---|---|---|
| 500 | the service is broken; restart it | no -- only the sandbox subsystem is degraded |
| 200 + `healthy=false` | healthy; keep sending traffic | no -- it cannot execute what it is asked to |
| **503** | this dependency is unavailable; take it out of rotation | **yes** |

These tests use a real `TestClient` over the real router. A fabricated `FastAPI` app would
validate the stand-in rather than the code.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from common_lib.modules.core_infrastructure.sandbox.sandbox_service import (
    SandboxIsolationError,
)


def _client() -> TestClient:
    from app.modules.sandbox.routes import router

    app = FastAPI()
    app.include_router(router)  # the router already carries prefix="/sandbox"
    # raise_server_exceptions=False so an unhandled 500 surfaces as a response
    # rather than an exception -- the point is what the CALLER sees.
    return TestClient(app, raise_server_exceptions=False)


def test_health_reports_503_not_500_when_isolation_is_unavailable(monkeypatch):
    """The regression: this used to return 500 (or run unisolated)."""
    client = _client()

    def _raise(*_a, **_kw):
        raise SandboxIsolationError(
            "Sandbox isolation unavailable: requested provider 'docker' could not "
            "be brought up; no fallback occurred."
        )

    monkeypatch.setattr(
        "app.modules.sandbox.routes.get_sandbox_service",
        lambda: type(
            "_Svc",
            (),
            {
                "_initialized": False,
                "initialize": staticmethod(_raise),
                "health_check": staticmethod(lambda: None),
                "list_sessions": staticmethod(lambda: None),
                "_provider": None,
            },
        )(),
    )

    response = client.get("/sandbox/health")
    assert response.status_code == 503, (
        f"expected 503 Service Unavailable, got {response.status_code} -- "
        "500 says the whole service is broken, 200 says it is ready"
    )
    body = response.json()
    assert body["healthy"] is False
    assert body["provider"] == "unavailable"
    assert body["sessions_active"] == 0
    assert "isolation unavailable" in (body.get("detail") or "").lower()


def test_health_still_200_when_the_provider_is_healthy(monkeypatch):
    """The 503 path must not swallow the healthy case."""
    client = _client()

    # A real class, because the route AWAITS these: a lambda returning True
    # would be a non-awaitable and the test would fail for the wrong reason.
    class _Healthy:
        _initialized = True
        _provider = object()

        async def initialize(self):
            return None

        async def health_check(self):
            return True

        async def list_sessions(self):
            return [1, 2, 3]

    monkeypatch.setattr(
        "app.modules.sandbox.routes.get_sandbox_service", lambda: _Healthy()
    )

    response = client.get("/sandbox/health")
    assert response.status_code == 200
    body = response.json()
    assert body["healthy"] is True
    assert body["sessions_active"] == 3
    # The new field is optional and additive; it must not appear as noise when
    # there is nothing wrong to explain.
    assert body.get("detail") is None


def test_detail_is_optional_so_existing_consumers_are_unaffected():
    """`detail` was added to the response model; it must have a default."""
    from app.modules.sandbox.routes import HealthResponse

    minimal = HealthResponse(healthy=True)
    assert minimal.provider == "unknown"
    assert minimal.sessions_active == 0
    assert minimal.detail is None
