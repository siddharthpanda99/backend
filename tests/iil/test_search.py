"""IIL Search — Integration Tests.

Tests the POST /search and GET /search API endpoints with mocked service layer.

Usage:
    cd "Backend Monorepo/Backend"
    uv run pytest tests/iil/test_search.py -v
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock


# =============================================================================
# POST /search Endpoint Tests
# =============================================================================


class TestSearchPostEndpoint:
    """Tests for POST /api/v1/iil/search"""

    def test_search_success(self, client, mock_iil_service, sample_search_result):
        """Search endpoint returns IILResult on success."""
        mock_iil_service.search = AsyncMock(return_value=sample_search_result)

        with patch("app.modules.iil.routes._get_service", return_value=mock_iil_service):
            resp = client.post(
                "/api/v1/iil/search",
                json={"query": "test query", "intent": "general", "n": 5},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "Test Title" in data["content"]
        assert len(data["results"]) == 1
        assert data["results"][0]["title"] == "Test Title"
        assert data["results"][0]["url"] == "http://example.com"
        assert data["provider_used"] == "test"

    def test_search_with_time_range(self, client, mock_iil_service, sample_search_result):
        """Search endpoint passes time_range to service."""
        mock_iil_service.search = AsyncMock(return_value=sample_search_result)

        with patch("app.modules.iil.routes._get_service", return_value=mock_iil_service):
            resp = client.post(
                "/api/v1/iil/search",
                json={"query": "news", "time_range": "week", "n": 10},
            )

        assert resp.status_code == 200
        call_kwargs = mock_iil_service.search.call_args
        assert call_kwargs[1]["time_range"] == "week"

    def test_search_with_providers(self, client, mock_iil_service, sample_search_result):
        """Search endpoint passes providers list to service."""
        mock_iil_service.search = AsyncMock(return_value=sample_search_result)

        with patch("app.modules.iil.routes._get_service", return_value=mock_iil_service):
            resp = client.post(
                "/api/v1/iil/search",
                json={"query": "test", "providers": ["google", "bing"]},
            )

        assert resp.status_code == 200
        call_kwargs = mock_iil_service.search.call_args
        assert call_kwargs[1]["providers"] == ["google", "bing"]

    def test_search_with_bypass_cache(self, client, mock_iil_service, sample_search_result):
        """Search endpoint passes bypass_cache flag to service."""
        mock_iil_service.search = AsyncMock(return_value=sample_search_result)

        with patch("app.modules.iil.routes._get_service", return_value=mock_iil_service):
            resp = client.post(
                "/api/v1/iil/search",
                json={"query": "test", "bypass_cache": True},
            )

        assert resp.status_code == 200
        call_kwargs = mock_iil_service.search.call_args
        assert call_kwargs[1]["bypass_cache"] is True

    def test_search_service_error(self, client, mock_iil_service):
        """Search endpoint returns 502 when service sets error."""
        from common_lib.modules.iil.schemas import IILResult

        error_result = IILResult(success=False, error="Search provider unavailable")
        mock_iil_service.search = AsyncMock(return_value=error_result)

        with patch("app.modules.iil.routes._get_service", return_value=mock_iil_service):
            resp = client.post(
                "/api/v1/iil/search",
                json={"query": "test"},
            )

        assert resp.status_code == 502
        body = resp.json()
        assert "Search provider unavailable" in body.get("message", "") or "Search provider unavailable" in str(body.get("detail", ""))

    def test_search_missing_query(self, client):
        """Search endpoint returns 422 when query is missing."""
        resp = client.post(
            "/api/v1/iil/search",
            json={"intent": "general"},
        )
        assert resp.status_code == 422

    def test_search_default_n(self, client, mock_iil_service, sample_search_result):
        """Search endpoint uses default n=10 when not provided."""
        mock_iil_service.search = AsyncMock(return_value=sample_search_result)

        with patch("app.modules.iil.routes._get_service", return_value=mock_iil_service):
            resp = client.post(
                "/api/v1/iil/search",
                json={"query": "test"},
            )

        assert resp.status_code == 200
        call_kwargs = mock_iil_service.search.call_args
        assert call_kwargs[1]["n"] == 10

    def test_search_empty_results(self, client, mock_iil_service):
        """Search endpoint handles empty results gracefully."""
        from common_lib.modules.iil.schemas import IILResult

        empty_result = IILResult(success=True, content="", results=[], provider_used="test")
        mock_iil_service.search = AsyncMock(return_value=empty_result)

        with patch("app.modules.iil.routes._get_service", return_value=mock_iil_service):
            resp = client.post(
                "/api/v1/iil/search",
                json={"query": "nonexistent"},
            )

        assert resp.status_code == 200
        assert resp.json()["results"] == []


# =============================================================================
# GET /search Endpoint Tests
# =============================================================================


class TestSearchGetEndpoint:
    """Tests for GET /api/v1/iil/search"""

    def test_search_get_success(self, client, mock_iil_service, sample_search_result):
        """GET search returns IILResult on success."""
        mock_iil_service.search = AsyncMock(return_value=sample_search_result)

        with patch("app.modules.iil.routes._get_service", return_value=mock_iil_service):
            resp = client.get("/api/v1/iil/search?q=test+query&intent=general&n=5")

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

    def test_search_get_defaults(self, client, mock_iil_service, sample_search_result):
        """GET search uses default values for optional params."""
        mock_iil_service.search = AsyncMock(return_value=sample_search_result)

        with patch("app.modules.iil.routes._get_service", return_value=mock_iil_service):
            resp = client.get("/api/v1/iil/search?q=test")

        assert resp.status_code == 200
        call_kwargs = mock_iil_service.search.call_args
        assert call_kwargs[1]["intent"] == "general"
        assert call_kwargs[1]["n"] == 10

    def test_search_get_with_time_range(self, client, mock_iil_service, sample_search_result):
        """GET search passes time_range query param."""
        mock_iil_service.search = AsyncMock(return_value=sample_search_result)

        with patch("app.modules.iil.routes._get_service", return_value=mock_iil_service):
            resp = client.get("/api/v1/iil/search?q=news&time_range=day")

        assert resp.status_code == 200
        call_kwargs = mock_iil_service.search.call_args
        assert call_kwargs[1]["time_range"] == "day"

    def test_search_get_missing_q(self, client):
        """GET search returns 422 when q param is missing."""
        resp = client.get("/api/v1/iil/search")
        assert resp.status_code == 422
