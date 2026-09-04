"""Route tests for the model-catalog usage endpoint.

Uses the real ai_models router + a patched ``ModelCatalogService`` so
no live network / DB is touched.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.ai_models.routes import router

app = FastAPI()
app.include_router(router)

client = TestClient(app)


USAGE_OVERVIEW = {
    "ok": True,
    "generated_at": "2026-09-04T00:00:00+00:00",
    "providers": [
        {
            "provider": "openrouter",
            "keys": [
                {
                    "id": 7,
                    "name": "or-prod",
                    "provider": "openrouter",
                    "label": "OpenRouter prod",
                    "enabled": True,
                    "is_active": True,
                    "status": "healthy",
                    "rate_limit": 1000,
                    "usage_limits": {"used": 0.5, "total": 10.0},
                    "last_used_at": None,
                    "last_checked_at": "2026-09-04T00:01:00",
                    "expires_at": None,
                    "models": [],
                }
            ],
            "model_count": 427,
            "usage": {
                "provider": "openrouter",
                "limit": 10.0,
                "usage": 0.5,
                "remaining": 9.5,
                "is_free_tier": False,
            },
            "rate_limit": 1000,
            "last_checked_at": "2026-09-04T00:01:00",
            "status": "healthy",
            "enabled": True,
        }
    ],
}


@pytest.fixture(autouse=True)
def _patched_catalog():
    svc = type(
        "FakeCatalog",
        (),
        {"usage_overview": lambda self: USAGE_OVERVIEW},
    )()
    with patch(
        "app.modules.ai_models.routes.router._catalog",
        return_value=svc,
    ):
        yield


def test_usage_endpoint_returns_overview() -> None:
    resp = client.get("/usage")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert len(body["providers"]) == 1
    prov = body["providers"][0]
    assert prov["provider"] == "openrouter"
    assert prov["model_count"] == 427
    assert prov["usage"]["remaining"] == 9.5
    assert prov["usage"]["is_free_tier"] is False
    assert prov["status"] == "healthy"


def test_usage_endpoint_isolated_route_set() -> None:
    """Only the catalog routes exist on the ai_models router."""
    routes = {
        (sorted(r.methods)[0] if r.methods else "?", r.path)
        for r in router.routes
    }
    assert ("GET", "/usage") in routes
    assert ("POST", "/refresh") in routes
    assert ("GET", "/list") in routes
