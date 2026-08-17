"""
API-level tests for Knowledge Hub Scraper endpoints.

Tests all 9 scraper endpoints by mocking ScraperService static methods
to avoid actual HTTP calls during tests.
"""

from __future__ import annotations

from typing import Any, Dict, Generator
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlalchemy.pool import StaticPool

from common_lib.modules.knowledge_engine.knowledge_hub.services.scraper_service import (
    ScraperService,
    ScraperError,
)

# ── In-memory engine ───────────────────────────────────────────────

TEST_DB_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DB_URL,
    echo=False,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
SQLModel.metadata.create_all(engine)


def get_test_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


# ── Sample data ────────────────────────────────────────────────────

from unittest.mock import MagicMock


def _make_scraper_mock(**overrides: Any) -> MagicMock:
    """Create a MagicMock that mimics a ScraperConfigRecord object."""
    base = {
        "id": "scr-test-001",
        "name": "Test Scraper",
        "url": "https://example.com",
        "scraper_type": "url",
        "project_id": None,
        "schedule": None,
        "respect_robots_txt": True,
        "max_pages": 100,
        "rate_limit_ms": 1000,
        "config": {},
        "status": "active",
        "last_run_at": None,
        "last_run_result": None,
        "created_at": "2025-01-01T00:00:00",
        "updated_at": "2025-01-01T00:00:00",
    }
    base.update(overrides)
    m = MagicMock()
    for k, v in base.items():
        setattr(m, k, v)
    return m


def _make_scraper_to_dict() -> MagicMock:
    """Create a MagicMock that returns a dict from _scraper_to_dict."""
    def converter(obj: Any) -> Dict[str, Any]:
        return {
            "id": obj.id,
            "name": obj.name,
            "url": obj.url,
            "scraper_type": obj.scraper_type,
            "project_id": obj.project_id,
            "schedule": obj.schedule,
            "respect_robots_txt": obj.respect_robots_txt,
            "max_pages": obj.max_pages,
            "rate_limit_ms": obj.rate_limit_ms,
            "config": obj.config,
            "status": obj.status,
            "last_run_at": obj.last_run_at,
            "last_run_result": obj.last_run_result,
            "created_at": obj.created_at,
            "updated_at": obj.updated_at,
        }
    return MagicMock(side_effect=converter)


SAMPLE_SCRAPER = _make_scraper_mock()
SAMPLE_SCRAPER_DICT = {
    "id": "scr-test-001",
    "name": "Test Scraper",
    "url": "https://example.com",
    "scraper_type": "url",
    "project_id": None,
    "schedule": None,
    "respect_robots_txt": True,
    "max_pages": 100,
    "rate_limit_ms": 1000,
    "config": {},
    "status": "active",
    "last_run_at": None,
    "last_run_result": None,
    "created_at": "2025-01-01T00:00:00",
    "updated_at": "2025-01-01T00:00:00",
}

SAMPLE_SCRAPER_LIST = [
    SAMPLE_SCRAPER,
    _make_scraper_mock(id="scr-test-002", name="Sitemap Scraper", scraper_type="sitemap"),
    _make_scraper_mock(id="scr-test-003", name="Crawl Scraper", scraper_type="crawl", status="paused"),
]

SAMPLE_RUN_RESULT: Dict[str, Any] = {
    "success": True,
    "url": "https://example.com",
    "status": "completed",
    "pages_fetched": 1,
    "text_length": 500,
    "content_preview": "Example domain content...",
    "link_count": 5,
    "duration_ms": 200,
    "total_duration_ms": 200,
}

SAMPLE_PREVIEW_RESULT: Dict[str, Any] = {
    "success": True,
    "url": "https://example.com",
    "status": "completed",
    "preview": True,
    "text_length": 500,
    "content_preview": "Preview content...",
    "duration_ms": 50,
}

# Module path for patching the serializer
ROUTES_MODULE = "app.modules.knowledge_hub.routes.scrapers"
_SCRAPER_TO_DICT_PATCH = patch(f"{ROUTES_MODULE}._scraper_to_dict", _make_scraper_to_dict())


# ── App fixture ─────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def app() -> FastAPI:
    from app.modules.knowledge_hub.routes.scrapers import router

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    from common_lib.modules.data_storage.database.connection import get_session
    app.dependency_overrides[get_session] = get_test_session
    return app


