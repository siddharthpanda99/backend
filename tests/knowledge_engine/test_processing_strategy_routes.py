"""Regression tests for the Processing Strategies HTTP surface (C2 fix).

Before this router existed, the KnowledgebasePage "Processing Strategies" tab
called `/api/v1/processing-strategies*`, which had NO backend implementation:
every request 404'd. These tests pin the router's contract so it cannot
silently drift again:

- every path the UI calls is actually registered under the mounted prefix;
- the KPS feature flag gates the surface with 503 (not a misleading 404);
- the router contains no business logic (thin-transport rule, G1).
"""

from __future__ import annotations

from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from app.modules.knowledge_engine.routes.processing_strategies import router

# Paths the KnowledgebasePage tab calls. Each must be registered.
UI_CALLED_PATHS = [
    ("GET", ""),
    ("POST", ""),
    ("POST", "/match"),
    ("GET", "/assignments"),
    ("POST", "/assign"),
    ("GET", "/{strategy_id}"),
    ("PATCH", "/{strategy_id}"),
    ("POST", "/{strategy_id}/activate"),
    ("POST", "/{strategy_id}/approve"),
    ("POST", "/{strategy_id}/deprecate"),
    ("GET", "/{strategy_id}/telemetry"),
]


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/knowledge-engine")
    return app


def _registered() -> set[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    for r in _app().routes:
        methods = getattr(r, "methods", None)
        if not methods:
            continue
        for m in methods:
            out.add((m, r.path))
    return out


class TestProcessingStrategyRoutesRegistered:
    def test_router_is_an_api_router(self) -> None:
        assert isinstance(router, APIRouter)

    def test_every_ui_called_path_is_registered(self) -> None:
        registered = _registered()
        missing = [
            (m, p)
            for m, p in UI_CALLED_PATHS
            if (m, f"/api/v1/knowledge-engine/processing-strategies{p}")
            not in registered
        ]
        assert not missing, f"Unregistered UI-called endpoints: {missing}"

    def test_no_delete_endpoint_is_exposed(self) -> None:
        """The service has no delete; the tab's dead Delete control was removed.

        If someone later adds a real delete, this test should be updated in the
        same change that adds the service method — not silently.
        """
        registered = _registered()
        assert not any(
            m == "DELETE"
            for m, p in registered
            if p.startswith("/api/v1/knowledge-engine/processing-strategies")
        )


class TestProcessingStrategyFeatureFlagGate:
    """G4/G9: the surface is OFF by default in production and env-gated.

    ``KPS_ENABLED`` is a frozen dataclass, so the flag is toggled through its
    documented env override (``KPS_ENABLED=0``) rather than by mutating the
    instance — that is also the mechanism operators actually use.
    """

    def test_returns_503_when_kps_disabled(self, monkeypatch) -> None:
        monkeypatch.setenv("KPS_ENABLED", "0")
        client = TestClient(_app())
        res = client.get("/api/v1/knowledge-engine/processing-strategies")
        assert res.status_code == 503
        assert "KPS_ENABLED" in res.json()["detail"]

    def test_match_also_gated(self, monkeypatch) -> None:
        monkeypatch.setenv("KPS_ENABLED", "0")
        client = TestClient(_app())
        res = client.post(
            "/api/v1/knowledge-engine/processing-strategies/match",
            json={"kb_id": "kb-1", "profile": {}},
        )
        assert res.status_code == 503

    def test_flag_defaults_off_in_production(self, monkeypatch) -> None:
        from common_lib.modules.knowledge_engine.processing_strategy.feature_flags import (
            KPS_ENABLED,
        )

        monkeypatch.delenv("KPS_ENABLED", raising=False)
        monkeypatch.setenv("ENVIRONMENT", "production")
        assert KPS_ENABLED.is_enabled() is False


class TestProcessingStrategyThinTransport:
    def test_router_module_defines_no_business_logic(self) -> None:
        """G1: the router delegates; it must not query the DB itself."""
        import inspect

        import app.modules.knowledge_engine.routes.processing_strategies as mod

        src = inspect.getsource(mod)
        for banned in ("session.exec(", "select(", "session.add(", "session.commit()"):
            assert banned not in src, f"Router contains persistence logic: {banned}"

    def test_router_delegates_to_the_common_lib_service(self) -> None:
        import inspect

        import app.modules.knowledge_engine.routes.processing_strategies as mod

        src = inspect.getsource(mod)
        assert "get_processing_strategy_service" in src
        assert "common_lib.modules.knowledge_engine.processing_strategy" in src
