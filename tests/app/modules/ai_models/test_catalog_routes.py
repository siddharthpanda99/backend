"""ai_models catalog router tests (pure-router TestClient).

Mounts the catalog router on a minimal FastAPI app and exercises the
HTTP contract the ModelCatalogPage UI consumes:

- GET  /api/v1/ai_models/list        -> snapshot payload
- POST /api/v1/ai_models/refresh     -> refresh payload (provider-filterable)
- POST /api/v1/ai_models/set-default -> persist default
- GET  /api/v1/ai_models/status      -> per-provider status

The service layer (ModelCatalogService) is patched — these tests only
verify the transport wiring, mirroring the platform's thin-router rule.
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ.setdefault("DISABLE_AUTH", "true")


@pytest.fixture(scope="module")
def client() -> TestClient:
    from app.modules.ai_models.routes import router as ai_models_router

    app = FastAPI()
    app.include_router(ai_models_router, prefix="/api/v1/ai_models")
    return TestClient(app)


_SNAPSHOT = {
    "ok": True,
    "generated_at": "2026-09-03T10:00:00+00:00",
    "models": [
        {
            "provider": "groq",
            "model_id": "llama-3.3-70b-versatile",
            "display_name": "llama-3.3-70b-versatile",
            "family": "",
            "context_window": None,
            "capabilities": {},
            "cost_tier": "unknown",
            "available_via_keys": [],
            "rate_limit_remaining": None,
            "quota_used": None,
            "quota_total": None,
            "last_refreshed": None,
            "source": "fallback",
            "notes": "",
        }
    ],
    "keys": [],
    "providers": ["groq"],
}

_REFRESH = {
    "ok": True,
    "refreshed": ["groq"],
    "skipped": [],
    "warnings": [],
    "generated_at": "2026-09-03T10:05:00+00:00",
    "model_counts": {"groq": 40},
}

_DEFAULT_OK = {"ok": True, "provider": "groq", "model": "llama-3.3-70b-versatile", "saved": True}


class TestList:
    def test_list_returns_snapshot(self, client):
        with patch(
            "common_lib.modules.ai_models.catalog.ModelCatalogService.snapshot",
            return_value=_SNAPSHOT,
        ):
            r = client.get("/api/v1/ai_models/list")
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert body["models"][0]["model_id"] == "llama-3.3-70b-versatile"
        assert body["providers"] == ["groq"]


class TestRefresh:
    def test_refresh_all(self, client):
        with patch(
            "common_lib.modules.ai_models.catalog.ModelCatalogService.refresh_status",
            return_value=_REFRESH,
        ) as m:
            r = client.post("/api/v1/ai_models/refresh")
        assert r.status_code == 200
        assert r.json()["refreshed"] == ["groq"]
        # No provider restriction passed.
        assert m.call_args.kwargs.get("provider") is None

    def test_refresh_one_provider(self, client):
        with patch(
            "common_lib.modules.ai_models.catalog.ModelCatalogService.refresh_status",
            return_value=_REFRESH,
        ) as m:
            r = client.post("/api/v1/ai_models/refresh?provider=groq")
        assert r.status_code == 200
        assert m.call_args.kwargs.get("provider") == "groq"


class TestSetDefault:
    def test_set_default(self, client):
        with patch(
            "common_lib.modules.ai_models.catalog.ModelCatalogService.set_default_model",
            return_value=_DEFAULT_OK,
        ) as m:
            r = client.post(
                "/api/v1/ai_models/set-default?provider=groq&model_id=llama-3.3-70b-versatile"
            )
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert m.call_args.args == ("groq", "llama-3.3-70b-versatile")


class TestStatus:
    def test_status_filters_by_provider(self, client):
        provider_snap = dict(_SNAPSHOT)
        provider_snap["provider"] = "groq"
        with patch(
            "common_lib.modules.ai_models.catalog.ModelCatalogService.provider_status",
            return_value=provider_snap,
        ) as m:
            r = client.get("/api/v1/ai_models/status?provider=groq")
        assert r.status_code == 200
        assert r.json()["provider"] == "groq"
        assert m.call_args.args[0] == "groq"


class TestErrorMapping:
    def test_internal_error_becomes_500(self, client):
        with patch(
            "common_lib.modules.ai_models.catalog.ModelCatalogService.snapshot",
            side_effect=RuntimeError("boom"),
        ):
            r = client.get("/api/v1/ai_models/list")
        assert r.status_code == 500
        assert "boom" in r.json()["detail"]