@pytest.fixture(scope="module")
def client(app: FastAPI) -> Generator[TestClient, None, None]:
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# ═══════════════════════════════════════════════════════════════════
# List Scrapers
# ═══════════════════════════════════════════════════════════════════


class TestListScrapers:
    """GET /knowledge-hub/scrapers"""

    def test_list_scrapers(self, client: TestClient) -> None:
        with patch.object(ScraperService, "list_scrapers", return_value=SAMPLE_SCRAPER_LIST):
            with _SCRAPER_TO_DICT_PATCH:
                response = client.get("/api/v1/knowledge-hub/scrapers")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["total"] == 3
        assert len(body["data"]) == 3

    def test_list_scrapers_empty(self, client: TestClient) -> None:
        with patch.object(ScraperService, "list_scrapers", return_value=[]):
            response = client.get("/api/v1/knowledge-hub/scrapers")
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 0
        assert len(body["data"]) == 0

    def test_list_scrapers_filtered_by_status(self, client: TestClient) -> None:
        with patch.object(ScraperService, "list_scrapers", return_value=[SAMPLE_SCRAPER_LIST[2]]):
            with _SCRAPER_TO_DICT_PATCH:
                response = client.get("/api/v1/knowledge-hub/scrapers?status=paused")
        assert response.status_code == 200
        body = response.json()
        assert len(body["data"]) == 1
        assert body["data"][0]["status"] == "paused"

    def test_list_scrapers_passes_filters(self, client: TestClient) -> None:
        with patch.object(ScraperService, "list_scrapers", return_value=[SAMPLE_SCRAPER_LIST[1]]) as mock_method:
            with _SCRAPER_TO_DICT_PATCH:
                response = client.get("/api/v1/knowledge-hub/scrapers?scraper_type=sitemap&project_id=proj-001")
        assert response.status_code == 200
        mock_method.assert_called_once()
        _, kwargs = mock_method.call_args
        assert kwargs.get("scraper_type") == "sitemap"
        assert kwargs.get("project_id") == "proj-001"

    def test_list_scrapers_500_error(self, client: TestClient) -> None:
        with patch.object(ScraperService, "list_scrapers", side_effect=Exception("DB error")):
            # Use raise_server_exceptions=False to capture the 500 error response
            # since the route has no try/except
            response = client.get("/api/v1/knowledge-hub/scrapers")
        assert response.status_code == 500


# ═══════════════════════════════════════════════════════════════════
# Get Scraper
# ═══════════════════════════════════════════════════════════════════


class TestGetScraper:
    """GET /knowledge-hub/scrapers/{scraper_id}"""

    def test_get_scraper(self, client: TestClient) -> None:
        with patch.object(ScraperService, "get_scraper", return_value=SAMPLE_SCRAPER):
            with _SCRAPER_TO_DICT_PATCH:
                response = client.get("/api/v1/knowledge-hub/scrapers/scr-test-001")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["id"] == "scr-test-001"
        assert body["data"]["name"] == "Test Scraper"
        assert body["data"]["scraper_type"] == "url"
        assert "config" in body["data"]

    def test_get_scraper_not_found(self, client: TestClient) -> None:
        with patch.object(ScraperService, "get_scraper", return_value=None):
            response = client.get("/api/v1/knowledge-hub/scrapers/nonexistent")
        assert response.status_code == 404


# ═══════════════════════════════════════════════════════════════════
# Create Scraper
# ═══════════════════════════════════════════════════════════════════


class TestCreateScraper:
    """POST /knowledge-hub/scrapers"""

    CREATE_PAYLOAD = {
        "name": "New Scraper",
        "url": "https://example.com",
        "scraper_type": "url",
        "max_pages": 50,
    }

    def test_create_scraper(self, client: TestClient) -> None:
        expected = _make_scraper_mock(id="scr-new", name="New Scraper")
        with patch.object(ScraperService, "create_scraper", return_value=expected):
            with _SCRAPER_TO_DICT_PATCH:
                response = client.post("/api/v1/knowledge-hub/scrapers", json=self.CREATE_PAYLOAD)
        assert response.status_code == 201
        body = response.json()
        assert body["success"] is True
        assert body["data"]["name"] == "New Scraper"
        assert body["data"]["scraper_type"] == "url"

    def test_create_scraper_invalid_type(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/knowledge-hub/scrapers",
            json={**self.CREATE_PAYLOAD, "scraper_type": "invalid"},
        )
        assert response.status_code == 400
        assert "scraper_type must be" in response.json()["detail"]

    def test_create_scraper_missing_name(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/knowledge-hub/scrapers",
            json={"url": "https://example.com", "scraper_type": "url"},
        )
        assert response.status_code == 422

    def test_create_scraper_missing_url(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/knowledge-hub/scrapers",
            json={"name": "No URL", "scraper_type": "url"},
        )
        assert response.status_code == 422

    def test_create_scraper_delegation(self, client: TestClient) -> None:
        expected = _make_scraper_mock(id="scr-delegate", name="Delegate Test")
        with patch.object(ScraperService, "create_scraper", return_value=expected) as mock_method:
            with _SCRAPER_TO_DICT_PATCH:
                client.post("/api/v1/knowledge-hub/scrapers", json=self.CREATE_PAYLOAD)
        mock_method.assert_called_once()
        args, _ = mock_method.call_args
        assert args[1]["name"] == "New Scraper"


