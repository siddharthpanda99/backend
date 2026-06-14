"""
API-level tests for Knowledge Chunk endpoints.

Tests both basic CRUD and advanced editor operations on knowledge chunks.

CRUD endpoints (uses real in-memory SQLite):
    GET    /knowledge/chunks                     — List chunks with filters
    POST   /knowledge/chunks                     — Create a new chunk
    GET    /knowledge/chunks/{chunk_id}          — Get a single chunk
    PUT    /knowledge/chunks/{chunk_id}          — Update a chunk
    DELETE /knowledge/chunks/{chunk_id}          — Delete a chunk

Editor endpoints (mocked ChunkEditorService):
    POST   /knowledge/chunks/{chunk_id}/split    — Split into two children
    POST   /knowledge/chunks/merge               — Merge multiple chunks
    GET    /knowledge/chunks/{chunk_id}/similar   — Find similar chunks
    PUT    /knowledge/chunks/{chunk_id}/confidence — Override confidence
    POST   /knowledge/chunks/{chunk_id}/soft-delete — Soft delete
    GET    /knowledge/chunks/{chunk_id}/children   — Get child chunks

Usage:
    cd Backend Monorepo/Backend
    uv run python -m pytest app/modules/knowledge/tests/test_chunks.py -v
"""

from __future__ import annotations

from typing import Any, Generator
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlmodel import select
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlalchemy.pool import StaticPool

from app.modules.knowledge.routes import router as knowledge_router
from common_lib.modules.knowledge_engine.models.db_records import KnowledgeChunkRecord

# ── In-memory SQLite engine ────────────────────────────────────────

TEST_DB_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DB_URL,
    echo=False,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

SQLModel.metadata.create_all(engine)

# ── Sample data ────────────────────────────────────────────────────

SAMPLE_CHUNK_DATA = {
    "chunk_id": "c0000000-0000-0000-0000-000000000001",
    "content": "This is a sample knowledge chunk for testing purposes.",
    "source_id": "src-test-001",
    "source_type": "text",
    "domain": "general",
    "classification": "public",
    "job_id": "job-001",
    "metadata_json": {"source": "test", "confidence": 0.95},
    "entity_mentions": ["test", "sample"],
    "topics": ["testing", "knowledge"],
}

SAMPLE_CHUNK_DATA_2 = {
    "chunk_id": "c0000000-0000-0000-0000-000000000002",
    "content": "Financial quarterly report with revenue numbers.",
    "source_id": "src-finance-001",
    "source_type": "financial",
    "domain": "financial",
    "classification": "public",
    "job_id": "job-002",
    "metadata_json": {"source": "finance", "confidence": 0.88},
    "entity_mentions": ["revenue", "quarterly"],
    "topics": ["finance", "revenue"],
}

SAMPLE_CHUNK_DATA_3 = {
    "chunk_id": "c0000000-0000-0000-0000-000000000003",
    "content": "News article about AI developments in 2026.",
    "source_id": "src-news-001",
    "source_type": "news",
    "domain": "news",
    "classification": "public",
    "job_id": "job-003",
    "metadata_json": {"source": "news", "confidence": 0.75},
    "entity_mentions": ["AI", "developments"],
    "topics": ["AI", "news"],
}

SAMPLE_SPLIT_RESULT = (
    KnowledgeChunkRecord(
        chunk_id="c-split-a",
        content="First part",
        source_id="src-test-001",
    ),
    KnowledgeChunkRecord(
        chunk_id="c-split-b",
        content="Second part",
        source_id="src-test-001",
    ),
)

SAMPLE_MERGE_RESULT = KnowledgeChunkRecord(
    chunk_id="c-merged-001",
    content="Merged content of multiple chunks.",
    source_id="src-test-001",
)

SAMPLE_SIMILAR_RESULTS = [
    {"chunk_id": "c-sim-001", "content_preview": "Similar chunk...", "score": 0.92, "source_id": "src-test-001", "source_type": "text", "domain": "general"},
    {"chunk_id": "c-sim-002", "content_preview": "Another similar...", "score": 0.85, "source_id": "src-test-001", "source_type": "text", "domain": "general"},
]

