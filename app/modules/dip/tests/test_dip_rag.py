"""
Integration tests for DIP RAG routes.

Verifies that the legacy DIP RAG endpoints (/api/v1/dip/rag/*) correctly
delegate to KnowledgeEngineService via the injected dependency.

Uses sync TestClient (httpx.Client) to avoid pytest-asyncio incompatibility
with pytest 9.x. AsyncMock assertions work correctly from sync contexts.

Usage:
    cd Backend Monorepo/Backend
    uv run python -m pytest app/modules/dip/tests/test_dip_rag.py -v
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.dip.routes.rag import router as dip_rag_router
from app.modules.knowledge.dependencies import get_knowledge_engine_service

# ── Sample data matching KnowledgeEngineService response shapes ──────────

SAMPLE_CONFIG = {
    "retrieval": {"default_top_k": 100, "min_score_threshold": 0.60},
    "reranking": {"enabled": True, "use_mmr": True, "diversity_lambda": 0.3},
    "chunking": {"default_strategy": "semantic", "max_chunk_tokens": 600},
}

SAMPLE_RETRIEVE_RESULT = {
    "query": "how does auth work",
    "knowledge_chunks": [
        {
            "chunk_id": "chunk-1",
            "content": "FastAPI supports dependency injection",
            "source_id": "doc_1",
            "score": 0.95,
        },
        {
            "chunk_id": "chunk-2",
            "content": "Dependencies can be async generators",
            "source_id": "doc_1",
            "score": 0.87,
        },
    ],
    "tokens_used": 150,
    "validation_report": {"quality_score": 0.92, "action": "use"},
    "formatted_context": "## Knowledge Results\n\n1. FastAPI supports...\n",
}

SAMPLE_HEALTH = {
    "module": "knowledge_engine",
    "version": "1.0.0",
    "initialized": True,
    "models_count": 7,
    "embedding_models": ["BAAI/bge-m3", "text-embedding-3-small"],
    "chunking_strategies": ["semantic", "code", "proposition", "hierarchical"],
}


# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def mock_service() -> MagicMock:
    """Create a mocked KnowledgeEngineService with known return values."""
    svc = MagicMock()
    svc.get_config.return_value = SAMPLE_CONFIG.copy()
    svc.retrieve = AsyncMock(return_value=SAMPLE_RETRIEVE_RESULT)
    svc.health = AsyncMock(return_value=SAMPLE_HEALTH.copy())
    return svc


@pytest.fixture
def client(mock_service: MagicMock) -> TestClient:
    """Create a sync TestClient with the DIP RAG router and mock dependency."""
    app = FastAPI()
    app.include_router(dip_rag_router, prefix="/api/v1")
    # Override the KnowledgeEngineService dependency with the mock
    app.dependency_overrides[get_knowledge_engine_service] = lambda: mock_service
    return TestClient(app)


# ── Tests: GET /api/v1/dip/rag/config ───────────────────────────────────


class TestRagConfig:
    """DIP RAG configuration endpoint."""

    def test_get_config_returns_expected_fields(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        response = client.get("/api/v1/dip/rag/config")
        assert response.status_code == 200
        body = response.json()
        data = body["data"]
        assert data["retrieval_strategy"] == "hybrid"
        assert data["top_k"] == SAMPLE_CONFIG["retrieval"]["default_top_k"]
        assert data["min_score"] == SAMPLE_CONFIG["retrieval"]["min_score_threshold"]
        assert data["reranking_enabled"] == SAMPLE_CONFIG["reranking"]["enabled"]
        assert data["engine"] == "knowledge_engine"
        mock_service.get_config.assert_called_once()

    def test_get_config_delegates_to_service(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        client.get("/api/v1/dip/rag/config")
        mock_service.get_config.assert_called_once()


# ── Tests: POST /api/v1/dip/rag/queries ─────────────────────────────────


class TestRagQueries:
    """DIP RAG query execution endpoint."""

    def test_execute_query_returns_chunks(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        response = client.post(
            "/api/v1/dip/rag/queries",
            json={"query": "how does auth work"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["count"] == 2
        assert len(body["data"]) == 2
        assert body["data"][0]["chunk_id"] == "chunk-1"
        assert body["query"] == "how does auth work"
        assert body["status"] == "success"
        assert "formatted_context" in body
        assert "validation" in body

    def test_execute_query_delegates_to_service(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        client.post(
            "/api/v1/dip/rag/queries",
            json={"query": "test"},
        )
        mock_service.retrieve.assert_awaited_once_with(query="test", top_k=10)

    def test_execute_query_honors_limit(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        # limit is a query parameter, not a body field
        client.post(
            "/api/v1/dip/rag/queries?limit=5",
            json={"query": "test"},
        )
        mock_service.retrieve.assert_awaited_once_with(query="test", top_k=5)

    def test_execute_query_empty_result(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        mock_service.retrieve.return_value = None
        response = client.post(
            "/api/v1/dip/rag/queries",
            json={"query": "nothing"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["count"] == 0
        assert body["data"] == []
        assert body["status"] == "empty"

    def test_execute_query_missing_query_returns_422(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        response = client.post(
            "/api/v1/dip/rag/queries",
            json={},
        )
        assert response.status_code == 422


# ── Tests: GET /api/v1/dip/rag/metrics ──────────────────────────────────


class TestRagMetrics:
    """DIP RAG metrics / health endpoint."""

    def test_get_metrics_returns_health_data(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        response = client.get("/api/v1/dip/rag/metrics")
        assert response.status_code == 200
        body = response.json()
        data = body["data"]
        assert data["module"] == "knowledge_engine"
        assert data["initialized"] is True
        assert data["models_count"] == 7
        assert len(data["embedding_models"]) == 2
        assert len(data["chunking_strategies"]) == 4

    def test_get_metrics_delegates_to_service(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        client.get("/api/v1/dip/rag/metrics")
        mock_service.health.assert_awaited_once()

    def test_get_metrics_handles_service_error(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        mock_service.health.side_effect = Exception("Engine not reachable")
        response = client.get("/api/v1/dip/rag/metrics")
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["initialized"] is False
        assert "error" in body["data"]
        assert "Engine not reachable" in body["data"]["error"]
