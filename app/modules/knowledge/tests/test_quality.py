"""
API-level tests for Knowledge Quality endpoints.

Verifies that all /knowledge/quality/* endpoints correctly delegate to
the QualityService, handle edge cases, and return expected response shapes.

Uses sync TestClient with mocked dependencies. External dependencies are
patched at the route module path.

Endpoints tested:
    POST /knowledge/quality/archive-stale        — Bulk archive stale chunks
    POST /knowledge/quality/reembed              — Bulk re-embed low-confidence chunks
    GET  /knowledge/quality/recommendations       — Generate quality improvement recommendations
    POST /knowledge/quality/run-validation        — Run full validation scan

Usage:
    cd Backend Monorepo/Backend
    uv run python -m pytest app/modules/knowledge/tests/test_quality.py -v
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.knowledge.routes import router as knowledge_router

# ── Sample data ──────────────────────────────────────────────────────────

SAMPLE_ARCHIVE_RESULT = {
    "total_stale": 3,
    "archived": 3,
    "dry_run": False,
    "skipped": 0,
    "by_domain": {
        "news": {"stale": 1, "archived": 1},
        "financial": {"stale": 1, "archived": 1},
        "general": {"stale": 1, "archived": 1},
    },
}

SAMPLE_ARCHIVE_DRY_RUN_RESULT = {
    "total_stale": 2,
    "archived": 0,
    "dry_run": True,
    "skipped": 0,
    "by_domain": {
        "news": {"stale": 1, "archived": 0},
        "financial": {"stale": 1, "archived": 0},
    },
}

SAMPLE_REEMBED_RESULT = {
    "total_low_confidence": 2,
    "reembedded": 2,
    "missing_embedding": 1,
    "dry_run": False,
    "errors": 0,
}

SAMPLE_REEMBED_DRY_RUN_RESULT = {
    "total_low_confidence": 1,
    "reembedded": 0,
    "missing_embedding": 1,
    "dry_run": True,
    "errors": 0,
}

SAMPLE_RECOMMENDATIONS = [
    {
        "title": "Re-embed low-confidence chunks",
        "description": "3 chunks have confidence below 0.6",
        "severity": "warning",
        "suggested_action": "POST /knowledge/quality/reembed",
    },
    {
        "title": "Archive stale financial chunks",
        "description": "5 financial chunks exceed domain staleness threshold",
        "severity": "info",
        "suggested_action": "POST /knowledge/quality/archive-stale",
    },
]

SAMPLE_VALIDATION_RESULT = {
    "job_id": "val_a1b2c3d4",
    "total_chunks_scanned": 50,
    "stale_chunks": 3,
    "low_confidence_chunks": 2,
    "archived_chunks": 3,
    "reembedded_chunks": 2,
    "duration_seconds": 1.25,
    "by_domain": {
        "news": {"total": 10, "stale": 1, "low_confidence": 0, "archived": 1, "reembedded": 0},
        "financial": {"total": 15, "stale": 2, "low_confidence": 1, "archived": 2, "reembedded": 1},
        "general": {"total": 25, "stale": 0, "low_confidence": 1, "archived": 0, "reembedded": 1},
    },
}


# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def client() -> TestClient:
    """Create a sync TestClient with the Knowledge router and overridden dependencies."""
    app = FastAPI()
    app.include_router(knowledge_router, prefix="/api/v1")

    # Override session dependency with a mock to avoid DB resolution
    from common_lib.modules.data_storage.database.connection import get_session

    app.dependency_overrides[get_session] = lambda: MagicMock()

    # Override knowledge engine service dependency with a mock
    from app.modules.knowledge.dependencies import get_knowledge_engine_service

    async def _mock_service():
        yield MagicMock()

    app.dependency_overrides[get_knowledge_engine_service] = _mock_service

    return TestClient(app)


@pytest.fixture
def mock_quality_service() -> MagicMock:
    """Return a mock QualityService with default success returns."""
    svc = MagicMock()
    svc.bulk_archive_stale = AsyncMock(return_value=SAMPLE_ARCHIVE_RESULT.copy())
    svc.bulk_reembed = AsyncMock(return_value=SAMPLE_REEMBED_RESULT.copy())
    svc.generate_recommendations = MagicMock(return_value=SAMPLE_RECOMMENDATIONS.copy())
    svc.run_validation_job = MagicMock(return_value=SAMPLE_VALIDATION_RESULT.copy())
    return svc


# ═══════════════════════════════════════════════════════════════════════════
# POST /knowledge/quality/archive-stale
# ═══════════════════════════════════════════════════════════════════════════


class TestBulkArchiveStaleEndpoint:
    """POST /api/v1/knowledge/quality/archive-stale — bulk archive stale chunks."""

    MODULE_PATH = "app.modules.knowledge.routes._get_quality_service"

    def test_archive_stale_defaults(
        self, client: TestClient, mock_quality_service: MagicMock
    ) -> None:
        """Empty body succeeds with mock response data."""
        with patch(self.MODULE_PATH, return_value=mock_quality_service):
            response = client.post(
                "/api/v1/knowledge/quality/archive-stale",
                json={},
            )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["total_stale"] == 3
        assert body["data"]["archived"] == 3
        assert "Dry-run" not in body["message"]

    def test_archive_stale_dry_run(
        self, client: TestClient, mock_quality_service: MagicMock
    ) -> None:
        """Dry-run returns preview without archiving."""
        mock_quality_service.bulk_archive_stale = AsyncMock(
            return_value=SAMPLE_ARCHIVE_DRY_RUN_RESULT.copy()
        )
        with patch(self.MODULE_PATH, return_value=mock_quality_service):
            response = client.post(
                "/api/v1/knowledge/quality/archive-stale",
                json={"dry_run": True},
            )
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["dry_run"] is True
        assert body["data"]["archived"] == 0
        assert "Dry-run" in body["message"]

    def test_archive_stale_with_override(
        self, client: TestClient, mock_quality_service: MagicMock
    ) -> None:
        """staleness_days override is passed to the service."""
        with patch(self.MODULE_PATH, return_value=mock_quality_service):
            response = client.post(
                "/api/v1/knowledge/quality/archive-stale",
                json={"staleness_days": 30, "dry_run": False},
            )
        assert response.status_code == 200
        mock_quality_service.bulk_archive_stale.assert_awaited_once()
        _args, kwargs = mock_quality_service.bulk_archive_stale.call_args
        assert kwargs.get("staleness_days") == 30
        assert kwargs.get("dry_run") is False

    def test_archive_stale_delegates_params(
        self, client: TestClient, mock_quality_service: MagicMock
    ) -> None:
        """Verify the route delegates correctly to QualityService."""
        with patch(self.MODULE_PATH, return_value=mock_quality_service) as mock_getter:
            client.post(
                "/api/v1/knowledge/quality/archive-stale",
                json={"staleness_days": 7, "dry_run": True},
            )
            # _get_quality_service was called
            mock_getter.assert_called_once()
            # bulk_archive_stale was called with the right params
            mock_quality_service.bulk_archive_stale.assert_awaited_once()
            _args, kwargs = mock_quality_service.bulk_archive_stale.call_args
            assert kwargs.get("staleness_days") == 7
            assert kwargs.get("dry_run") is True

    def test_archive_stale_returns_500_on_error(
        self, client: TestClient, mock_quality_service: MagicMock
    ) -> None:
        """Service exception propagates as 500."""
        mock_quality_service.bulk_archive_stale = AsyncMock(
            side_effect=ValueError("DB connection failed")
        )
        with patch(self.MODULE_PATH, return_value=mock_quality_service):
            response = client.post(
                "/api/v1/knowledge/quality/archive-stale",
                json={},
            )
        assert response.status_code == 500
        assert "Bulk archive failed" in response.json()["detail"]

    def test_archive_stale_no_body_uses_defaults(
        self, client: TestClient, mock_quality_service: MagicMock
    ) -> None:
        """Request without body uses schema defaults (dry_run=true)."""
        with patch(self.MODULE_PATH, return_value=mock_quality_service) as mock_getter:
            response = client.post(
                "/api/v1/knowledge/quality/archive-stale",
                json={},
            )
        assert response.status_code == 200
        mock_getter.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════════
# POST /knowledge/quality/reembed
# ═══════════════════════════════════════════════════════════════════════════


class TestBulkReembedEndpoint:
    """POST /api/v1/knowledge/quality/reembed — bulk re-embed low-confidence chunks."""

    MODULE_PATH = "app.modules.knowledge.routes._get_quality_service"

    def test_reembed_defaults(
        self, client: TestClient, mock_quality_service: MagicMock
    ) -> None:
        """Default dry_run=true and min_confidence=0.6."""
        with patch(self.MODULE_PATH, return_value=mock_quality_service):
            response = client.post(
                "/api/v1/knowledge/quality/reembed",
                json={},
            )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["total_low_confidence"] == 2
        assert body["data"]["reembedded"] == 2

    def test_reembed_dry_run(
        self, client: TestClient, mock_quality_service: MagicMock
    ) -> None:
        """Dry-run returns preview without re-embedding."""
        mock_quality_service.bulk_reembed = AsyncMock(
            return_value=SAMPLE_REEMBED_DRY_RUN_RESULT.copy()
        )
        with patch(self.MODULE_PATH, return_value=mock_quality_service):
            response = client.post(
                "/api/v1/knowledge/quality/reembed",
                json={"dry_run": True},
            )
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["dry_run"] is True
        assert body["data"]["reembedded"] == 0
        assert "Dry-run" in body["message"]

    def test_reembed_custom_confidence(
        self, client: TestClient, mock_quality_service: MagicMock
    ) -> None:
        """Custom min_confidence is passed to the service."""
        with patch(self.MODULE_PATH, return_value=mock_quality_service):
            response = client.post(
                "/api/v1/knowledge/quality/reembed",
                json={"min_confidence": 0.8, "dry_run": False},
            )
        assert response.status_code == 200
        mock_quality_service.bulk_reembed.assert_awaited_once()
        _args, kwargs = mock_quality_service.bulk_reembed.call_args
        assert kwargs.get("min_confidence") == 0.8
        assert kwargs.get("dry_run") is False

    def test_reembed_invalid_confidence_returns_422(
        self, client: TestClient
    ) -> None:
        """min_confidence out of range returns 422."""
        response = client.post(
            "/api/v1/knowledge/quality/reembed",
            json={"min_confidence": 1.5},
        )
        assert response.status_code == 422

    def test_reembed_negative_confidence_returns_422(
        self, client: TestClient
    ) -> None:
        """min_confidence below 0 returns 422."""
        response = client.post(
            "/api/v1/knowledge/quality/reembed",
            json={"min_confidence": -0.1},
        )
        assert response.status_code == 422

    def test_reembed_returns_500_on_error(
        self, client: TestClient, mock_quality_service: MagicMock
    ) -> None:
        """Service exception propagates as 500."""
        mock_quality_service.bulk_reembed = AsyncMock(
            side_effect=RuntimeError("Embedding service unavailable")
        )
        with patch(self.MODULE_PATH, return_value=mock_quality_service):
            response = client.post(
                "/api/v1/knowledge/quality/reembed",
                json={},
            )
        assert response.status_code == 500
        assert "Bulk re-embed failed" in response.json()["detail"]

    def test_reembed_empty_body_uses_defaults(
        self, client: TestClient, mock_quality_service: MagicMock
    ) -> None:
        """Request without body uses schema defaults."""
        with patch(self.MODULE_PATH, return_value=mock_quality_service):
            response = client.post(
                "/api/v1/knowledge/quality/reembed",
                json={},
            )
        assert response.status_code == 200
        mock_quality_service.bulk_reembed.assert_awaited_once()
        _args, kwargs = mock_quality_service.bulk_reembed.call_args
        assert kwargs.get("min_confidence") == 0.6
        assert kwargs.get("dry_run") is True


# ═══════════════════════════════════════════════════════════════════════════
# GET /knowledge/quality/recommendations
# ═══════════════════════════════════════════════════════════════════════════


class TestGenerateRecommendationsEndpoint:
    """GET /api/v1/knowledge/quality/recommendations — quality improvement recommendations."""

    MODULE_PATH = "app.modules.knowledge.routes._get_quality_service"

    def test_recommendations_returns_list(
        self, client: TestClient, mock_quality_service: MagicMock
    ) -> None:
        """Returns recommendations with success wrapper."""
        with patch(self.MODULE_PATH, return_value=mock_quality_service):
            response = client.get("/api/v1/knowledge/quality/recommendations")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert len(body["data"]["recommendations"]) == 2
        assert body["data"]["total"] == 2
        assert body["data"]["recommendations"][0]["title"] == "Re-embed low-confidence chunks"
        assert body["data"]["recommendations"][0]["severity"] == "warning"

    def test_recommendations_has_required_fields(
        self, client: TestClient, mock_quality_service: MagicMock
    ) -> None:
        """Each recommendation has required fields."""
        with patch(self.MODULE_PATH, return_value=mock_quality_service):
            response = client.get("/api/v1/knowledge/quality/recommendations")
        for rec in response.json()["data"]["recommendations"]:
            assert "title" in rec
            assert "description" in rec
            assert "severity" in rec
            assert "suggested_action" in rec

    def test_recommendations_empty(
        self, client: TestClient, mock_quality_service: MagicMock
    ) -> None:
        """Empty recommendations returns empty list."""
        mock_quality_service.generate_recommendations = MagicMock(return_value=[])
        with patch(self.MODULE_PATH, return_value=mock_quality_service):
            response = client.get("/api/v1/knowledge/quality/recommendations")
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["recommendations"] == []
        assert body["data"]["total"] == 0

    def test_recommendations_delegates(
        self, client: TestClient, mock_quality_service: MagicMock
    ) -> None:
        """Verifies delegation to QualityService.generate_recommendations."""
        with patch(self.MODULE_PATH, return_value=mock_quality_service) as mock_getter:
            client.get("/api/v1/knowledge/quality/recommendations")
            mock_getter.assert_called_once()
            mock_quality_service.generate_recommendations.assert_called_once()

    def test_recommendations_returns_500_on_error(
        self, client: TestClient, mock_quality_service: MagicMock
    ) -> None:
        """Service exception propagates as 500."""
        mock_quality_service.generate_recommendations = MagicMock(
            side_effect=Exception("Analysis failed")
        )
        with patch(self.MODULE_PATH, return_value=mock_quality_service):
            response = client.get("/api/v1/knowledge/quality/recommendations")
        assert response.status_code == 500
        assert "Failed to generate recommendations" in response.json()["detail"]


# ═══════════════════════════════════════════════════════════════════════════
# POST /knowledge/quality/run-validation
# ═══════════════════════════════════════════════════════════════════════════


class TestRunValidationJobEndpoint:
    """POST /api/v1/knowledge/quality/run-validation — run validation scan as tracked job."""

    MODULE_PATH = "app.modules.knowledge.routes._get_quality_service"

    def test_validation_returns_job_result(
        self, client: TestClient, mock_quality_service: MagicMock
    ) -> None:
        """Returns validation job result with success wrapper."""
        with patch(self.MODULE_PATH, return_value=mock_quality_service):
            response = client.post("/api/v1/knowledge/quality/run-validation", json={})
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["job_id"] == "val_a1b2c3d4"
        assert body["data"]["total_chunks_scanned"] == 50
        assert body["data"]["stale_chunks"] == 3
        assert body["data"]["low_confidence_chunks"] == 2
        assert body["data"]["duration_seconds"] == 1.25

    def test_validation_has_per_domain_breakdown(
        self, client: TestClient, mock_quality_service: MagicMock
    ) -> None:
        """Validation result includes per-domain breakdown."""
        with patch(self.MODULE_PATH, return_value=mock_quality_service):
            response = client.post("/api/v1/knowledge/quality/run-validation", json={})
        by_domain = response.json()["data"]["by_domain"]
        assert "news" in by_domain
        assert "financial" in by_domain
        assert "general" in by_domain
        assert by_domain["news"]["total"] == 10
        assert by_domain["financial"]["stale"] == 2

    def test_validation_delegates(
        self, client: TestClient, mock_quality_service: MagicMock
    ) -> None:
        """Verifies delegation to QualityService.run_validation_job."""
        with patch(self.MODULE_PATH, return_value=mock_quality_service) as mock_getter:
            client.post("/api/v1/knowledge/quality/run-validation", json={})
            mock_getter.assert_called_once()
            mock_quality_service.run_validation_job.assert_called_once()

    def test_validation_message_includes_summary(
        self, client: TestClient, mock_quality_service: MagicMock
    ) -> None:
        """Message includes job_id, scanned count, stale, low conf, and duration."""
        with patch(self.MODULE_PATH, return_value=mock_quality_service):
            response = client.post("/api/v1/knowledge/quality/run-validation", json={})
        msg = response.json()["message"]
        assert "val_a1b2" in msg  # job_id truncated to 8 chars
        assert "50" in msg
        assert "3" in msg  # stale
        assert "2" in msg  # low confidence
        assert "1.25" in msg  # duration

    def test_validation_empty_body_succeeds(
        self, client: TestClient, mock_quality_service: MagicMock
    ) -> None:
        """POST with empty body succeeds (no required params)."""
        with patch(self.MODULE_PATH, return_value=mock_quality_service):
            response = client.post("/api/v1/knowledge/quality/run-validation", json={})
        assert response.status_code == 200

    def test_validation_returns_500_on_error(
        self, client: TestClient, mock_quality_service: MagicMock
    ) -> None:
        """Service exception propagates as 500."""
        mock_quality_service.run_validation_job = MagicMock(
            side_effect=Exception("Scan failed")
        )
        with patch(self.MODULE_PATH, return_value=mock_quality_service):
            response = client.post("/api/v1/knowledge/quality/run-validation", json={})
        assert response.status_code == 500
        assert "Validation job failed" in response.json()["detail"]


# ═══════════════════════════════════════════════════════════════════════════
# Routing integrity
# ═══════════════════════════════════════════════════════════════════════════


class TestQualityRoutingIntegrity:
    """Verify all quality routes are registered at expected paths."""

    def test_all_quality_routes_in_openapi(
        self, client: TestClient
    ) -> None:
        """OpenAPI schema includes all 4 quality endpoints."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        paths = response.json().get("paths", {})
        quality_paths = {path for path in paths if "knowledge/quality" in path}
        assert "/api/v1/knowledge/quality/archive-stale" in quality_paths
        assert "/api/v1/knowledge/quality/reembed" in quality_paths
        assert "/api/v1/knowledge/quality/recommendations" in quality_paths
        assert "/api/v1/knowledge/quality/run-validation" in quality_paths

    def test_quality_routes_have_correct_methods(
        self, client: TestClient
    ) -> None:
        """Each quality endpoint has the correct HTTP method."""
        response = client.get("/openapi.json")
        paths = response.json().get("paths", {})
        assert "post" in paths["/api/v1/knowledge/quality/archive-stale"]
        assert "post" in paths["/api/v1/knowledge/quality/reembed"]
        assert "get" in paths["/api/v1/knowledge/quality/recommendations"]
        assert "post" in paths["/api/v1/knowledge/quality/run-validation"]