SAMPLE_SOFT_DELETE_RESULT = {"status": "deleted", "chunk_id": "c-to-delete"}

SAMPLE_CHILDREN_RESULTS = [
    {"chunk_id": "c-child-001", "content_preview": "Child one...", "source_id": "src-test-001", "chunk_level": 1},
    {"chunk_id": "c-child-002", "content_preview": "Child two...", "source_id": "src-test-001", "chunk_level": 2},
]

# ── Seed the test DB ────────────────────────────────────────────────


def seed_test_chunks(session: Session) -> list[KnowledgeChunkRecord]:
    """Insert sample chunks and return them."""
    chunks = []
    for data in [SAMPLE_CHUNK_DATA, SAMPLE_CHUNK_DATA_2, SAMPLE_CHUNK_DATA_3]:
        rec = KnowledgeChunkRecord(**data)
        session.add(rec)
        chunks.append(rec)
    session.commit()
    for c in chunks:
        session.refresh(c)
    return chunks


with Session(engine) as _session:
    existing = _session.exec(
        select(KnowledgeChunkRecord).limit(1)
    ).first()
    if not existing:
        seed_test_chunks(_session)


def get_test_session() -> Generator[Session, None, None]:
    """Yield a session connected to the in-memory test DB."""
    with Session(engine) as session:
        yield session


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def client() -> TestClient:
    """Create a sync TestClient with the Knowledge router and overridden session."""
    app = FastAPI()
    app.include_router(knowledge_router, prefix="/api/v1")

    from common_lib.modules.data_storage.database.connection import get_session
    app.dependency_overrides[get_session] = get_test_session

    from app.modules.knowledge.dependencies import get_knowledge_engine_service

    async def _mock_service():
        svc = MagicMock()
        svc.embed = AsyncMock(return_value=MagicMock(dense=[0.1, 0.2, 0.3]))
        yield svc

    app.dependency_overrides[get_knowledge_engine_service] = _mock_service

    return TestClient(app)


@pytest.fixture
def mock_editor_service() -> MagicMock:
    """Return a mock ChunkEditorService with default returns."""
    svc = MagicMock()
    svc.edit_chunk = AsyncMock(return_value=KnowledgeChunkRecord(**SAMPLE_CHUNK_DATA))
    svc.split_chunk = AsyncMock(return_value=SAMPLE_SPLIT_RESULT)
    svc.merge_chunks = AsyncMock(return_value=SAMPLE_MERGE_RESULT)
    svc.find_similar = MagicMock(return_value=SAMPLE_SIMILAR_RESULTS)
    svc.override_confidence = MagicMock(return_value=KnowledgeChunkRecord(**SAMPLE_CHUNK_DATA))
    svc.soft_delete = MagicMock(return_value=SAMPLE_SOFT_DELETE_RESULT)
    svc.get_children = MagicMock(return_value=SAMPLE_CHILDREN_RESULTS)
    return svc


# ═══════════════════════════════════════════════════════════════════════
# GET /knowledge/chunks — List chunks
# ═══════════════════════════════════════════════════════════════════════


