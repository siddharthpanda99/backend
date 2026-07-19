"""IIL Knowledge — Integration Tests.

Tests the POST /knowledge/ingest, POST /knowledge/search, and GET /knowledge/stats endpoints.

Usage:
    cd "Backend Monorepo/Backend"
    uv run pytest tests/iil/test_knowledge.py -v
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock


# =============================================================================
# POST /knowledge/ingest Endpoint Tests
# =============================================================================


class TestKnowledgeIngestEndpoint:
    """Tests for POST /api/v1/iil/knowledge/ingest"""

    def test_ingest_success(self, client, mock_iil_service):
        """Ingest endpoint returns IngestResponse on success."""
        from common_lib.modules.iil.schemas import IngestResponse

        response = IngestResponse(
            artifact_id="art_123",
            url="http://example.com/article",
            title="Test Article",
            chunks_created=5,
            embedding_created=True,
            duration_ms=800.0,
        )
        mock_iil_service.ingest = AsyncMock(return_value=response)

        with patch("app.modules.iil.routes._get_service", return_value=mock_iil_service):
            resp = client.post(
                "/api/v1/iil/knowledge/ingest",
                json={"url_or_content": "http://example.com/article"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["artifact_id"] == "art_123"
        assert data["url"] == "http://example.com/article"
        assert data["title"] == "Test Article"
        assert data["chunks_created"] == 5
        assert data["embedding_created"] is True

    def test_ingest_service_error(self, client, mock_iil_service):
        """Ingest endpoint returns 502 when service sets error."""
        from common_lib.modules.iil.schemas import IngestResponse

        error_response = IngestResponse(
            artifact_id="",
            url="http://example.com",
            error="Ingestion failed: network timeout",
        )
        mock_iil_service.ingest = AsyncMock(return_value=error_response)

        with patch("app.modules.iil.routes._get_service", return_value=mock_iil_service):
            resp = client.post(
                "/api/v1/iil/knowledge/ingest",
                json={"url_or_content": "http://example.com"},
            )

        assert resp.status_code == 502
        body = resp.json()
        assert "Ingestion failed" in body.get("message", "")

    def test_ingest_missing_url(self, client):
        """Ingest endpoint returns 422 when url_or_content is missing."""
        resp = client.post("/api/v1/iil/knowledge/ingest", json={})
        assert resp.status_code == 422


# =============================================================================
# POST /knowledge/search Endpoint Tests
# =============================================================================


class TestKnowledgeSearchEndpoint:
    """Tests for POST /api/v1/iil/knowledge/search"""

    def test_knowledge_search_success(self, client, mock_iil_service):
        """Knowledge search returns KnowledgeSearchResponse on success."""
        from common_lib.modules.iil.schemas import KnowledgeSearchResponse, KnowledgeResult

        response = KnowledgeSearchResponse(
            query="test query",
            results=[
                KnowledgeResult(
                    id="kr_456",
                    source_url="http://example.com/doc",
                    snippet="Relevant snippet text",
                    title="Test Document",
                )
            ],
            total=1,
            mode="hybrid",
            duration_ms=150.0,
        )
        mock_iil_service.search_knowledge = MagicMock(return_value=response)

        with patch("app.modules.iil.routes._get_service", return_value=mock_iil_service):
            resp = client.post(
                "/api/v1/iil/knowledge/search",
                json={"query": "test query"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["query"] == "test query"
        assert len(data["results"]) == 1
        assert data["results"][0]["title"] == "Test Document"

    def test_knowledge_search_empty_results(self, client, mock_iil_service):
        """Knowledge search handles no results."""
        from common_lib.modules.iil.schemas import KnowledgeSearchResponse

        response = KnowledgeSearchResponse(
            query="nonexistent",
            results=[],
            total=0,
            mode="hybrid",
        )
        mock_iil_service.search_knowledge = MagicMock(return_value=response)

        with patch("app.modules.iil.routes._get_service", return_value=mock_iil_service):
            resp = client.post(
                "/api/v1/iil/knowledge/search",
                json={"query": "nonexistent"},
            )

        assert resp.status_code == 200
        assert resp.json()["results"] == []
        assert resp.json()["total"] == 0

    def test_knowledge_search_missing_query(self, client):
        """Knowledge search returns 422 when query is missing."""
        resp = client.post("/api/v1/iil/knowledge/search", json={})
        assert resp.status_code == 422


# =============================================================================
# GET /knowledge/stats Endpoint Tests
# =============================================================================


class TestKnowledgeStatsEndpoint:
    """Tests for GET /api/v1/iil/knowledge/stats"""

    def test_knowledge_stats_success(self, client, mock_iil_service):
        """Knowledge stats returns stats on success."""
        mock_iil_service.get_knowledge_stats.return_value = {
            "total_artifacts": 150,
            "total_chunks": 1200,
            "total_embeddings": 1100,
        }

        with patch("app.modules.iil.routes._get_service", return_value=mock_iil_service):
            resp = client.get("/api/v1/iil/knowledge/stats")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total_artifacts"] == 150
        assert data["total_chunks"] == 1200

    def test_knowledge_stats_empty(self, client, mock_iil_service):
        """Knowledge stats returns zero counts when empty."""
        mock_iil_service.get_knowledge_stats.return_value = {
            "total_artifacts": 0,
            "total_chunks": 0,
            "total_embeddings": 0,
        }

        with patch("app.modules.iil.routes._get_service", return_value=mock_iil_service):
            resp = client.get("/api/v1/iil/knowledge/stats")

        assert resp.status_code == 200
        assert resp.json()["total_artifacts"] == 0
