"""
API-level tests for Knowledge Analytics endpoints.

All analytics routes delegate to AnalyticsService static methods.
Tests mock the service to verify routing, response structure,
delegation, validation, and error handling.

Endpoints:
    GET /knowledge/analytics/overview           — Overview metrics
    GET /knowledge/analytics/time-series        — Time series data
    GET /knowledge/analytics/top-chunks         — Top chunks
    GET /knowledge/analytics/agent-usage        — Agent usage tracking

Usage:
    cd Backend Monorepo/Backend
    uv run python -m pytest app/modules/knowledge/tests/test_analytics.py -v
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.modules.knowledge.routes import router as knowledge_router
from common_lib.modules.knowledge_hub.services.analytics_service import (
    AnalyticsService,
)


# ── Sample data ────────────────────────────────────────────────────

SAMPLE_OVERVIEW = {
    "total_chunks": 100,
    "total_projects": 10,
    "total_packets": 25,
    "total_sources": 15,
    "total_scrapers": 5,
    "total_conflicts": 3,
    "open_conflicts": 1,
    "projects_with_agents": 4,
    "chunks_by_source_type": {"text": 60, "financial": 40},
    "chunks_by_domain": {"general": 50, "financial": 30, "news": 20},
}

SAMPLE_OVERVIEW_WITH_RECENT = {
    **SAMPLE_OVERVIEW,
    "recent_chunks": 10,
    "recent_projects": 2,
    "recent_packets": 5,
    "recent_activity_entries": 50,
    "lookback_days": 7,
}

SAMPLE_TIME_SERIES = {
    "metric": "chunks",
    "granularity": "day",
    "lookback_days": 30,
    "data_points": [
        {"date": "2026-01-01", "count": 5},
        {"date": "2026-01-02", "count": 3},
    ],
    "total_in_period": 8,
}

SAMPLE_TOP_CHUNKS = {
    "top_chunks": [
        {
            "chunk_id": "c-top-001",
            "content_preview": "This is a top chunk...",
            "source_id": "src-001",
            "source_type": "text",
            "domain": "general",
            "topics": ["AI"],
            "has_embedding": True,
            "created_at": "2026-01-01T00:00:00",
            "updated_at": "2026-01-15T00:00:00",
        }
    ],
    "total_returned": 1,
    "source_type_breakdown": {"text": 1},
}

SAMPLE_AGENT_USAGE = {
    "agents": [
        {
            "agent_id": "agent-001",
            "projects": [
                {
                    "project_id": "proj-001",
                    "project_name": "Test Project",
                    "packet_count": 3,
                    "status": "verified",
                }
            ],
            "total_projects": 1,
            "total_packets": 3,
        }
    ],
    "total_agents": 1,
    "total_projects_with_agents": 1,
}


# ── Fixtures ───────────────────────────────────────────────────────


@pytest.fixture
def app() -> FastAPI:
    """Create a FastAPI app with the Knowledge router mounted at /api/v1."""
    _app = FastAPI()
    _app.include_router(knowledge_router, prefix="/api/v1")

    # Override session dependency with a minimal test session
    from sqlmodel import SQLModel, create_engine
    from sqlalchemy.pool import StaticPool
    from common_lib.modules.data_storage.database.connection import get_session

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def get_test_session():
        with Session(engine) as session:
            yield session

    _app.dependency_overrides[get_session] = get_test_session
    return _app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """Sync TestClient for the knowledge app."""
    return TestClient(app)


# ═══════════════════════════════════════════════════════════════════
# GET /knowledge/analytics/overview
# ═══════════════════════════════════════════════════════════════════


class TestAnalyticsOverview:
    """GET /api/v1/knowledge/analytics/overview — overview metrics."""

    MODULE_PATH = "app.modules.knowledge.routes.AnalyticsService"

    def test_overview_returns_counts(self, client: TestClient) -> None:
        with patch.object(AnalyticsService, "overview", return_value=SAMPLE_OVERVIEW):
            response = client.get("/api/v1/knowledge/analytics/overview")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["total_chunks"] == 100
        assert body["data"]["total_projects"] == 10
        assert body["data"]["total_sources"] == 15

    def test_overview_with_days_param(self, client: TestClient) -> None:
        with patch.object(
            AnalyticsService, "overview", return_value=SAMPLE_OVERVIEW_WITH_RECENT
        ) as mock:
            response = client.get("/api/v1/knowledge/analytics/overview?days=7")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["lookback_days"] == 7
        assert data["recent_chunks"] == 10
        mock.assert_called_once()
        _, kwargs = mock.call_args
        assert kwargs.get("days") == 7

    def test_overview_delegates(self, client: TestClient) -> None:
        with patch.object(AnalyticsService, "overview", return_value=SAMPLE_OVERVIEW) as mock:
            client.get("/api/v1/knowledge/analytics/overview")
            mock.assert_called_once()

    def test_overview_includes_breakdowns(self, client: TestClient) -> None:
        with patch.object(AnalyticsService, "overview", return_value=SAMPLE_OVERVIEW):
            response = client.get("/api/v1/knowledge/analytics/overview")
        data = response.json()["data"]
        assert "chunks_by_source_type" in data
        assert "chunks_by_domain" in data
        assert data["chunks_by_source_type"]["text"] == 60

    def test_overview_returns_500_on_error(self, app: FastAPI) -> None:
        quiet_client = TestClient(app, raise_server_exceptions=False)
        with patch.object(
            AnalyticsService, "overview", side_effect=Exception("DB error")
        ):
            response = quiet_client.get("/api/v1/knowledge/analytics/overview")
        assert response.status_code == 500


# ═══════════════════════════════════════════════════════════════════
# GET /knowledge/analytics/time-series
# ═══════════════════════════════════════════════════════════════════


class TestAnalyticsTimeSeries:
    """GET /api/v1/knowledge/analytics/time-series — time series data."""

    def test_time_series_returns_data_points(self, client: TestClient) -> None:
        with patch.object(AnalyticsService, "time_series", return_value=SAMPLE_TIME_SERIES):
            response = client.get("/api/v1/knowledge/analytics/time-series?metric=chunks&days=30&granularity=day")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["metric"] == "chunks"
        assert len(body["data"]["data_points"]) == 2
        assert body["data"]["total_in_period"] == 8

    def test_time_series_delegates_defaults(self, client: TestClient) -> None:
        with patch.object(AnalyticsService, "time_series", return_value=SAMPLE_TIME_SERIES) as mock:
            client.get("/api/v1/knowledge/analytics/time-series")
            mock.assert_called_once()
            _, kwargs = mock.call_args
            assert kwargs.get("metric") == "chunks"
            assert kwargs.get("days") == 30
            assert kwargs.get("granularity") == "day"

    def test_time_series_delegates_params(self, client: TestClient) -> None:
        with patch.object(AnalyticsService, "time_series", return_value=SAMPLE_TIME_SERIES) as mock:
            client.get("/api/v1/knowledge/analytics/time-series?metric=projects&days=7&granularity=week")
            _, kwargs = mock.call_args
            assert kwargs.get("metric") == "projects"
            assert kwargs.get("days") == 7
            assert kwargs.get("granularity") == "week"

    def test_time_series_invalid_metric_returns_400(self, client: TestClient) -> None:
        response = client.get("/api/v1/knowledge/analytics/time-series?metric=invalid")
        assert response.status_code == 400
        assert "metric must be" in response.json()["detail"].lower()

    def test_time_series_invalid_granularity_returns_400(self, client: TestClient) -> None:
        response = client.get("/api/v1/knowledge/analytics/time-series?granularity=year")
        assert response.status_code == 400
        assert "granularity must be" in response.json()["detail"].lower()

    def test_time_series_returns_500_on_error(self, app: FastAPI) -> None:
        quiet_client = TestClient(app, raise_server_exceptions=False)
        with patch.object(
            AnalyticsService, "time_series", side_effect=Exception("Query failed")
        ):
            response = quiet_client.get("/api/v1/knowledge/analytics/time-series")
        assert response.status_code == 500


# ═══════════════════════════════════════════════════════════════════
# GET /knowledge/analytics/top-chunks
# ═══════════════════════════════════════════════════════════════════


class TestAnalyticsTopChunks:
    """GET /api/v1/knowledge/analytics/top-chunks — top chunks."""

    def test_top_chunks_returns_list(self, client: TestClient) -> None:
        with patch.object(AnalyticsService, "top_chunks", return_value=SAMPLE_TOP_CHUNKS):
            response = client.get("/api/v1/knowledge/analytics/top-chunks")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert len(body["data"]["top_chunks"]) == 1
        assert body["data"]["top_chunks"][0]["chunk_id"] == "c-top-001"

    def test_top_chunks_has_required_fields(self, client: TestClient) -> None:
        with patch.object(AnalyticsService, "top_chunks", return_value=SAMPLE_TOP_CHUNKS):
            response = client.get("/api/v1/knowledge/analytics/top-chunks")
        chunk = response.json()["data"]["top_chunks"][0]
        assert "chunk_id" in chunk
        assert "content_preview" in chunk
        assert "source_id" in chunk
        assert "has_embedding" in chunk
        assert "domain" in chunk

    def test_top_chunks_with_params(self, client: TestClient) -> None:
        with patch.object(AnalyticsService, "top_chunks", return_value=SAMPLE_TOP_CHUNKS) as mock:
            client.get("/api/v1/knowledge/analytics/top-chunks?limit=5&days=30&domain=news")
            _, kwargs = mock.call_args
            assert kwargs.get("limit") == 5
            assert kwargs.get("days") == 30
            assert kwargs.get("domain") == "news"

    def test_top_chunks_delegates_defaults(self, client: TestClient) -> None:
        with patch.object(AnalyticsService, "top_chunks", return_value=SAMPLE_TOP_CHUNKS) as mock:
            client.get("/api/v1/knowledge/analytics/top-chunks")
            _, kwargs = mock.call_args
            assert kwargs.get("limit") == 10
            assert kwargs.get("days") is None
            assert kwargs.get("domain") is None

    def test_top_chunks_empty(self, client: TestClient) -> None:
        empty = {"top_chunks": [], "total_returned": 0, "source_type_breakdown": {}}
        with patch.object(AnalyticsService, "top_chunks", return_value=empty):
            response = client.get("/api/v1/knowledge/analytics/top-chunks")
        assert response.status_code == 200
        assert response.json()["data"]["top_chunks"] == []

    def test_top_chunks_returns_500_on_error(self, app: FastAPI) -> None:
        quiet_client = TestClient(app, raise_server_exceptions=False)
        with patch.object(
            AnalyticsService, "top_chunks", side_effect=Exception("Query failed")
        ):
            response = quiet_client.get("/api/v1/knowledge/analytics/top-chunks")
        assert response.status_code == 500


# ═══════════════════════════════════════════════════════════════════
# GET /knowledge/analytics/agent-usage
# ═══════════════════════════════════════════════════════════════════


class TestAnalyticsAgentUsage:
    """GET /api/v1/knowledge/analytics/agent-usage — agent usage tracking."""

    def test_agent_usage_returns_list(self, client: TestClient) -> None:
        with patch.object(AnalyticsService, "agent_usage", return_value=SAMPLE_AGENT_USAGE):
            response = client.get("/api/v1/knowledge/analytics/agent-usage")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert len(body["data"]["agents"]) == 1
        assert body["data"]["total_agents"] == 1

    def test_agent_usage_includes_project_details(self, client: TestClient) -> None:
        with patch.object(AnalyticsService, "agent_usage", return_value=SAMPLE_AGENT_USAGE):
            response = client.get("/api/v1/knowledge/analytics/agent-usage")
        agent = response.json()["data"]["agents"][0]
        assert len(agent["projects"]) == 1
        assert agent["projects"][0]["project_name"] == "Test Project"
        assert agent["projects"][0]["packet_count"] == 3

    def test_agent_usage_empty(self, client: TestClient) -> None:
        empty = {"agents": [], "total_agents": 0, "total_projects_with_agents": 0}
        with patch.object(AnalyticsService, "agent_usage", return_value=empty):
            response = client.get("/api/v1/knowledge/analytics/agent-usage")
        assert response.status_code == 200
        assert response.json()["data"]["agents"] == []

    def test_agent_usage_delegates(self, client: TestClient) -> None:
        with patch.object(AnalyticsService, "agent_usage", return_value=SAMPLE_AGENT_USAGE) as mock:
            client.get("/api/v1/knowledge/analytics/agent-usage")
            mock.assert_called_once()

    def test_agent_usage_returns_500_on_error(self, app: FastAPI) -> None:
        quiet_client = TestClient(app, raise_server_exceptions=False)
        with patch.object(
            AnalyticsService, "agent_usage", side_effect=Exception("DB error")
        ):
            response = quiet_client.get("/api/v1/knowledge/analytics/agent-usage")
        assert response.status_code == 500


# ═══════════════════════════════════════════════════════════════════
# Routing integrity
# ═══════════════════════════════════════════════════════════════════


class TestAnalyticsRoutingIntegrity:
    """Verify all analytics routes are registered at expected paths."""

    def test_all_analytics_routes_in_openapi(self, client: TestClient) -> None:
        response = client.get("/openapi.json")
        assert response.status_code == 200
        paths = response.json().get("paths", {})
        analytics_paths = {p for p in paths if "knowledge/analytics" in p}

        assert "/api/v1/knowledge/analytics/overview" in analytics_paths
        assert "/api/v1/knowledge/analytics/time-series" in analytics_paths
        assert "/api/v1/knowledge/analytics/top-chunks" in analytics_paths
        assert "/api/v1/knowledge/analytics/agent-usage" in analytics_paths

    def test_analytics_routes_have_correct_methods(self, client: TestClient) -> None:
        paths = client.get("/openapi.json").json().get("paths", {})

        assert "get" in paths["/api/v1/knowledge/analytics/overview"]
        assert "get" in paths["/api/v1/knowledge/analytics/time-series"]
        assert "get" in paths["/api/v1/knowledge/analytics/top-chunks"]
        assert "get" in paths["/api/v1/knowledge/analytics/agent-usage"]