class TestListChunks:
    """GET /api/v1/knowledge/chunks — list knowledge chunks."""

    def test_list_all_chunks(self, client: TestClient) -> None:
        response = client.get("/api/v1/knowledge/chunks")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["total"] == 3
        assert len(body["data"]["chunks"]) == 3

    def test_list_chunks_has_required_fields(self, client: TestClient) -> None:
        response = client.get("/api/v1/knowledge/chunks")
        chunk = response.json()["data"]["chunks"][0]
        assert "chunk_id" in chunk
        assert "content" in chunk
        assert "source_id" in chunk
        assert "source_type" in chunk
        assert "domain" in chunk
        assert "created_at" in chunk
        assert "metadata" in chunk

    def test_list_chunks_filter_by_source_id(self, client: TestClient) -> None:
        response = client.get("/api/v1/knowledge/chunks?source_id=src-finance-001")
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["total"] == 1
        assert body["data"]["chunks"][0]["source_id"] == "src-finance-001"

    def test_list_chunks_filter_by_domain(self, client: TestClient) -> None:
        response = client.get("/api/v1/knowledge/chunks?domain=news")
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["total"] == 1
        assert body["data"]["chunks"][0]["domain"] == "news"

    def test_list_chunks_pagination(self, client: TestClient) -> None:
        response = client.get("/api/v1/knowledge/chunks?limit=2&offset=0")
        assert response.status_code == 200
        body = response.json()
        assert len(body["data"]["chunks"]) == 2
        assert body["data"]["limit"] == 2
        assert body["data"]["offset"] == 0

    def test_list_chunks_filter_no_results(self, client: TestClient) -> None:
        response = client.get("/api/v1/knowledge/chunks?source_id=nonexistent")
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["total"] == 0
        assert body["data"]["chunks"] == []


# ═══════════════════════════════════════════════════════════════════════
# POST /knowledge/chunks — Create chunk
# ═══════════════════════════════════════════════════════════════════════


class TestCreateChunk:
    """POST /api/v1/knowledge/chunks — create a new knowledge chunk."""

    CREATE_PAYLOAD = {
        "content": "Newly created chunk content for testing.",
        "source_id": "src-create-001",
        "source_type": "text",
        "domain": "testing",
        "classification": "public",
        "metadata": {"purpose": "creation test"},
        "topics": ["creation"],
    }

    def test_create_chunk_returns_201(self, client: TestClient) -> None:
        response = client.post("/api/v1/knowledge/chunks", json=self.CREATE_PAYLOAD)
        assert response.status_code == 201
        body = response.json()
        assert body["success"] is True
        assert body["data"]["content"] == self.CREATE_PAYLOAD["content"]
        assert body["data"]["source_id"] == "src-create-001"
        assert body["data"]["domain"] == "testing"
        assert "chunk_id" in body["data"]

        # Cleanup
        chunk_id = body["data"]["chunk_id"]
        client.delete(f"/api/v1/knowledge/chunks/{chunk_id}")

    def test_create_chunk_with_minimal_fields(self, client: TestClient) -> None:
        response = client.post("/api/v1/knowledge/chunks", json={
            "content": "Minimal chunk",
            "source_id": "src-minimal",
        })
        assert response.status_code == 201
        body = response.json()
        assert body["data"]["source_type"] == "text"  # default
        assert body["data"]["classification"] == "public"  # default

        chunk_id = body["data"]["chunk_id"]
        client.delete(f"/api/v1/knowledge/chunks/{chunk_id}")

    def test_create_chunk_missing_content_returns_422(self, client: TestClient) -> None:
        response = client.post("/api/v1/knowledge/chunks", json={
            "source_id": "src-no-content",
        })
        assert response.status_code == 422

    def test_create_chunk_missing_source_id_returns_422(self, client: TestClient) -> None:
        response = client.post("/api/v1/knowledge/chunks", json={
            "content": "Content without source",
        })
        assert response.status_code == 422


# ═══════════════════════════════════════════════════════════════════════
# GET /knowledge/chunks/{chunk_id} — Get single chunk
# ═══════════════════════════════════════════════════════════════════════


class TestGetChunk:
    """GET /api/v1/knowledge/chunks/{chunk_id} — get a single chunk."""

    def test_get_chunk_returns_chunk(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/knowledge/chunks/c0000000-0000-0000-0000-000000000001"
        )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["chunk_id"] == SAMPLE_CHUNK_DATA["chunk_id"]
        assert body["data"]["content"] == SAMPLE_CHUNK_DATA["content"]
        assert body["data"]["source_id"] == SAMPLE_CHUNK_DATA["source_id"]

    def test_get_chunk_includes_metadata(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/knowledge/chunks/c0000000-0000-0000-0000-000000000001"
        )
        metadata = response.json()["data"]["metadata"]
        assert metadata["source"] == "test"
        assert metadata["confidence"] == 0.95

    def test_get_chunk_not_found(self, client: TestClient) -> None:
        response = client.get("/api/v1/knowledge/chunks/nonexistent-id")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


