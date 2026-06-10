"""
Integration tests for DIP KG, Storage, and Embeddings routes.

Verifies that all DIP endpoints registered in main.py return expected
response shapes and correctly handle edge cases.

Uses sync TestClient to avoid pytest-asyncio incompatibility with pytest 9.x.

Usage:
    cd Backend Monorepo/Backend
    uv run python -m pytest app/modules/dip/tests/test_dip_kg_storage_embeddings.py -v
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.dip.routes.kg import router as dip_kg_router
from app.modules.dip.routes.storage import router as dip_storage_router
from app.modules.dip.routes.embeddings import router as dip_embeddings_router
from common_lib.modules.graph import GraphNode, GraphEdge, GraphResponse


# ── Sample data ──────────────────────────────────────────────────────────

SAMPLE_NODES = [
    GraphNode(id="1", label="FastAPI", category="Core", description="Web framework", tags=["python", "api"], entity_type="doc"),
    GraphNode(id="2", label="pgvector", category="Storage", description="Vector search", tags=["database"], entity_type="doc"),
    GraphNode(id="3", label="React", category="Frontend", description="UI library", tags=["javascript"], entity_type="doc"),
]

SAMPLE_EDGES = [
    GraphEdge(from_id="1", to_id="2", label="uses"),
    GraphEdge(from_id="1", to_id="3", label="connects_to"),
]

SAMPLE_GRAPH_RESPONSE = GraphResponse(
    graph={"id": "super_graph", "name": "Super Graph"},
    nodes=SAMPLE_NODES,
    edges=SAMPLE_EDGES,
    categories=["Core", "Frontend", "Storage"],
    summary={"nodes": 3, "edges": 2},
)

SAMPLE_DOCUMENTS = [
    {"document_id": "doc-1", "filename": "report.pdf", "status": "completed", "created_at": "2026-01-01T00:00:00", "extraction_count": 3},
    {"document_id": "doc-2", "filename": "notes.txt", "status": "completed", "created_at": "2026-01-02T00:00:00", "extraction_count": 1},
]


# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def kg_client() -> TestClient:
    """Create a sync TestClient with the DIP KG router.

    The KG routes call _graph_svc.load_graph() which requires a database.
    We patch app.modules.dip.routes.kg._graph_svc.load_graph on the module path.
    """
    app = FastAPI()
    app.include_router(dip_kg_router, prefix="/api/v1")
    return TestClient(app)


@pytest.fixture
def storage_client() -> TestClient:
    """Create a sync TestClient with the DIP Storage router.

    The storage routes call list_documents() from document_vault.
    We patch common_lib.modules.dip.document_vault.list_documents.
    """
    app = FastAPI()
    app.include_router(dip_storage_router, prefix="/api/v1")
    return TestClient(app)


@pytest.fixture
def embeddings_client() -> TestClient:
    """Create a sync TestClient with the DIP Embeddings router.

    All embeddings endpoints return hardcoded data — no mocking needed.
    """
    app = FastAPI()
    app.include_router(dip_embeddings_router, prefix="/api/v1")
    return TestClient(app)


# ═══════════════════════════════════════════════════════════════════════════
# KG Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestKgEntities:
    """GET /api/v1/dip/kg/entities"""

    def test_list_entities_returns_nodes(self, kg_client: TestClient) -> None:
        with patch(
            "app.modules.dip.routes.kg._graph_svc.load_graph",
            return_value=SAMPLE_GRAPH_RESPONSE,
        ):
            response = kg_client.get("/api/v1/dip/kg/entities")
        assert response.status_code == 200
        body = response.json()
        assert body["count"] == 3
        assert len(body["data"]) == 3
        assert body["data"][0]["id"] == "1"
        assert body["data"][0]["label"] == "FastAPI"
        assert body["data"][0]["category"] == "Core"

    def test_list_entities_filters_by_category(
        self, kg_client: TestClient
    ) -> None:
        with patch(
            "app.modules.dip.routes.kg._graph_svc.load_graph",
            return_value=SAMPLE_GRAPH_RESPONSE,
        ):
            response = kg_client.get("/api/v1/dip/kg/entities?category=storage")
        assert response.status_code == 200
        body = response.json()
        assert body["count"] == 1
        assert body["data"][0]["id"] == "2"
        assert body["data"][0]["category"] == "Storage"

    def test_list_entities_no_match_returns_empty(
        self, kg_client: TestClient
    ) -> None:
        with patch(
            "app.modules.dip.routes.kg._graph_svc.load_graph",
            return_value=SAMPLE_GRAPH_RESPONSE,
        ):
            response = kg_client.get(
                "/api/v1/dip/kg/entities?category=nonexistent"
            )
        assert response.status_code == 200
        body = response.json()
        assert body["count"] == 0
        assert body["data"] == []

    def test_list_entities_supports_refresh_param(
        self, kg_client: TestClient
    ) -> None:
        with patch(
            "app.modules.dip.routes.kg._graph_svc.load_graph",
            return_value=SAMPLE_GRAPH_RESPONSE,
        ) as mock_load:
            kg_client.get("/api/v1/dip/kg/entities?refresh=true")
            mock_load.assert_called_once_with(refresh=True)

    def test_list_entities_empty_graph(self, kg_client: TestClient) -> None:
        empty = GraphResponse(
            graph={"id": "super_graph", "name": "Super Graph"},
            nodes=[], edges=[], categories=[], summary={"nodes": 0, "edges": 0},
        )
        with patch(
            "app.modules.dip.routes.kg._graph_svc.load_graph",
            return_value=empty,
        ):
            response = kg_client.get("/api/v1/dip/kg/entities")
        assert response.status_code == 200
        assert response.json()["count"] == 0


class TestKgRelations:
    """GET /api/v1/dip/kg/relations"""

    def test_list_relations_returns_edges(
        self, kg_client: TestClient
    ) -> None:
        with patch(
            "app.modules.dip.routes.kg._graph_svc.load_graph",
            return_value=SAMPLE_GRAPH_RESPONSE,
        ):
            response = kg_client.get("/api/v1/dip/kg/relations")
        assert response.status_code == 200
        body = response.json()
        assert body["count"] == 2
        assert len(body["data"]) == 2
        assert body["data"][0]["from_id"] == "1"
        assert body["data"][0]["to_id"] == "2"
        assert body["data"][0]["label"] == "uses"

    def test_list_relations_supports_refresh(
        self, kg_client: TestClient
    ) -> None:
        with patch(
            "app.modules.dip.routes.kg._graph_svc.load_graph",
            return_value=SAMPLE_GRAPH_RESPONSE,
        ) as mock_load:
            kg_client.get("/api/v1/dip/kg/relations?refresh=true")
            mock_load.assert_called_once_with(refresh=True)


class TestKgMetrics:
    """GET /api/v1/dip/kg/metrics"""

    def test_get_metrics_returns_summary(
        self, kg_client: TestClient
    ) -> None:
        with patch(
            "app.modules.dip.routes.kg._graph_svc.load_graph",
            return_value=SAMPLE_GRAPH_RESPONSE,
        ):
            response = kg_client.get("/api/v1/dip/kg/metrics")
        assert response.status_code == 200
        body = response.json()
        data = body["data"]
        assert data["total_entities"] == 3
        assert data["total_relations"] == 2
        assert data["density"] > 0  # 3 nodes, 2 edges → density > 0
        assert data["categories"] == ["Core", "Frontend", "Storage"]
        assert "summary" in data

    def test_get_metrics_empty_graph(
        self, kg_client: TestClient
    ) -> None:
        empty = GraphResponse(
            graph={"id": "super_graph", "name": "Super Graph"},
            nodes=[], edges=[], categories=[], summary={"nodes": 0, "edges": 0},
        )
        with patch(
            "app.modules.dip.routes.kg._graph_svc.load_graph",
            return_value=empty,
        ):
            response = kg_client.get("/api/v1/dip/kg/metrics")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["total_entities"] == 0
        assert data["total_relations"] == 0
        assert data["density"] == 0  # node_count <= 1 → density = 0


# ═══════════════════════════════════════════════════════════════════════════
# Storage Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestStorageIndexes:
    """GET /api/v1/dip/storage/indexes — hardcoded data, no mocking needed."""

    def test_list_indexes_returns_expected_count(
        self, storage_client: TestClient
    ) -> None:
        response = storage_client.get("/api/v1/dip/storage/indexes")
        assert response.status_code == 200
        body = response.json()
        data = body["data"]
        assert len(data) == 3

    def test_list_indexes_has_required_fields(
        self, storage_client: TestClient
    ) -> None:
        response = storage_client.get("/api/v1/dip/storage/indexes")
        data = response.json()["data"]
        for idx in data:
            assert "id" in idx
            assert "name" in idx
            assert "type" in idx
            assert "status" in idx
        types = {i["type"] for i in data}
        assert "vector" in types
        assert "relational" in types

    def test_list_indexes_all_active(
        self, storage_client: TestClient
    ) -> None:
        response = storage_client.get("/api/v1/dip/storage/indexes")
        for idx in response.json()["data"]:
            assert idx["status"] == "active"


class TestStorageDocuments:
    """GET /api/v1/dip/storage/documents — calls list_documents()."""

    def test_list_documents_returns_docs(
        self, storage_client: TestClient
    ) -> None:
        with patch(
            "app.modules.dip.routes.storage.list_documents",
            return_value=SAMPLE_DOCUMENTS,
        ):
            response = storage_client.get("/api/v1/dip/storage/documents")
        assert response.status_code == 200
        body = response.json()
        assert body["count"] == 2
        assert body["data"][0]["document_id"] == "doc-1"
        assert body["data"][1]["filename"] == "notes.txt"

    def test_list_documents_passes_limit(
        self, storage_client: TestClient
    ) -> None:
        with patch(
            "app.modules.dip.routes.storage.list_documents",
            return_value=SAMPLE_DOCUMENTS[:1],
        ) as mock_list:
            response = storage_client.get("/api/v1/dip/storage/documents?limit=1")
        assert response.status_code == 200
        mock_list.assert_called_once_with(1)
        assert response.json()["count"] == 1

    def test_list_documents_empty(
        self, storage_client: TestClient
    ) -> None:
        with patch(
            "app.modules.dip.routes.storage.list_documents",
            return_value=[],
        ):
            response = storage_client.get("/api/v1/dip/storage/documents")
        assert response.status_code == 200
        body = response.json()
        assert body["count"] == 0
        assert body["data"] == []


class TestStorageMetrics:
    """GET /api/v1/dip/storage/metrics — calls list_documents()."""

    def test_get_metrics_returns_expected_fields(
        self, storage_client: TestClient
    ) -> None:
        with patch(
            "app.modules.dip.routes.storage.list_documents",
            return_value=SAMPLE_DOCUMENTS,
        ):
            response = storage_client.get("/api/v1/dip/storage/metrics")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["used_bytes"] == 1024 * 1024 * 45
        assert data["total_documents"] == 2
        assert data["index_health"] == "optimal"
        assert "last_sync" in data

    def test_get_metrics_empty_vault(
        self, storage_client: TestClient
    ) -> None:
        with patch(
            "app.modules.dip.routes.storage.list_documents",
            return_value=[],
        ):
            response = storage_client.get("/api/v1/dip/storage/metrics")
        assert response.status_code == 200
        assert response.json()["data"]["total_documents"] == 0


# ═══════════════════════════════════════════════════════════════════════════
# Embeddings Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestEmbeddingsModels:
    """GET /api/v1/dip/embeddings/models — hardcoded data."""

    def test_list_models_returns_three_models(
        self, embeddings_client: TestClient
    ) -> None:
        response = embeddings_client.get("/api/v1/dip/embeddings/models")
        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data) == 3
        ids = {m["id"] for m in data}
        assert ids == {
            "text-embedding-3-small",
            "bge-large-en-v1.5",
            "clip-vit-b-32",
        }

    def test_list_models_has_required_fields(
        self, embeddings_client: TestClient
    ) -> None:
        response = embeddings_client.get("/api/v1/dip/embeddings/models")
        for m in response.json()["data"]:
            assert "id" in m
            assert "provider" in m
            assert "dims" in m
            assert "status" in m


class TestEmbeddingsQueues:
    """GET /api/v1/dip/embeddings/queues — hardcoded data."""

    def test_get_queues_returns_expected_fields(
        self, embeddings_client: TestClient
    ) -> None:
        response = embeddings_client.get("/api/v1/dip/embeddings/queues")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["pending_tasks"] == 0
        assert data["failed_tasks"] == 12
        assert data["processed_today"] == 4500
        assert data["status"] == "clear"

    def test_get_queues_has_all_keys(
        self, embeddings_client: TestClient
    ) -> None:
        response = embeddings_client.get("/api/v1/dip/embeddings/queues")
        keys = set(response.json()["data"].keys())
        expected = {"pending_tasks", "failed_tasks", "processed_today", "status"}
        assert keys == expected


class TestEmbeddingsMetrics:
    """GET /api/v1/dip/embeddings/metrics — hardcoded data."""

    def test_get_metrics_returns_expected_fields(
        self, embeddings_client: TestClient
    ) -> None:
        response = embeddings_client.get("/api/v1/dip/embeddings/metrics")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["avg_generation_time_ms"] == 22
        assert data["throughput_per_sec"] == 45
        assert data["error_rate"] == 0.001

    def test_get_metrics_has_all_keys(
        self, embeddings_client: TestClient
    ) -> None:
        response = embeddings_client.get("/api/v1/dip/embeddings/metrics")
        keys = set(response.json()["data"].keys())
        expected = {"avg_generation_time_ms", "throughput_per_sec", "error_rate"}
        assert keys == expected