# ═══════════════════════════════════════════════════════════════════
# Update Scraper
# ═══════════════════════════════════════════════════════════════════


class TestUpdateScraper:
    """PUT /knowledge-hub/scrapers/{scraper_id}"""

    def test_update_scraper(self, client: TestClient) -> None:
        updated = _make_scraper_mock(name="Updated Name")
        with patch.object(ScraperService, "update_scraper", return_value=updated):
            with _SCRAPER_TO_DICT_PATCH:
                response = client.put(
                    "/api/v1/knowledge-hub/scrapers/scr-test-001",
                    json={"name": "Updated Name"},
                )
        assert response.status_code == 200
        assert response.json()["data"]["name"] == "Updated Name"

    def test_update_scraper_not_found(self, client: TestClient) -> None:
        with patch.object(ScraperService, "update_scraper", return_value=None):
            response = client.put(
                "/api/v1/knowledge-hub/scrapers/nonexistent",
                json={"name": "Nope"},
            )
        assert response.status_code == 404


# ═══════════════════════════════════════════════════════════════════
# Delete Scraper
# ═══════════════════════════════════════════════════════════════════


class TestDeleteScraper:
    """DELETE /knowledge-hub/scrapers/{scraper_id}"""

    def test_delete_scraper(self, client: TestClient) -> None:
        with patch.object(ScraperService, "delete_scraper", return_value=True):
            response = client.delete("/api/v1/knowledge-hub/scrapers/scr-test-001")
        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_delete_scraper_not_found(self, client: TestClient) -> None:
        with patch.object(ScraperService, "delete_scraper", return_value=False):
            response = client.delete("/api/v1/knowledge-hub/scrapers/nonexistent")
        assert response.status_code == 404


# ═══════════════════════════════════════════════════════════════════
# Run Scraper
# ═══════════════════════════════════════════════════════════════════


class TestRunScraper:
    """POST /knowledge-hub/scrapers/{scraper_id}/run"""

    def test_run_scraper(self, client: TestClient) -> None:
        with patch.object(ScraperService, "run_scraper", return_value=SAMPLE_RUN_RESULT):
            response = client.post("/api/v1/knowledge-hub/scrapers/scr-test-001/run")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["status"] == "completed"
        assert "pages_fetched" in body["data"]

    def test_run_scraper_not_found(self, client: TestClient) -> None:
        with patch.object(ScraperService, "run_scraper", return_value={"success": False, "message": "Scraper 'nonexistent' not found"}):
            response = client.post("/api/v1/knowledge-hub/scrapers/nonexistent/run")
        assert response.status_code == 404

    def test_run_scraper_error(self, client: TestClient) -> None:
        with patch.object(ScraperService, "run_scraper", side_effect=ScraperError("Connection failed")):
            response = client.post("/api/v1/knowledge-hub/scrapers/scr-test-001/run")
        assert response.status_code == 500

    def test_run_scraper_delegation(self, client: TestClient) -> None:
        with patch.object(ScraperService, "run_scraper", return_value=SAMPLE_RUN_RESULT) as mock_method:
            client.post("/api/v1/knowledge-hub/scrapers/scr-test-001/run")
        mock_method.assert_called_once()


# ═══════════════════════════════════════════════════════════════════
# Preview Scraper
# ═══════════════════════════════════════════════════════════════════