# ═══════════════════════════════════════════════════════════════════════
# PUT /knowledge/chunks/{chunk_id} — Update chunk
# ═══════════════════════════════════════════════════════════════════════


class TestUpdateChunk:
    """PUT /api/v1/knowledge/chunks/{chunk_id} — update a chunk."""

    def test_update_chunk_content(self, client: TestClient) -> None:
        response = client.put(
            "/api/v1/knowledge/chunks/c0000000-0000-0000-0000-000000000001",
            json={"content": "Updated content for testing."},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["content"] == "Updated content for testing."

        # Restore original
        client.put(
            "/api/v1/knowledge/chunks/c0000000-0000-0000-0000-000000000001",
            json={"content": SAMPLE_CHUNK_DATA["content"]},
        )

    def test_update_chunk_domain(self, client: TestClient) -> None:
        response = client.put(
            "/api/v1/knowledge/chunks/c0000000-0000-0000-0000-000000000001",
            json={"domain": "updated-domain"},
        )
        assert response.status_code == 200
        assert response.json()["data"]["domain"] == "updated-domain"

        # Restore
        client.put(
            "/api/v1/knowledge/chunks/c0000000-0000-0000-0000-000000000001",
            json={"domain": SAMPLE_CHUNK_DATA["domain"]},
        )

    def test_update_chunk_not_found(self, client: TestClient) -> None:
        response = client.put(
            "/api/v1/knowledge/chunks/nonexistent-id",
            json={"content": "Updated"},
        )
        assert response.status_code == 404

    def test_update_chunk_partial_update(self, client: TestClient) -> None:
        """Only specified fields should be updated."""
        # Get current state
        get_resp = client.get(
            "/api/v1/knowledge/chunks/c0000000-0000-0000-0000-000000000002"
        )
        original_domain = get_resp.json()["data"]["domain"]

        # Update only topics
        response = client.put(
            "/api/v1/knowledge/chunks/c0000000-0000-0000-0000-000000000002",
            json={"topics": ["updated-topic"]},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["topics"] == ["updated-topic"]
        # Domain should remain unchanged
        assert data["domain"] == original_domain

        # Restore
        client.put(
            "/api/v1/knowledge/chunks/c0000000-0000-0000-0000-000000000002",
            json={"topics": SAMPLE_CHUNK_DATA_2["topics"]},
        )


# ═══════════════════════════════════════════════════════════════════════
# DELETE /knowledge/chunks/{chunk_id} — Delete chunk
# ═══════════════════════════════════════════════════════════════════════


class TestDeleteChunk:
    """DELETE /api/v1/knowledge/chunks/{chunk_id} — delete a chunk."""

    def test_delete_chunk_returns_success(self, client: TestClient) -> None:
        # Create a chunk to delete
        create_resp = client.post("/api/v1/knowledge/chunks", json={
            "content": "Chunk to delete",
            "source_id": "src-delete-test",
        })
        chunk_id = create_resp.json()["data"]["chunk_id"]

        response = client.delete(f"/api/v1/knowledge/chunks/{chunk_id}")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["chunk_id"] == chunk_id

        # Verify it's gone
        get_resp = client.get(f"/api/v1/knowledge/chunks/{chunk_id}")
        assert get_resp.status_code == 404

    def test_delete_chunk_not_found(self, client: TestClient) -> None:
        response = client.delete("/api/v1/knowledge/chunks/nonexistent-id")
        assert response.status_code == 404


# ═══════════════════════════════════════════════════════════════════════
# POST /knowledge/chunks/{chunk_id}/split — Split chunk
# ═══════════════════════════════════════════════════════════════════════


class TestSplitChunk:
    """POST /api/v1/knowledge/chunks/{chunk_id}/split — split into two children."""

    MODULE_PATH = "app.modules.knowledge.routes._get_chunk_editor_svc"

    def test_split_chunk_returns_201(self, client: TestClient, mock_editor_service: MagicMock) -> None:
        with patch(self.MODULE_PATH, return_value=mock_editor_service):
            response = client.post(
                "/api/v1/knowledge/chunks/c0000000-0000-0000-0000-000000000001/split",
                json={"split_point": 10, "second_content": "Second part content"},
            )
        assert response.status_code == 201
        body = response.json()
        assert body["success"] is True
        assert "children" in body["data"]
        assert len(body["data"]["children"]) == 2

    def test_split_chunk_delegates_params(self, client: TestClient, mock_editor_service: MagicMock) -> None:
        with patch(self.MODULE_PATH, return_value=mock_editor_service) as mock_getter:
            client.post(
                "/api/v1/knowledge/chunks/c0000000-0000-0000-0000-000000000001/split",
                json={"split_point": 15, "second_content": "Second part", "re_embed": False},
            )
            mock_getter.assert_called_once()
            mock_editor_service.split_chunk.assert_awaited_once()
            _args, kwargs = mock_editor_service.split_chunk.call_args
            assert kwargs.get("split_point") == 15
            assert kwargs.get("second_content") == "Second part"
            assert kwargs.get("re_embed") is False

    def test_split_chunk_missing_split_point_returns_422(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/knowledge/chunks/c0000000-0000-0000-0000-000000000001/split",
            json={"second_content": "Missing split point"},
        )
        assert response.status_code == 422

    def test_split_chunk_returns_500_on_error(self, client: TestClient, mock_editor_service: MagicMock) -> None:
        mock_editor_service.split_chunk = AsyncMock(
            side_effect=ValueError("Split failed")
        )
        with patch(self.MODULE_PATH, return_value=mock_editor_service):
            response = client.post(
                "/api/v1/knowledge/chunks/c0000000-0000-0000-0000-000000000001/split",
                json={"split_point": 10, "second_content": "Second part"},
            )
        assert response.status_code == 500


# ═══════════════════════════════════════════════════════════════════════
# POST /knowledge/chunks/merge — Merge chunks
# ═══════════════════════════════════════════════════════════════════════


class TestMergeChunks:
    """POST /api/v1/knowledge/chunks/merge — merge multiple chunks."""

    MODULE_PATH = "app.modules.knowledge.routes._get_chunk_editor_svc"

    def test_merge_chunks_returns_201(self, client: TestClient, mock_editor_service: MagicMock) -> None:
        with patch(self.MODULE_PATH, return_value=mock_editor_service):
            response = client.post(
                "/api/v1/knowledge/chunks/merge",
                json={"chunk_ids": ["c-001", "c-002"], "merge_strategy": "concat"},
            )
        assert response.status_code == 201
        body = response.json()
        assert body["success"] is True
        assert body["data"]["chunk"]["chunk_id"] == "c-merged-001"
        assert body["data"]["merged_ids"] == ["c-001", "c-002"]
        assert body["data"]["strategy"] == "concat"
        assert "Merged" in body["message"]

    def test_merge_chunks_with_newline_strategy(self, client: TestClient, mock_editor_service: MagicMock) -> None:
        with patch(self.MODULE_PATH, return_value=mock_editor_service):
            response = client.post(
                "/api/v1/knowledge/chunks/merge",
                json={"chunk_ids": ["c-001", "c-002", "c-003"], "merge_strategy": "newline"},
            )
        assert response.status_code == 201
        mock_editor_service.merge_chunks.assert_awaited_once()
        _args, kwargs = mock_editor_service.merge_chunks.call_args
        assert kwargs.get("merge_strategy") == "newline"

    def test_merge_chunks_missing_chunk_ids_returns_422(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/knowledge/chunks/merge",
            json={"merge_strategy": "concat"},
        )
        assert response.status_code == 422

    def test_merge_chunks_single_id_returns_422(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/knowledge/chunks/merge",
            json={"chunk_ids": ["c-001"]},
        )
        assert response.status_code == 422

    def test_merge_chunks_invalid_strategy_returns_422(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/knowledge/chunks/merge",
            json={"chunk_ids": ["c-001", "c-002"], "merge_strategy": "invalid"},
        )
        assert response.status_code == 422

    def test_merge_chunks_returns_500_on_error(self, client: TestClient, mock_editor_service: MagicMock) -> None:
        mock_editor_service.merge_chunks = AsyncMock(
            side_effect=Exception("Merge failed")
        )
        with patch(self.MODULE_PATH, return_value=mock_editor_service):
            response = client.post(
                "/api/v1/knowledge/chunks/merge",
                json={"chunk_ids": ["c-001", "c-002"]},
            )
        assert response.status_code == 500


# ═══════════════════════════════════════════════════════════════════════
# GET /knowledge/chunks/{chunk_id}/similar — Find similar chunks
# ═══════════════════════════════════════════════════════════════════════


class TestFindSimilarChunks:
    """GET /api/v1/knowledge/chunks/{chunk_id}/similar — find similar chunks."""

    MODULE_PATH = "app.modules.knowledge.routes._get_chunk_editor_svc"

    def test_similar_returns_results(self, client: TestClient, mock_editor_service: MagicMock) -> None:
        with patch(self.MODULE_PATH, return_value=mock_editor_service):
            response = client.get(
                "/api/v1/knowledge/chunks/c0000000-0000-0000-0000-000000000001/similar"
            )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert len(body["data"]["results"]) == 2

    def test_similar_has_required_fields(self, client: TestClient, mock_editor_service: MagicMock) -> None:
        with patch(self.MODULE_PATH, return_value=mock_editor_service):
            response = client.get(
                "/api/v1/knowledge/chunks/c0000000-0000-0000-0000-000000000001/similar"
            )
        for result in response.json()["data"]["results"]:
            assert "chunk_id" in result
            assert "score" in result
            assert "content_preview" in result

    def test_similar_with_params(self, client: TestClient, mock_editor_service: MagicMock) -> None:
        with patch(self.MODULE_PATH, return_value=mock_editor_service):
            client.get(
                "/api/v1/knowledge/chunks/c0000000-0000-0000-0000-000000000001/similar?top_k=5&min_score=0.5"
            )
        # Verify delegation
        mock_editor_service.find_similar.assert_called_once()
        _args, kwargs = mock_editor_service.find_similar.call_args
        assert kwargs.get("top_k") == 5
        assert kwargs.get("min_score") == 0.5

    def test_similar_empty_results(self, client: TestClient, mock_editor_service: MagicMock) -> None:
        mock_editor_service.find_similar = MagicMock(return_value=[])
        with patch(self.MODULE_PATH, return_value=mock_editor_service):
            response = client.get(
                "/api/v1/knowledge/chunks/c0000000-0000-0000-0000-000000000001/similar"
            )
        assert response.status_code == 200
        assert response.json()["data"]["results"] == []
        assert response.json()["data"]["results"] == []

    def test_similar_returns_500_on_error(self, client: TestClient, mock_editor_service: MagicMock) -> None:
        mock_editor_service.find_similar = MagicMock(
            side_effect=Exception("Similarity search failed")
        )
        with patch(self.MODULE_PATH, return_value=mock_editor_service):
            response = client.get(
                "/api/v1/knowledge/chunks/c0000000-0000-0000-0000-000000000001/similar"
            )
        assert response.status_code == 500


# ═══════════════════════════════════════════════════════════════════════
# PUT /knowledge/chunks/{chunk_id}/confidence — Override confidence
# ═══════════════════════════════════════════════════════════════════════


class TestOverrideConfidence:
    """PUT /api/v1/knowledge/chunks/{chunk_id}/confidence — override confidence."""

    MODULE_PATH = "app.modules.knowledge.routes._get_chunk_editor_svc"

    def test_override_confidence(self, client: TestClient, mock_editor_service: MagicMock) -> None:
        with patch(self.MODULE_PATH, return_value=mock_editor_service):
            response = client.put(
                "/api/v1/knowledge/chunks/c0000000-0000-0000-0000-000000000001/confidence",
                json={"confidence": 0.85},
            )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert "Confidence" in body["message"]

    def test_override_confidence_delegates(self, client: TestClient, mock_editor_service: MagicMock) -> None:
        with patch(self.MODULE_PATH, return_value=mock_editor_service):
            client.put(
                "/api/v1/knowledge/chunks/c0000000-0000-0000-0000-000000000001/confidence",
                json={"confidence": 0.42},
            )
        mock_editor_service.override_confidence.assert_called_once()
        _args, kwargs = mock_editor_service.override_confidence.call_args
        assert kwargs.get("confidence") == 0.42

    def test_override_confidence_out_of_range_returns_422(self, client: TestClient) -> None:
        response = client.put(
            "/api/v1/knowledge/chunks/c0000000-0000-0000-0000-000000000001/confidence",
            json={"confidence": 1.5},
        )
        assert response.status_code == 422

    def test_override_confidence_negative_returns_422(self, client: TestClient) -> None:
        response = client.put(
            "/api/v1/knowledge/chunks/c0000000-0000-0000-0000-000000000001/confidence",
            json={"confidence": -0.1},
        )
        assert response.status_code == 422

    def test_override_confidence_returns_500_on_error(self, client: TestClient, mock_editor_service: MagicMock) -> None:
        mock_editor_service.override_confidence = MagicMock(
            side_effect=ValueError("Invalid chunk")
        )
        with patch(self.MODULE_PATH, return_value=mock_editor_service):
            response = client.put(
                "/api/v1/knowledge/chunks/c0000000-0000-0000-0000-000000000001/confidence",
                json={"confidence": 0.5},
            )
        assert response.status_code == 500


# ═══════════════════════════════════════════════════════════════════════
# POST /knowledge/chunks/{chunk_id}/soft-delete — Soft delete chunk
# ═══════════════════════════════════════════════════════════════════════


class TestSoftDeleteChunk:
    """POST /api/v1/knowledge/chunks/{chunk_id}/soft-delete — soft delete."""

    MODULE_PATH = "app.modules.knowledge.routes._get_chunk_editor_svc"

    def test_soft_delete_returns_success(self, client: TestClient, mock_editor_service: MagicMock) -> None:
        with patch(self.MODULE_PATH, return_value=mock_editor_service):
            response = client.post(
                "/api/v1/knowledge/chunks/c0000000-0000-0000-0000-000000000001/soft-delete",
            )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["status"] == "deleted"
        assert "soft-deleted" in body["message"]

    def test_soft_delete_delegates(self, client: TestClient, mock_editor_service: MagicMock) -> None:
        with patch(self.MODULE_PATH, return_value=mock_editor_service) as mock_getter:
            client.post(
                "/api/v1/knowledge/chunks/c0000000-0000-0000-0000-000000000001/soft-delete",
            )
            mock_getter.assert_called_once()
            mock_editor_service.soft_delete.assert_called_once()

    def test_soft_delete_returns_500_on_error(self, client: TestClient, mock_editor_service: MagicMock) -> None:
        mock_editor_service.soft_delete = MagicMock(
            side_effect=Exception("Delete failed")
        )
        with patch(self.MODULE_PATH, return_value=mock_editor_service):
            response = client.post(
                "/api/v1/knowledge/chunks/c0000000-0000-0000-0000-000000000001/soft-delete",
            )
        assert response.status_code == 500


# ═══════════════════════════════════════════════════════════════════════
# GET /knowledge/chunks/{chunk_id}/children — Get child chunks
# ═══════════════════════════════════════════════════════════════════════


class TestGetChunkChildren:
    """GET /api/v1/knowledge/chunks/{chunk_id}/children — get child chunks."""

    MODULE_PATH = "app.modules.knowledge.routes._get_chunk_editor_svc"

    def test_get_children_returns_list(self, client: TestClient, mock_editor_service: MagicMock) -> None:
        with patch(self.MODULE_PATH, return_value=mock_editor_service):
            response = client.get(
                "/api/v1/knowledge/chunks/c0000000-0000-0000-0000-000000000001/children"
            )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert len(body["data"]["children"]) == 2
        assert body["data"]["parent_id"] == "c0000000-0000-0000-0000-000000000001"

    def test_get_children_has_required_fields(self, client: TestClient, mock_editor_service: MagicMock) -> None:
        with patch(self.MODULE_PATH, return_value=mock_editor_service):
            response = client.get(
                "/api/v1/knowledge/chunks/c0000000-0000-0000-0000-000000000001/children"
            )
        for child in response.json()["data"]["children"]:
            assert "chunk_id" in child
            assert "content_preview" in child
            assert "chunk_level" in child

    def test_get_children_empty(self, client: TestClient, mock_editor_service: MagicMock) -> None:
        mock_editor_service.get_children = MagicMock(return_value=[])
        with patch(self.MODULE_PATH, return_value=mock_editor_service):
            response = client.get(
                "/api/v1/knowledge/chunks/c0000000-0000-0000-0000-000000000001/children"
            )
        assert response.status_code == 200
        assert response.json()["data"]["children"] == []
        assert response.json()["data"]["count"] == 0

    def test_get_children_delegates(self, client: TestClient, mock_editor_service: MagicMock) -> None:
        with patch(self.MODULE_PATH, return_value=mock_editor_service) as mock_getter:
            client.get(
                "/api/v1/knowledge/chunks/c0000000-0000-0000-0000-000000000001/children"
            )
            mock_getter.assert_called_once()
            mock_editor_service.get_children.assert_called_once()

    def test_get_children_returns_500_on_error(self, client: TestClient, mock_editor_service: MagicMock) -> None:
        mock_editor_service.get_children = MagicMock(
            side_effect=Exception("Failed to get children")
        )
        with patch(self.MODULE_PATH, return_value=mock_editor_service):
            response = client.get(
                "/api/v1/knowledge/chunks/c0000000-0000-0000-0000-000000000001/children"
            )
        assert response.status_code == 500


# ═══════════════════════════════════════════════════════════════════════
# Routing integrity
# ═══════════════════════════════════════════════════════════════════════


class TestChunksRoutingIntegrity:
    """Verify all chunk routes are registered at expected paths."""

    def test_all_chunk_routes_in_openapi(self, client: TestClient) -> None:
        response = client.get("/openapi.json")
        assert response.status_code == 200
        paths = response.json().get("paths", {})
        chunk_paths = {path for path in paths if "knowledge/chunks" in path}

        assert "/api/v1/knowledge/chunks" in chunk_paths  # GET list + POST create
        assert "/api/v1/knowledge/chunks/{chunk_id}" in chunk_paths  # GET/PUT/DELETE
        assert "/api/v1/knowledge/chunks/{chunk_id}/split" in chunk_paths
        assert "/api/v1/knowledge/chunks/merge" in chunk_paths
        assert "/api/v1/knowledge/chunks/{chunk_id}/similar" in chunk_paths
        assert "/api/v1/knowledge/chunks/{chunk_id}/confidence" in chunk_paths
        assert "/api/v1/knowledge/chunks/{chunk_id}/soft-delete" in chunk_paths
        assert "/api/v1/knowledge/chunks/{chunk_id}/children" in chunk_paths

    def test_chunk_routes_have_correct_methods(self, client: TestClient) -> None:
        response = client.get("/openapi.json")
        paths = response.json().get("paths", {})

        chunks_path = paths["/api/v1/knowledge/chunks"]
        assert "get" in chunks_path
        assert "post" in chunks_path

        chunk_id_path = paths["/api/v1/knowledge/chunks/{chunk_id}"]
        assert "get" in chunk_id_path
        assert "put" in chunk_id_path
        assert "delete" in chunk_id_path
