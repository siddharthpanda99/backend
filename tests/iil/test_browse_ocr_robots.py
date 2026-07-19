"""IIL Browse, OCR, and Robots Checker — Integration Tests.

Tests the /browse, /ocr, and /robots-check API endpoints with mocked service layer.
Uses FastAPI TestClient for synchronous endpoint testing.

Usage:
    cd "Backend Monorepo/Backend"
    uv run pytest tests/iil/test_browse_ocr_robots.py -v
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock


# =============================================================================
# /browse Endpoint Tests
# =============================================================================


class TestBrowseEndpoint:
    """Tests for POST /api/v1/iil/browse"""

    def test_browse_success(self, client, mock_iil_service, sample_browser_response):
        """Browse endpoint returns BrowserResponse on success."""
        mock_iil_service.browse = AsyncMock(return_value=sample_browser_response)

        with patch("app.modules.iil.routes._get_service", return_value=mock_iil_service):
            resp = client.post(
                "/api/v1/iil/browse",
                json={
                    "task": "Navigate to example.com and click the header",
                    "start_url": "http://example.com",
                    "max_steps": 10,
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["final_url"] == "http://example.com"
        assert data["final_answer"] == "Successfully navigated to example.com"
        assert len(data["steps"]) == 3
        mock_iil_service.browse.assert_called_once_with(
            task="Navigate to example.com and click the header",
            start_url="http://example.com",
            max_steps=10,
        )

    def test_browse_service_error(self, client, mock_iil_service):
        """Browse endpoint returns 502 when service raises an error."""
        from common_lib.modules.iil.schemas import BrowserResponse

        error_response = BrowserResponse(
            success=False,
            final_url="http://example.com",
            error="Browser not available on server",
        )
        mock_iil_service.browse = AsyncMock(return_value=error_response)

        with patch("app.modules.iil.routes._get_service", return_value=mock_iil_service):
            resp = client.post(
                "/api/v1/iil/browse",
                json={
                    "task": "Navigate somewhere",
                    "start_url": "http://example.com",
                },
            )

        assert resp.status_code == 502
        # App uses custom http_exception_handler → format: {error, message, module, detail}
        body = resp.json()
        assert "Browser not available" in body.get("message", "") or "Browser not available" in str(body.get("detail", ""))

    def test_browse_missing_task(self, client):
        """Browse endpoint returns 422 when task is missing."""
        resp = client.post(
            "/api/v1/iil/browse",
            json={"start_url": "http://example.com"},
        )
        assert resp.status_code == 422

    def test_browse_missing_start_url(self, client):
        """Browse endpoint returns 422 when start_url is missing."""
        resp = client.post(
            "/api/v1/iil/browse",
            json={"task": "Do something"},
        )
        assert resp.status_code == 422

    def test_browse_default_max_steps(self, client, mock_iil_service, sample_browser_response):
        """Browse endpoint uses default max_steps=20 when not provided."""
        mock_iil_service.browse = AsyncMock(return_value=sample_browser_response)

        with patch("app.modules.iil.routes._get_service", return_value=mock_iil_service):
            resp = client.post(
                "/api/v1/iil/browse",
                json={
                    "task": "Simple task",
                    "start_url": "http://example.com",
                },
            )

        assert resp.status_code == 200
        call_kwargs = mock_iil_service.browse.call_args
        assert call_kwargs[1]["max_steps"] == 20

    def test_browse_empty_steps(self, client, mock_iil_service):
        """Browse endpoint handles response with no steps gracefully."""
        from common_lib.modules.iil.schemas import BrowserResponse

        empty_response = BrowserResponse(
            success=True,
            final_url="http://example.com",
            final_answer="Nothing to do",
            steps=[],
            total_duration_ms=100.0,
        )
        mock_iil_service.browse = AsyncMock(return_value=empty_response)

        with patch("app.modules.iil.routes._get_service", return_value=mock_iil_service):
            resp = client.post(
                "/api/v1/iil/browse",
                json={"task": "Quick check", "start_url": "http://example.com"},
            )

        assert resp.status_code == 200
        assert resp.json()["steps"] == []


# =============================================================================
# /ocr Endpoint Tests
# =============================================================================


class TestOCREndpoint:
    """Tests for POST /api/v1/iil/ocr"""

    def test_ocr_success(self, client, mock_iil_service, sample_scrape_response):
        """OCR endpoint returns ScrapeResponse with extracted text."""
        mock_iil_service.ocr_extract = AsyncMock(return_value=sample_scrape_response)

        with patch("app.modules.iil.routes._get_service", return_value=mock_iil_service):
            resp = client.post(
                "/api/v1/iil/ocr",
                json={
                    "url": "http://example.com/image.png",
                    "language": "eng",
                    "max_chars": 50000,
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        # sample_scrape_response fixture has url="http://example.com" — mock passes it through
        assert data["url"] == "http://example.com"
        assert data["extraction_method"] == "http"
        assert "Test Page" in data["content_markdown"]
        mock_iil_service.ocr_extract.assert_called_once_with(
            url="http://example.com/image.png",
            language="eng",
            max_chars=50000,
        )

    def test_ocr_service_error(self, client, mock_iil_service):
        """OCR endpoint returns 502 when service raises an error."""
        from common_lib.modules.iil.schemas import ScrapeResponse

        error_response = ScrapeResponse(
            url="http://example.com/image.png",
            final_url="http://example.com/image.png",
            extraction_method="ocr",
            error="OCR backend not available",
        )
        mock_iil_service.ocr_extract = AsyncMock(return_value=error_response)

        with patch("app.modules.iil.routes._get_service", return_value=mock_iil_service):
            resp = client.post(
                "/api/v1/iil/ocr",
                json={"url": "http://example.com/image.png"},
            )

        assert resp.status_code == 502
        # App uses custom http_exception_handler → format: {error, message, module, detail}
        body = resp.json()
        assert "OCR backend not available" in body.get("message", "") or "OCR backend not available" in str(body.get("detail", ""))

    def test_ocr_missing_url(self, client):
        """OCR endpoint returns 422 when url is missing."""
        resp = client.post(
            "/api/v1/iil/ocr",
            json={"language": "eng"},
        )
        assert resp.status_code == 422

    def test_ocr_default_language(self, client, mock_iil_service, sample_scrape_response):
        """OCR endpoint defaults to English when language not provided."""
        mock_iil_service.ocr_extract = AsyncMock(return_value=sample_scrape_response)

        with patch("app.modules.iil.routes._get_service", return_value=mock_iil_service):
            resp = client.post(
                "/api/v1/iil/ocr",
                json={"url": "http://example.com/doc.pdf"},
            )

        assert resp.status_code == 200
        call_kwargs = mock_iil_service.ocr_extract.call_args
        assert call_kwargs[1]["language"] == "eng"

    def test_ocr_default_max_chars(self, client, mock_iil_service, sample_scrape_response):
        """OCR endpoint defaults max_chars to 50000 when not provided."""
        mock_iil_service.ocr_extract = AsyncMock(return_value=sample_scrape_response)

        with patch("app.modules.iil.routes._get_service", return_value=mock_iil_service):
            resp = client.post(
                "/api/v1/iil/ocr",
                json={"url": "http://example.com/image.png"},
            )

        assert resp.status_code == 200
        call_kwargs = mock_iil_service.ocr_extract.call_args
        assert call_kwargs[1]["max_chars"] == 50000

    def test_ocr_language_variants(self, client, mock_iil_service, sample_scrape_response):
        """OCR endpoint accepts different language codes."""
        mock_iil_service.ocr_extract = AsyncMock(return_value=sample_scrape_response)

        for lang in ["eng", "fra", "deu", "jpn", "chi_sim"]:
            with patch("app.modules.iil.routes._get_service", return_value=mock_iil_service):
                resp = client.post(
                    "/api/v1/iil/ocr",
                    json={"url": "http://example.com/img.png", "language": lang},
                )
                assert resp.status_code == 200
                call_kwargs = mock_iil_service.ocr_extract.call_args
                assert call_kwargs[1]["language"] == lang

    def test_ocr_max_chars_validation(self, client):
        """OCR endpoint rejects max_chars outside valid range."""
        # Too low
        resp = client.post(
            "/api/v1/iil/ocr",
            json={"url": "http://example.com/img.png", "max_chars": 50},
        )
        assert resp.status_code == 422

        # Too high
        resp = client.post(
            "/api/v1/iil/ocr",
            json={"url": "http://example.com/img.png", "max_chars": 600000},
        )
        assert resp.status_code == 422

    def test_ocr_pdf_url(self, client, mock_iil_service, sample_scrape_response):
        """OCR endpoint handles PDF URLs."""
        mock_iil_service.ocr_extract = AsyncMock(return_value=sample_scrape_response)

        with patch("app.modules.iil.routes._get_service", return_value=mock_iil_service):
            resp = client.post(
                "/api/v1/iil/ocr",
                json={"url": "http://example.com/scanned.pdf", "language": "eng"},
            )

        assert resp.status_code == 200
        call_kwargs = mock_iil_service.ocr_extract.call_args
        assert call_kwargs[1]["url"] == "http://example.com/scanned.pdf"


# =============================================================================
# /robots-check Endpoint Tests
# =============================================================================


class TestRobotsCheckEndpoint:
    """Tests for POST /api/v1/iil/robots-check"""

    def test_robots_check_success(self, client, mock_iil_service, sample_robots_result):
        """Robots check returns allowed=true for crawlable URLs."""
        mock_iil_service.check_robots = AsyncMock(return_value=sample_robots_result)

        with patch("app.modules.iil.routes._get_service", return_value=mock_iil_service):
            resp = client.post(
                "/api/v1/iil/robots-check",
                json={
                    "url": "http://example.com/page",
                    "user_agent": "IIL-Bot/1.0",
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["allowed"] is True
        assert data["url"] == "http://example.com/page"
        assert data["user_agent"] == "IIL-Bot/1.0"
        assert data["sitemaps"] == ["http://example.com/sitemap.xml"]
        assert data["blocked_reason"] is None
        mock_iil_service.check_robots.assert_called_once_with(
            url="http://example.com/page",
            user_agent="IIL-Bot/1.0",
        )

    def test_robots_check_blocked(self, client, mock_iil_service):
        """Robots check returns allowed=false for disallowed URLs."""
        blocked_result = {
            "allowed": False,
            "url": "http://example.com/admin",
            "user_agent": "IIL-Bot/1.0",
            "crawl_delay_seconds": None,
            "sitemaps": [],
            "blocked_reason": "Blocked by robots.txt: /admin",
        }
        mock_iil_service.check_robots = AsyncMock(return_value=blocked_result)

        with patch("app.modules.iil.routes._get_service", return_value=mock_iil_service):
            resp = client.post(
                "/api/v1/iil/robots-check",
                json={"url": "http://example.com/admin"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["allowed"] is False
        assert "Blocked by robots.txt" in data["blocked_reason"]

    def test_robots_check_missing_url(self, client):
        """Robots check returns 422 when url is missing."""
        resp = client.post(
            "/api/v1/iil/robots-check",
            json={"user_agent": "TestBot/1.0"},
        )
        assert resp.status_code == 422

    def test_robots_check_default_user_agent(self, client, mock_iil_service, sample_robots_result):
        """Robots check defaults user_agent to IIL-Bot/1.0."""
        mock_iil_service.check_robots = AsyncMock(return_value=sample_robots_result)

        with patch("app.modules.iil.routes._get_service", return_value=mock_iil_service):
            resp = client.post(
                "/api/v1/iil/robots-check",
                json={"url": "http://example.com/page"},
            )

        assert resp.status_code == 200
        call_kwargs = mock_iil_service.check_robots.call_args
        assert call_kwargs[1]["user_agent"] == "IIL-Bot/1.0"

    def test_robots_check_custom_user_agent(self, client, mock_iil_service, sample_robots_result):
        """Robots check accepts custom user agent strings."""
        mock_iil_service.check_robots = AsyncMock(return_value=sample_robots_result)

        with patch("app.modules.iil.routes._get_service", return_value=mock_iil_service):
            resp = client.post(
                "/api/v1/iil/robots-check",
                json={
                    "url": "http://example.com/page",
                    "user_agent": "Mozilla/5.0 (compatible; MyBot/1.0)",
                },
            )

        assert resp.status_code == 200
        call_kwargs = mock_iil_service.check_robots.call_args
        assert call_kwargs[1]["user_agent"] == "Mozilla/5.0 (compatible; MyBot/1.0)"

    def test_robots_check_with_crawl_delay(self, client, mock_iil_service):
        """Robots check returns crawl delay when specified."""
        result_with_delay = {
            "allowed": True,
            "url": "http://slow-site.com/page",
            "user_agent": "IIL-Bot/1.0",
            "crawl_delay_seconds": 5.0,
            "sitemaps": [],
            "blocked_reason": None,
        }
        mock_iil_service.check_robots = AsyncMock(return_value=result_with_delay)

        with patch("app.modules.iil.routes._get_service", return_value=mock_iil_service):
            resp = client.post(
                "/api/v1/iil/robots-check",
                json={"url": "http://slow-site.com/page"},
            )

        assert resp.status_code == 200
        assert resp.json()["crawl_delay_seconds"] == 5.0

    def test_robots_check_with_multiple_sitemaps(self, client, mock_iil_service):
        """Robots check returns all sitemaps from robots.txt."""
        result_multi_sitemap = {
            "allowed": True,
            "url": "http://example.com/blog/post",
            "user_agent": "IIL-Bot/1.0",
            "crawl_delay_seconds": None,
            "sitemaps": [
                "http://example.com/sitemap.xml",
                "http://example.com/sitemap-news.xml",
                "http://example.com/sitemap-images.xml",
            ],
            "blocked_reason": None,
        }
        mock_iil_service.check_robots = AsyncMock(return_value=result_multi_sitemap)

        with patch("app.modules.iil.routes._get_service", return_value=mock_iil_service):
            resp = client.post(
                "/api/v1/iil/robots-check",
                json={"url": "http://example.com/blog/post"},
            )

        assert resp.status_code == 200
        assert len(resp.json()["sitemaps"]) == 3

    def test_robots_check_no_robots_txt(self, client, mock_iil_service):
        """Robots check handles sites with no robots.txt."""
        no_robots_result = {
            "allowed": True,
            "url": "http://no-robots.com/page",
            "user_agent": "IIL-Bot/1.0",
            "crawl_delay_seconds": None,
            "sitemaps": [],
            "blocked_reason": None,
        }
        mock_iil_service.check_robots = AsyncMock(return_value=no_robots_result)

        with patch("app.modules.iil.routes._get_service", return_value=mock_iil_service):
            resp = client.post(
                "/api/v1/iil/robots-check",
                json={"url": "http://no-robots.com/page"},
            )

        assert resp.status_code == 200
        assert resp.json()["allowed"] is True
        assert resp.json()["sitemaps"] == []


# =============================================================================
# Cross-Endpoint Integration Tests
# =============================================================================


class TestCrossEndpointIntegration:
    """Tests that verify interactions between multiple IIL endpoints."""

    def test_browse_then_robots_check_flow(
        self, client, mock_iil_service, sample_browser_response, sample_robots_result
    ):
        """Simulate a browse→robots-check workflow."""
        mock_iil_service.check_robots = AsyncMock(return_value=sample_robots_result)
        mock_iil_service.browse = AsyncMock(return_value=sample_browser_response)

        with patch("app.modules.iil.routes._get_service", return_value=mock_iil_service):
            # Step 1: Check robots.txt before browsing
            robots_resp = client.post(
                "/api/v1/iil/robots-check",
                json={"url": "http://example.com"},
            )
            assert robots_resp.status_code == 200
            assert robots_resp.json()["allowed"] is True

            # Step 2: Browse the site
            browse_resp = client.post(
                "/api/v1/iil/browse",
                json={"task": "Get page title", "start_url": "http://example.com"},
            )
            assert browse_resp.status_code == 200
            assert browse_resp.json()["success"] is True

    def test_ocr_then_scrape_flow(
        self, client, mock_iil_service, sample_scrape_response
    ):
        """Simulate an OCR→scrape workflow for PDF processing."""
        mock_iil_service.scrape = AsyncMock(return_value=sample_scrape_response)
        mock_iil_service.ocr_extract = AsyncMock(return_value=sample_scrape_response)

        with patch("app.modules.iil.routes._get_service", return_value=mock_iil_service):
            # Step 1: Scrape the PDF page
            scrape_resp = client.post(
                "/api/v1/iil/scrape",
                json={"url": "http://example.com/docs", "extract_mode": "markdown"},
            )
            assert scrape_resp.status_code == 200

            # Step 2: OCR a scanned image from the page
            ocr_resp = client.post(
                "/api/v1/iil/ocr",
                json={"url": "http://example.com/scanned.png"},
            )
            assert ocr_resp.status_code == 200

    def test_health_endpoint(self, client):
        """Health endpoint returns status."""
        resp = client.get("/api/v1/iil/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["module"] == "Internet Intelligence Layer"

    def test_analytics_endpoint(self, client, mock_analytics):
        """Analytics endpoint returns metrics data."""
        with patch("app.modules.iil.routes._get_analytics", return_value=mock_analytics):
            resp = client.get("/api/v1/iil/analytics?hours=24")

        assert resp.status_code == 200
        data = resp.json()
        assert "data_points" in data
        assert "total_tracked" in data
        assert "operations_total" in data

    def test_cache_stats_endpoint(self, client, mock_iil_service):
        """Cache stats endpoint returns cache information."""
        from common_lib.modules.iil.schemas import CacheStats

        mock_iil_service.get_cache_stats.return_value = CacheStats()
        mock_analytics = MagicMock()

        with patch("app.modules.iil.routes._get_service", return_value=mock_iil_service), \
             patch("app.modules.iil.routes._get_analytics", return_value=mock_analytics):
            resp = client.get("/api/v1/iil/cache/stats")

        assert resp.status_code == 200
        data = resp.json()
        assert "total_entries" in data