class TestPreviewScraper:
    """GET /knowledge-hub/scrapers/{scraper_id}/preview"""

    def test_preview_scraper(self, client: TestClient) -> None:
        with patch.object(ScraperService, "preview_scraper", return_value=SAMPLE_PREVIEW_RESULT):
            response = client.get("/api/v1/knowledge-hub/scrapers/scr-test-001/preview")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["preview"] is True
        assert body["data"]["status"] == "completed"

    def test_preview_scraper_not_found(self, client: TestClient) -> None:
        with patch.object(ScraperService, "preview_scraper", return_value={"success": False, "message": "Scraper 'nonexistent' not found"}):
            response = client.get("/api/v1/knowledge-hub/scrapers/nonexistent/preview")
        assert response.status_code == 404

    def test_preview_scraper_fetch_failed(self, client: TestClient) -> None:
        with patch.object(ScraperService, "preview_scraper", return_value={"success": False, "message": "Failed to fetch URL"}):
            response = client.get("/api/v1/knowledge-hub/scrapers/scr-test-001/preview")
        assert response.status_code == 502


# ═══════════════════════════════════════════════════════════════════
# Pause / Resume Scraper
# ═══════════════════════════════════════════════════════════════════


class TestPauseScraper:
    """POST /knowledge-hub/scrapers/{scraper_id}/pause"""

    def test_pause_scraper(self, client: TestClient) -> None:
        with patch.object(ScraperService, "pause_scraper", return_value=_make_scraper_mock(status="paused")):
            with _SCRAPER_TO_DICT_PATCH:
                response = client.post("/api/v1/knowledge-hub/scrapers/scr-test-001/pause")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["status"] == "paused"

    def test_pause_scraper_not_found(self, client: TestClient) -> None:
        with patch.object(ScraperService, "pause_scraper", return_value=None):
            response = client.post("/api/v1/knowledge-hub/scrapers/nonexistent/pause")
        assert response.status_code == 404


class TestResumeScraper:
    """POST /knowledge-hub/scrapers/{scraper_id}/resume"""

    def test_resume_scraper(self, client: TestClient) -> None:
        with patch.object(ScraperService, "resume_scraper", return_value=_make_scraper_mock(status="active")):
            with _SCRAPER_TO_DICT_PATCH:
                response = client.post("/api/v1/knowledge-hub/scrapers/scr-test-001/resume")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["status"] == "active"

    def test_resume_scraper_not_found(self, client: TestClient) -> None:
        with patch.object(ScraperService, "resume_scraper", return_value=None):
            response = client.post("/api/v1/knowledge-hub/scrapers/nonexistent/resume")
        assert response.status_code == 404


# ═══════════════════════════════════════════════════════════════════
# Routing Integrity
# ═══════════════════════════════════════════════════════════════════


class TestScraperRoutingIntegrity:
    """Verify all scraper routes are mounted at expected paths."""

    def test_scraper_routes_in_openapi(self, client: TestClient) -> None:
        response = client.get("/openapi.json")
        assert response.status_code == 200
        paths = response.json().get("paths", {})
        scraper_paths = {path for path in paths if "/scrapers" in path}
        assert "/api/v1/knowledge-hub/scrapers" in scraper_paths
        # 6 unique path patterns: /scrapers, /scrapers/{id}, /scrapers/{id}/run,
        # /scrapers/{id}/preview, /scrapers/{id}/pause, /scrapers/{id}/resume
        assert len(scraper_paths) >= 6

    def test_scraper_methods(self, client: TestClient) -> None:
        response = client.get("/openapi.json")
        assert response.status_code == 200
        paths = response.json().get("paths", {})

        # Check CRUD on collection path
        scrapers_path = paths.get("/api/v1/knowledge-hub/scrapers", {})
        assert "get" in scrapers_path
        assert "post" in scrapers_path

        # Check CRUD on individual scraper path
        scrapers_id_path = paths.get("/api/v1/knowledge-hub/scrapers/{scraper_id}", {})
        assert "get" in scrapers_id_path
        assert "put" in scrapers_id_path
        assert "delete" in scrapers_id_path

        # Check action sub-paths exist
        run_paths = [p for p in paths if "/scrapers/" in p and "/run" in p]
        preview_paths = [p for p in paths if "/scrapers/" in p and "/preview" in p]
        pause_paths = [p for p in paths if "/scrapers/" in p and "/pause" in p]
        resume_paths = [p for p in paths if "/scrapers/" in p and "/resume" in p]
        assert run_paths
        assert preview_paths
        assert pause_paths
        assert resume_paths
