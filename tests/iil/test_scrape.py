"""IIL Scrape — Integration Tests.

Tests the POST /scrape and GET /scrape API endpoints with mocked service layer.

Usage:
    cd "Backend Monorepo/Backend"
    uv run pytest tests/iil/test_scrape.py -v
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock


# =============================================================================
# POST /scrape Endpoint Tests
# =============================================================================


class TestScrapePostEndpoint:
    """Tests for POST /api/v1/iil/scrape"""

    def test_scrape_success(self, client, mock_iil_service, sample_scrape_response):
        """Scrape endpoint returns ScrapeResponse on success."""
        mock_iil_service.scrape = AsyncMock(return_value=sample_scrape_response)

        with patch("app.modules.iil.routes._get_service", return_value=mock_iil_service):
            resp = client.post(
                "/api/v1/iil/scrape",
                json={
                    "url": "http://example.com",
                    "extract_mode": "markdown",
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["url"] == "http://example.com"
        assert data["extraction_method"] == "http"
        assert "Test Page" in data["content_markdown"]
        mock_iil_service.scrape.assert_called_once()

    def test_scrape_with_js_required(self, client, mock_iil_service, sample_scrape_response):
        """Scrape endpoint passes js_required flag to service."""
        mock_iil_service.scrape = AsyncMock(return_value=sample_scrape_response)

        with patch("app.modules.iil.routes._get_service", return_value=mock_iil_service):
            resp = client.post(
                "/api/v1/iil/scrape",
                json={
                    "url": "http://example.com",
                    "extract_mode": "markdown",
                    "js_required": True,
                },
            )

        assert resp.status_code == 200
        call_kwargs = mock_iil_service.scrape.call_args
        assert call_kwargs[1]["js_required"] is True

    def test_scrape_with_max_chars(self, client, mock_iil_service, sample_scrape_response):
        """Scrape endpoint passes max_chars to service."""
        mock_iil_service.scrape = AsyncMock(return_value=sample_scrape_response)

        with patch("app.modules.iil.routes._get_service", return_value=mock_iil_service):
            resp = client.post(
                "/api/v1/iil/scrape",
                json={
                    "url": "http://example.com",
                    "extract_mode": "markdown",
                    "max_chars": 5000,
                },
            )

        assert resp.status_code == 200
        call_kwargs = mock_iil_service.scrape.call_args
        assert call_kwargs[1]["max_chars"] == 5000

    def test_scrape_with_screenshot(self, client, mock_iil_service, sample_scrape_response):
        """Scrape endpoint passes screenshot flag to service."""
        mock_iil_service.scrape = AsyncMock(return_value=sample_scrape_response)

        with patch("app.modules.iil.routes._get_service", return_value=mock_iil_service):
            resp = client.post(
                "/api/v1/iil/scrape",
                json={
                    "url": "http://example.com",
                    "extract_mode": "markdown",
                    "screenshot": True,
                },
            )

        assert resp.status_code == 200
        call_kwargs = mock_iil_service.scrape.call_args
        assert call_kwargs[1]["screenshot"] is True

    def test_scrape_with_bypass_cache(self, client, mock_iil_service, sample_scrape_response):
        """Scrape endpoint passes bypass_cache flag to service."""
        mock_iil_service.scrape = AsyncMock(return_value=sample_scrape_response)

        with patch("app.modules.iil.routes._get_service", return_value=mock_iil_service):
            resp = client.post(
                "/api/v1/iil/scrape",
                json={
                    "url": "http://example.com",
                    "extract_mode": "markdown",
                    "bypass_cache": True,
                },
            )

        assert resp.status_code == 200
        call_kwargs = mock_iil_service.scrape.call_args
        assert call_kwargs[1]["bypass_cache"] is True

    def test_scrape_service_error(self, client, mock_iil_service):
        """Scrape endpoint returns error response when service fails."""
        from common_lib.modules.iil.schemas import ScrapeResponse

        error_response = ScrapeResponse(
            url="http://example.com",
            final_url="http://example.com",
            extraction_method="http",
            error="Failed to fetch URL",
        )
        mock_iil_service.scrape = AsyncMock(return_value=error_response)

        with patch("app.modules.iil.routes._get_service", return_value=mock_iil_service):
            resp = client.post(
                "/api/v1/iil/scrape",
                json={"url": "http://example.com", "extract_mode": "markdown"},
            )

        # Route returns the response even with error (no explicit raise)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("error") == "Failed to fetch URL"

    def test_scrape_missing_url(self, client):
        """Scrape endpoint returns 422 when url is missing."""
        resp = client.post(
            "/api/v1/iil/scrape",
            json={"extract_mode": "markdown"},
        )
        assert resp.status_code == 422

    def test_scrape_default_extract_mode(self, client, mock_iil_service, sample_scrape_response):
        """Scrape endpoint defaults to markdown extract_mode."""
        mock_iil_service.scrape = AsyncMock(return_value=sample_scrape_response)

        with patch("app.modules.iil.routes._get_service", return_value=mock_iil_service):
            resp = client.post(
                "/api/v1/iil/scrape",
                json={"url": "http://example.com"},
            )

        assert resp.status_code == 200
        call_kwargs = mock_iil_service.scrape.call_args
        assert call_kwargs[1]["extract_mode"] == "markdown"

    def test_scrape_with_scroll_to_bottom(self, client, mock_iil_service, sample_scrape_response):
        """Scrape endpoint passes scroll_to_bottom flag."""
        mock_iil_service.scrape = AsyncMock(return_value=sample_scrape_response)

        with patch("app.modules.iil.routes._get_service", return_value=mock_iil_service):
            resp = client.post(
                "/api/v1/iil/scrape",
                json={
                    "url": "http://example.com",
                    "extract_mode": "markdown",
                    "scroll_to_bottom": True,
                },
            )

        assert resp.status_code == 200
        call_kwargs = mock_iil_service.scrape.call_args
        assert call_kwargs[1]["scroll_to_bottom"] is True


# =============================================================================
# GET /scrape Endpoint Tests
# =============================================================================


class TestScrapeGetEndpoint:
    """Tests for GET /api/v1/iil/scrape"""

    def test_scrape_get_success(self, client, mock_iil_service, sample_scrape_response):
        """GET scrape returns ScrapeResponse on success."""
        mock_iil_service.scrape = AsyncMock(return_value=sample_scrape_response)

        with patch("app.modules.iil.routes._get_service", return_value=mock_iil_service):
            resp = client.get(
                "/api/v1/iil/scrape?url=http://example.com&extract_mode=markdown"
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["url"] == "http://example.com"

    def test_scrape_get_defaults(self, client, mock_iil_service, sample_scrape_response):
        """GET scrape uses default extract_mode=markdown."""
        mock_iil_service.scrape = AsyncMock(return_value=sample_scrape_response)

        with patch("app.modules.iil.routes._get_service", return_value=mock_iil_service):
            resp = client.get("/api/v1/iil/scrape?url=http://example.com")

        assert resp.status_code == 200
        call_kwargs = mock_iil_service.scrape.call_args
        assert call_kwargs[1]["extract_mode"] == "markdown"

    def test_scrape_get_missing_url(self, client):
        """GET scrape returns 422 when url param is missing."""
        resp = client.get("/api/v1/iil/scrape")
        assert resp.status_code == 422
