"""IIL Integration Test Fixtures — FastAPI test client and mock helpers."""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Bootstrap paths
BACKEND_ROOT = Path(__file__).parent.parent.parent.resolve()
PROJECT_ROOT = BACKEND_ROOT.parent
sys.path.insert(0, str(PROJECT_ROOT / "Python Libs" / "common_lib" / "src"))
sys.path.insert(0, str(BACKEND_ROOT))

# ── FastAPI TestClient ────────────────────────────────────────────

@pytest.fixture(scope="session")
def app():
    """Import and configure the FastAPI application."""
    from app.main import app as _app
    return _app


@pytest.fixture(scope="session")
def client(app):
    """Synchronous test client for the FastAPI app."""
    from fastapi.testclient import TestClient
    return TestClient(app)


@pytest.fixture
def mock_iil_service():
    """Mock IILService with all async methods stubbed."""
    service = MagicMock()
    service.search = AsyncMock()
    service.scrape = AsyncMock()
    service.research = AsyncMock()
    service.verify_fact = AsyncMock()
    service.ingest = AsyncMock()
    service.browse = AsyncMock()
    service.ocr_extract = AsyncMock()
    service.check_robots = AsyncMock()
    service.check_robots_before_fetch = AsyncMock()
    service.get_cache_stats = MagicMock()
    service.clear_cache = MagicMock()
    service.search_knowledge = MagicMock()
    service.get_knowledge_stats = MagicMock()
    return service


@pytest.fixture
def mock_analytics():
    """Mock analytics tracker."""
    analytics = MagicMock()
    analytics.track_request = MagicMock()
    analytics.track_cache_event = MagicMock()
    analytics.track_error = MagicMock()
    analytics.get_request_volume = MagicMock(return_value=[])
    analytics.get_total_requests = MagicMock(return_value=0)
    analytics.get_operations_breakdown = MagicMock(return_value={})
    analytics.get_cache_hit_rate_data = MagicMock(return_value=[])
    analytics.get_overall_cache_hit_rate = MagicMock(return_value=0.0)
    analytics.get_total_errors = MagicMock(return_value=0)
    analytics.get_error_rate = MagicMock(return_value=0.0)
    analytics.get_retention_days = MagicMock(return_value=30)
    analytics.set_retention_days = MagicMock()
    analytics.reset = MagicMock()
    return analytics


@pytest.fixture
def sample_search_result():
    """Sample IILResult for search tests."""
    from common_lib.modules.iil.schemas import IILResult, SearchResultItem

    return IILResult(
        success=True,
        content="1. [Test Title](http://example.com)\n   Test snippet content",
        results=[
            SearchResultItem(
                title="Test Title",
                url="http://example.com",
                snippet="Test snippet content",
                source="http://example.com",
                score=0.95,
                rrf_score=0.8,
            )
        ],
        citations=["http://example.com"],
        provider_used="test",
        duration_ms=150.0,
    )


@pytest.fixture
def sample_scrape_response():
    """Sample ScrapeResponse for scrape tests."""
    from common_lib.modules.iil.schemas import ScrapeResponse

    return ScrapeResponse(
        url="http://example.com",
        final_url="http://example.com",
        content_markdown="# Test Page\n\nThis is test content.",
        title="Test Page",
        extraction_method="http",
        cache_hit=False,
    )


@pytest.fixture
def sample_browser_response():
    """Sample BrowserResponse for browse tests — uses MagicMock to avoid Pydantic validation."""
    from common_lib.modules.iil.schemas import BrowserResponse, BrowserStepResult

    steps = [
        BrowserStepResult(step=1, action="navigate", url="http://example.com", result="OK"),
        BrowserStepResult(step=2, action="click", url="http://example.com", result="Clicked"),
        BrowserStepResult(step=3, action="done", url="http://example.com", result="Success"),
    ]
    return BrowserResponse(
        success=True,
        final_url="http://example.com",
        final_answer="Successfully navigated to example.com",
        steps=steps,
        total_duration_ms=2500.0,
    )


@pytest.fixture
def sample_robots_result():
    """Sample robots check result dict."""
    return {
        "allowed": True,
        "url": "http://example.com/page",
        "user_agent": "IIL-Bot/1.0",
        "crawl_delay_seconds": None,
        "sitemaps": ["http://example.com/sitemap.xml"],
        "blocked_reason": None,
    }


@pytest.fixture
def iil_base_url():
    """Base URL for IIL API endpoints."""
    return "/api/v1/iil"
