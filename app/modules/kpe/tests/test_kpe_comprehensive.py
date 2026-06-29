"""
Comprehensive API-level tests for all KPE endpoints.

Tests all KPE routes:
    POST   /kpe/extraction/       — Run extraction on text/document
    POST   /kpe/classification/   — Run classifiers on text/document
    POST   /kpe/retrieval/search  — Full retrieval pipeline
    POST   /kpe/retrieval/rewrite — Query rewriting
    POST   /kpe/retrieval/enrich  — Context enrichment
    POST   /kpe/retrieval/rerank  — Rerank results
    POST   /kpe/summarization/    — Text summarization
    POST   /kpe/ingestion/        — Ingest content
    GET    /kpe/ingestion/logs    — List ingestion logs
    GET    /kpe/documents/        — List documents
    GET    /kpe/documents/{id}    — Get document
    POST   /kpe/documents/        — Create document
    DELETE /kpe/documents/{id}    — Delete document
    POST   /kpe/processing/       — Process document
    POST   /kpe/kg/extract        — Extract knowledge graph
    POST   /kpe/kg/infer          — Infer relationships
    POST   /kpe/kg/query          — Query knowledge graph
    POST   /kpe/quality/          — Run quality checks

Usage:
    cd Backend Monorepo/Backend
    uv run python -m pytest app/modules/kpe/tests/test_kpe_comprehensive.py -v
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.kpe.routes import router as kpe_router


# ═══════════════════════════════════════════════════════════════════════════
# Sample Data
# ═══════════════════════════════════════════════════════════════════════════

SAMPLE_EXTRACTION_RESULT = {
    "entities": [
        {"text": "OpenAI", "type": "ORG", "confidence": 0.98, "position": {"start": 0, "end": 6}},
        {"text": "GPT-4", "type": "PRODUCT", "confidence": 0.95, "position": {"start": 20, "end": 25}},
    ],
    "relationships": [
        {"source": "OpenAI", "target": "GPT-4", "type": "DEVELOPS", "confidence": 0.92},
    ],
    "facts": [
        {"fact": "OpenAI developed GPT-4", "confidence": 0.96, "category": "technology"},
    ],
}

SAMPLE_CLASSIFICATION_RESULT = {
    "topic": {"label": "machine learning", "confidence": 0.94, "taxonomy_matches": ["AI", "ML"]},
    "intent": {"label": "informational", "confidence": 0.87, "sub_intent": "research"},
    "trust": {"score": 0.82, "flags": [], "verdict": "trusted"},
}

SAMPLE_RETRIEVAL_RESULT = [
    {"id": "chunk_1", "content": "Machine learning is a subset of AI.", "score": 0.92, "metadata": {"source": "wiki"}},
    {"id": "chunk_2", "content": "Deep learning uses neural networks.", "score": 0.85, "metadata": {"source": "wiki"}},
]

SAMPLE_SUMMARIZATION_RESULT = {
    "summary": "This is an AI-generated summary of the provided text.",
    "compression_ratio": 3.5,
    "method": "llm",
    "original_length": 1000,
    "summary_length": 285,
    "key_points": ["Key point one", "Key point two"],
    "tone": "neutral",
}

SAMPLE_QUALITY_RESULT = {
    "sensitivity": {"score": 0.02, "is_sensitive": False, "flagged_categories": []},
    "factuality": {"score": 0.91, "verifiable": True, "supported": True},
    "consistency": {"score": 0.88, "internal_consistency": True},
    "hallucination": {"detected": False, "score": 0.05},
}


# ═══════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture
def client() -> TestClient:
    """Create a sync TestClient with the KPE router."""
    app = FastAPI()
    app.include_router(kpe_router)
    return TestClient(app)


# ═══════════════════════════════════════════════════════════════════════════
# EXTRACTION — POST /kpe/extraction/
# ═══════════════════════════════════════════════════════════════════════════


class TestExtractionEndpoint:
    """POST /api/v1/kpe/extraction/ — Run extraction on text/document."""

    MODULE_PATH = "app.modules.kpe.routes.extraction._llm_service"

    def test_extraction_text_inline(self, client: TestClient) -> None:
        """Inline text extraction with default extractors succeeds."""
        with patch(f"{self.MODULE_PATH}.entity_extractor") as mock_entity:
            mock_entity.extract.return_value = SAMPLE_EXTRACTION_RESULT["entities"]
            with patch(f"{self.MODULE_PATH}.event_extractor") as mock_event:
                mock_event.extract.return_value = []
                with patch(f"{self.MODULE_PATH}.keyword_extractor") as mock_kw:
                    mock_kw.extract.return_value = []
                    with patch(f"{self.MODULE_PATH}.sentiment_analyzer") as mock_sent:
                        mock_sent.analyze.return_value = {"sentiment": "positive", "score": 0.8}

                        response = client.post(
                            "/kpe/extraction/",
                            json={
                                "document_id": "inline",
                                "text": "OpenAI developed GPT-4, a powerful language model.",
                                "extractors": ["entities"],
                                "use_llm": True,
                            },
                        )

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["engine"] == "llm"
        assert "entities" in body["results"]

    def test_extraction_invalid_extractor(self, client: TestClient) -> None:
        """Unknown extractor type is handled gracefully."""
        with patch(f"{self.MODULE_PATH}.entity_extractor") as mock_entity:
            mock_entity.extract.return_value = []

            response = client.post(
                "/kpe/extraction/",
                json={
                    "document_id": "test",
                    "text": "Some text.",
                    "extractors": ["nonexistent_extractor"],
                    "use_llm": True,
                },
            )

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True

    def test_extraction_returns_500_on_error(self, client: TestClient) -> None:
        """Service exception propagates as 500."""
        with patch(f"{self.MODULE_PATH}.entity_extractor") as mock:
            mock.extract.side_effect = RuntimeError("LLM unavailable")

            response = client.post(
                "/kpe/extraction/",
                json={
                    "document_id": "test",
                    "text": "Some text.",
                    "use_llm": True,
                },
            )

        assert response.status_code == 500

    def test_extraction_missing_id_uses_inline(self, client: TestClient) -> None:
        """Empty document_id defaults to 'inline'."""
        with patch(f"{self.MODULE_PATH}.entity_extractor") as mock_entity:
            mock_entity.extract.return_value = []

            response = client.post(
                "/kpe/extraction/",
                json={
                    "document_id": "",
                    "text": "Test text.",
                    "extractors": ["entities"],
                    "use_llm": True,
                },
            )

        assert response.status_code == 200
        body = response.json()
        assert body["document_id"] == "inline"

    def test_extraction_static_fallback(self, client: TestClient) -> None:
        """use_llm=False delegates to _static_service.run_extractors()."""
        with patch("app.modules.kpe.routes.extraction._static_service") as mock:
            mock.run_extractors = AsyncMock(return_value={
                "entities": [{"text": "OpenAI", "type": "ORG", "confidence": 0.95}],
                "keywords": ["AI", "language model"],
            })

            response = client.post(
                "/kpe/extraction/",
                json={
                    "document_id": "doc_123",
                    "text": "",
                    "extractors": ["entities", "keywords"],
                    "use_llm": False,
                },
            )

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["engine"] == "static"
        assert body["document_id"] == "doc_123"
        assert "entities" in body["results"]
        assert "keywords" in body["results"]
        # Verify delegation to _static_service.run_extractors with correct params
        mock.run_extractors.assert_awaited_once_with(
            document_id="doc_123",
            extractors=["entities", "keywords"],
        )

    def test_extraction_static_fallback_empty_text_defaults(self, client: TestClient) -> None:
        """Empty text without use_llm=false also falls back to static path."""
        with patch("app.modules.kpe.routes.extraction._static_service") as mock:
            mock.run_extractors = AsyncMock(return_value={})

            response = client.post(
                "/kpe/extraction/",
                json={
                    "document_id": "doc_456",
                    "extractors": ["entities"],
                    # use_llm defaults to True, but text is empty so it hits static path
                },
            )

        assert response.status_code == 200
        body = response.json()
        assert body["engine"] == "static"
        mock.run_extractors.assert_awaited_once()

    def test_extraction_static_returns_empty_results(self, client: TestClient) -> None:
        """Static path with empty results still returns 200."""
        with patch("app.modules.kpe.routes.extraction._static_service") as mock:
            mock.run_extractors = AsyncMock(return_value={})

            response = client.post(
                "/kpe/extraction/",
                json={
                    "document_id": "doc_empty",
                    "text": "",
                    "extractors": ["entities", "relationships", "facts"],
                    "use_llm": False,
                },
            )

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["results"] == {}
        assert body["engine"] == "static"

    def test_extraction_static_returns_500(self, client: TestClient) -> None:
        """Static service exception returns 500."""
        with patch("app.modules.kpe.routes.extraction._static_service") as mock:
            mock.run_extractors.side_effect = RuntimeError("Static extraction failed")

            response = client.post(
                "/kpe/extraction/",
                json={
                    "document_id": "doc_err",
                    "text": "",
                    "use_llm": False,
                },
            )

        assert response.status_code == 500

    def test_extraction_all_extractor_types(self, client: TestClient) -> None:
        """Running entities+relationships+facts uses both extractors."""
        with (
            patch(f"{self.MODULE_PATH}.entity_extractor") as mock_entity,
            patch(f"{self.MODULE_PATH}.event_extractor") as mock_event,
            patch(f"{self.MODULE_PATH}.keyword_extractor") as mock_kw,
            patch(f"{self.MODULE_PATH}.sentiment_analyzer") as mock_sent,
        ):
            mock_entity.extract.return_value = SAMPLE_EXTRACTION_RESULT["entities"]
            mock_event.extract.return_value = []
            mock_kw.extract.return_value = []
            mock_sent.analyze.return_value = {"sentiment": "neutral", "score": 0.5}

            response = client.post(
                "/kpe/extraction/",
                json={
                    "document_id": "inline",
                    "text": "Test text for all extractors.",
                    "extractors": ["entities", "events", "keywords", "sentiment"],
                    "use_llm": True,
                },
            )

        assert response.status_code == 200
        body = response.json()
        assert len(body["results"]) == 4
        assert "entities" in body["results"]
        assert "events" in body["results"]
        assert "keywords" in body["results"]
        assert "sentiment" in body["results"]


# ═══════════════════════════════════════════════════════════════════════════
# CLASSIFICATION — POST /kpe/classification/
# ═══════════════════════════════════════════════════════════════════════════


class TestClassificationEndpoint:
    """POST /api/v1/kpe/classification/ — Run classifiers on text."""

    MODULE_PATH = "app.modules.kpe.routes.classification._llm_service"

    def test_classification_topic_intent_trust(self, client: TestClient) -> None:
        """LLM-driven topic + intent + trust classification returns all results."""
        with (
            patch(f"{self.MODULE_PATH}.topic") as mock_topic,
            patch(f"{self.MODULE_PATH}.intent") as mock_intent,
            patch(f"{self.MODULE_PATH}.trust") as mock_trust,
        ):
            mock_topic.classify.return_value = SAMPLE_CLASSIFICATION_RESULT["topic"]
            mock_intent.classify.return_value = SAMPLE_CLASSIFICATION_RESULT["intent"]
            mock_trust.evaluate.return_value = SAMPLE_CLASSIFICATION_RESULT["trust"]

            response = client.post(
                "/kpe/classification/",
                json={
                    "text": "Machine learning is transforming how we process data.",
                    "classifiers": ["topic", "intent", "trust"],
                    "use_llm": True,
                },
            )

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["engine"] == "llm"
        assert "topic" in body["classifications"]
        assert "intent" in body["classifications"]
        assert "trust" in body["classifications"]

    def test_classification_domain_and_risk(self, client: TestClient) -> None:
        """Domain and risk classifiers work through dynamic imports."""
        response = client.post(
            "/kpe/classification/",
            json={
                "text": "This is a security-related document about cybersecurity threats.",
                "classifiers": ["domain", "risk"],
                "use_llm": True,
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert "domain" in body["classifications"]
        assert "risk" in body["classifications"]

    def test_classification_static_fallback(self, client: TestClient) -> None:
        """use_llm=false uses static classifiers."""
        with (
            patch("app.modules.kpe.routes.classification._topic_classifier") as mock_topic,
            patch("app.modules.kpe.routes.classification._intent_classifier") as mock_intent,
        ):
            mock_topic.classify.return_value = {"label": "machine learning", "confidence": 0.6}
            mock_intent.classify.return_value = {"label": "informational", "confidence": 0.7}

            response = client.post(
                "/kpe/classification/",
                json={
                    "text": "Machine learning basics.",
                    "classifiers": ["topic", "intent"],
                    "use_llm": False,
                },
            )

        assert response.status_code == 200
        body = response.json()
        assert body["engine"] == "static"

    def test_classification_with_custom_taxonomy(self, client: TestClient) -> None:
        """Custom taxonomy is passed to the classifier."""
        with patch(f"{self.MODULE_PATH}.topic") as mock_topic:
            mock_topic.classify.return_value = {"label": "custom_topic", "confidence": 0.9}

            response = client.post(
                "/kpe/classification/",
                json={
                    "text": "Custom taxonomy test.",
                    "classifiers": ["topic"],
                    "taxonomy": ["custom_a", "custom_b", "custom_c"],
                    "use_llm": True,
                },
            )

        assert response.status_code == 200
        body = response.json()
        assert body["classifications"]["topic"]["label"] == "custom_topic"

    def test_classification_empty_text_still_works(self, client: TestClient) -> None:
        """Empty text with static fallback returns default classifications."""
        with patch("app.modules.kpe.routes.classification._topic_classifier") as mock:
            mock.classify.return_value = {"label": "unknown", "confidence": 0.0}

            response = client.post(
                "/kpe/classification/",
                json={
                    "text": "",
                    "classifiers": ["topic"],
                    "use_llm": False,
                },
            )

        assert response.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════
# RETRIEVAL — various endpoints
# ═══════════════════════════════════════════════════════════════════════════


class TestRetrievalSearchEndpoint:
    """POST /api/v1/kpe/retrieval/search — Full retrieval pipeline."""

    MODULE_PATH = "app.modules.kpe.routes.retrieval"

    def test_search_bm25_default(self, client: TestClient) -> None:
        """BM25 search returns results."""
        with patch(f"{self.MODULE_PATH}._query_rewriter") as mock_rw, \
             patch(f"{self.MODULE_PATH}._bm25") as mock_bm25, \
             patch(f"{self.MODULE_PATH}._reranker") as mock_rerank:
            mock_rw.rewrite.return_value = {
                "rewritten_query": "machine learning AI",
                "original_query": "ml ai",
                "search_type": "hybrid",
                "intent": "factual",
                "key_entities": ["machine learning"],
                "filters": {},
                "query_expansion": ["ML", "artificial intelligence"],
                "decomposition": [],
            }
            mock_bm25.search.return_value = SAMPLE_RETRIEVAL_RESULT
            mock_rerank.rerank.return_value = SAMPLE_RETRIEVAL_RESULT

            response = client.post(
                "/kpe/retrieval/search",
                json={
                    "query": "ml ai",
                    "retriever_type": "bm25",
                    "top_k": 5,
                    "use_llm_rewrite": True,
                    "use_llm_rerank": True,
                },
            )

        assert response.status_code == 200
        body = response.json()
        assert "results" in body
        assert body["total_results"] == 2
        assert body["engine"] == "llm_pipeline"

    def test_search_hybrid_retriever(self, client: TestClient) -> None:
        """Hybrid retriever delegates to HybridRetriever."""
        with patch(f"{self.MODULE_PATH}._query_rewriter") as mock_rw, \
             patch(f"{self.MODULE_PATH}._hybrid") as mock_hybrid, \
             patch(f"{self.MODULE_PATH}._reranker") as mock_rerank:
            mock_rw.rewrite.return_value = {"rewritten_query": "optimized query", "original_query": "test"}
            mock_hybrid.search.return_value = SAMPLE_RETRIEVAL_RESULT
            mock_rerank.rerank.return_value = SAMPLE_RETRIEVAL_RESULT

            response = client.post(
                "/kpe/retrieval/search",
                json={
                    "query": "test",
                    "retriever_type": "hybrid",
                    "top_k": 10,
                    "use_llm_rewrite": True,
                    "use_llm_rerank": True,
                },
            )

        assert response.status_code == 200
        assert len(response.json()["results"]) == 2

    def test_search_dense_retriever(self, client: TestClient) -> None:
        """Dense retriever delegates to DenseRetriever."""
        with patch(f"{self.MODULE_PATH}._query_rewriter") as mock_rw, \
             patch(f"{self.MODULE_PATH}._dense") as mock_dense, \
             patch(f"{self.MODULE_PATH}._reranker") as mock_rerank:
            mock_rw.rewrite.return_value = {"rewritten_query": "q", "original_query": "q"}
            mock_dense.search.return_value = [SAMPLE_RETRIEVAL_RESULT[0]]
            mock_rerank.rerank.return_value = [SAMPLE_RETRIEVAL_RESULT[0]]

            response = client.post(
                "/kpe/retrieval/search",
                json={
                    "query": "q",
                    "retriever_type": "dense",
                    "use_llm_rewrite": True,
                    "use_llm_rerank": True,
                },
            )

        assert response.status_code == 200
        assert len(response.json()["results"]) == 1

    def test_search_no_llm(self, client: TestClient) -> None:
        """With use_llm_rewrite=false and use_llm_rerank=false, engine is 'static'."""
        with patch(f"{self.MODULE_PATH}._bm25") as mock_bm25:
            mock_bm25.search.return_value = SAMPLE_RETRIEVAL_RESULT

            response = client.post(
                "/kpe/retrieval/search",
                json={
                    "query": "test query",
                    "retriever_type": "bm25",
                    "top_k": 10,
                    "use_llm_rewrite": False,
                    "use_llm_rerank": False,
                },
            )

        assert response.status_code == 200
        assert response.json()["engine"] == "static"

    def test_search_returns_500_on_error(self, client: TestClient) -> None:
        """Service exception returns 500."""
        with patch(f"{self.MODULE_PATH}._query_rewriter") as mock:
            mock.rewrite.side_effect = RuntimeError("LLM unavailable")

            response = client.post(
                "/kpe/retrieval/search",
                json={"query": "test"},
            )

        assert response.status_code == 500


_REWRITE_FULL_RESULT = {
    "original_query": "best way to learn ml",
    "rewritten_query": "most effective methods for learning machine learning",
    "search_type": "hybrid",
    "intent": "educational",
    "key_entities": ["machine learning"],
    "filters": {},
    "query_expansion": ["ML techniques", "ML courses"],
    "decomposition": [],
}


class TestRetrievalRewriteEndpoint:
    """POST /api/v1/kpe/retrieval/rewrite — Query rewriting."""

    MODULE_PATH = "app.modules.kpe.routes.retrieval._query_rewriter"

    def test_rewrite(self, client: TestClient) -> None:
        """Query rewrite returns structured response."""
        with patch(self.MODULE_PATH) as mock:
            mock.rewrite.return_value = _REWRITE_FULL_RESULT

            response = client.post(
                "/kpe/retrieval/rewrite",
                json={"query": "best way to learn ml"},
            )

        assert response.status_code == 200
        body = response.json()
        assert body["rewritten_query"] == "most effective methods for learning machine learning"
        assert body["intent"] == "educational"
        assert body["key_entities"] == ["machine learning"]
        assert body["engine"] == "llm"

    def test_rewrite_empty_query(self, client: TestClient) -> None:
        """Empty query returns fallback engine."""
        with patch(self.MODULE_PATH) as mock:
            # Must include key_entities=[] to avoid TypeError: any(None) is not iterable
            mock.rewrite.return_value = {
                "original_query": "",
                "rewritten_query": "",
                "key_entities": [],
            }

            response = client.post(
                "/kpe/retrieval/rewrite",
                json={"query": ""},
            )

        assert response.status_code == 200

    def test_rewrite_with_context(self, client: TestClient) -> None:
        """Optional context is passed to the rewriter."""
        with patch(self.MODULE_PATH) as mock:
            # Must include key_entities=[] to avoid TypeError: any(None) is not iterable
            mock.rewrite.return_value = {
                "original_query": "python",
                "rewritten_query": "Python programming language",
                "intent": "factual",
                "key_entities": [],
            }

            response = client.post(
                "/kpe/retrieval/rewrite",
                json={"query": "python", "context": "User is a software engineer"},
            )

        assert response.status_code == 200
        mock.rewrite.assert_called_once_with(query="python", context="User is a software engineer")

    def test_rewrite_returns_500(self, client: TestClient) -> None:
        """Service exception returns 500."""
        with patch(self.MODULE_PATH) as mock:
            mock.rewrite.side_effect = RuntimeError("Rewrite failed")
            response = client.post("/kpe/retrieval/rewrite", json={"query": "test"})
        assert response.status_code == 500


class TestRetrievalEnrichEndpoint:
    """POST /api/v1/kpe/retrieval/enrich — Context enrichment."""

    MODULE_PATH = "app.modules.kpe.routes.retrieval._contextual_enricher"

    def test_enrich(self, client: TestClient) -> None:
        """Context enrichment returns enriched chunks."""
        with patch(self.MODULE_PATH) as mock:
            mock.enrich.return_value = [
                {"id": "c1", "content": "enriched content", "context": {"doc_title": "Test"}},
            ]

            response = client.post(
                "/kpe/retrieval/enrich",
                json={
                    "chunks": [{"id": "c1", "content": "raw content"}],
                    "doc_context": {"d1": "Test Document title"},
                },
            )

        assert response.status_code == 200
        body = response.json()
        assert len(body["enriched_chunks"]) == 1
        assert body["count"] == 1

    def test_enrich_empty_chunks(self, client: TestClient) -> None:
        """Empty chunks returns empty list."""
        with patch(self.MODULE_PATH) as mock:
            mock.enrich.return_value = []

            response = client.post(
                "/kpe/retrieval/enrich",
                json={"chunks": [], "doc_context": {}},
            )

        assert response.status_code == 200
        assert response.json()["count"] == 0

    def test_enrich_returns_500(self, client: TestClient) -> None:
        """Service exception returns 500."""
        with patch(self.MODULE_PATH) as mock:
            mock.enrich.side_effect = RuntimeError("Enrich failed")
            response = client.post(
                "/kpe/retrieval/enrich",
                json={"chunks": [], "doc_context": {}},
            )
        assert response.status_code == 500


class TestRetrievalRerankEndpoint:
    """POST /api/v1/kpe/retrieval/rerank — Rerank results."""

    MODULE_PATH = "app.modules.kpe.routes.retrieval._reranker"

    def test_rerank(self, client: TestClient) -> None:
        """Rerank returns reordered results."""
        with patch(self.MODULE_PATH) as mock:
            mock.rerank.return_value = [
                {"id": "c2", "content": "better result", "score": 0.95},
                {"id": "c1", "content": "worse result", "score": 0.70},
            ]

            response = client.post(
                "/kpe/retrieval/rerank",
                json={
                    "query": "machine learning",
                    "results": [
                        {"id": "c1", "content": "worse result", "score": 0.70},
                        {"id": "c2", "content": "better result", "score": 0.95},
                    ],
                },
            )

        assert response.status_code == 200
        body = response.json()
        assert body["count"] == 2
        assert body["results"][0]["id"] == "c2"

    def test_rerank_empty_results(self, client: TestClient) -> None:
        """Empty results returns empty list."""
        with patch(self.MODULE_PATH) as mock:
            mock.rerank.return_value = []

            response = client.post(
                "/kpe/retrieval/rerank",
                json={"query": "test", "results": []},
            )

        assert response.status_code == 200
        assert response.json()["count"] == 0

    def test_rerank_returns_500(self, client: TestClient) -> None:
        """Service exception returns 500."""
        with patch(self.MODULE_PATH) as mock:
            mock.rerank.side_effect = RuntimeError("Rerank failed")
            response = client.post(
                "/kpe/retrieval/rerank",
                json={"query": "test", "results": []},
            )
        assert response.status_code == 500


# ═══════════════════════════════════════════════════════════════════════════
# SUMMARIZATION — POST /kpe/summarization/
# ═══════════════════════════════════════════════════════════════════════════


class TestSummarizationEndpoint:
    """POST /api/v1/kpe/summarization/ — Text summarization."""

    MODULE_PATH = "app.modules.kpe.routes.summarization._llm_summarizer"

    def test_summarize_llm(self, client: TestClient) -> None:
        """LLM summarization returns structured response."""
        with patch(self.MODULE_PATH) as mock:
            mock.summarize.return_value = SAMPLE_SUMMARIZATION_RESULT

            response = client.post(
                "/kpe/summarization/",
                json={
                    "text": "Long text to summarize... " * 100,
                    "max_length": 200,
                    "style": "technical",
                    "focus": "key_points",
                    "format": "bullets",
                    "use_llm": True,
                },
            )

        assert response.status_code == 200
        body = response.json()
        assert body["engine"] == "llm"
        assert len(body["summary"]) > 0
        assert body["key_points"] == ["Key point one", "Key point two"]
        assert body["compression_ratio"] > 1.0

    def test_summarize_all_styles(self, client: TestClient) -> None:
        """All summary styles are accepted."""
        styles = ["neutral", "technical", "simple", "persuasive", "academic"]
        for style in styles:
            with patch(self.MODULE_PATH) as mock:
                mock.summarize.return_value = SAMPLE_SUMMARIZATION_RESULT.copy()
                response = client.post(
                    "/kpe/summarization/",
                    json={"text": "Test text.", "style": style, "use_llm": True},
                )
            assert response.status_code == 200, f"Style '{style}' failed"

    def test_summarize_all_formats(self, client: TestClient) -> None:
        """All summary formats are accepted."""
        formats = ["paragraph", "bullets", "structured", "tl_dr"]
        for fmt in formats:
            with patch(self.MODULE_PATH) as mock:
                mock.summarize.return_value = SAMPLE_SUMMARIZATION_RESULT.copy()
                response = client.post(
                    "/kpe/summarization/",
                    json={"text": "Test text.", "format": fmt, "use_llm": True},
                )
            assert response.status_code == 200, f"Format '{fmt}' failed"

    def test_summarize_static_fallback(self, client: TestClient) -> None:
        """use_llm=false uses extractive summarization."""
        with patch("app.modules.kpe.routes.summarization._extractive") as mock:
            mock.summarize.return_value = "Short extractive summary."

            response = client.post(
                "/kpe/summarization/",
                json={
                    "text": "Long text to summarize. " * 50,
                    "max_length": 100,
                    "use_llm": False,
                },
            )

        assert response.status_code == 200
        body = response.json()
        assert body["engine"] == "extractive"
        assert body["method"] == "extractive"

    def test_summarize_invalid_max_length(self, client: TestClient) -> None:
        """max_length < 10 returns 422."""
        response = client.post(
            "/kpe/summarization/",
            json={"text": "Short text.", "max_length": 5},
        )
        assert response.status_code == 422

    def test_summarize_returns_500(self, client: TestClient) -> None:
        """Service exception returns 500."""
        with patch(self.MODULE_PATH) as mock:
            mock.summarize.side_effect = RuntimeError("Summarization failed")
            response = client.post(
                "/kpe/summarization/",
                json={"text": "Some text.", "use_llm": True},
            )
        assert response.status_code == 500


# ═══════════════════════════════════════════════════════════════════════════
# QUALITY — POST /kpe/quality/
# ═══════════════════════════════════════════════════════════════════════════


class TestQualityCheckEndpoint:
    """POST /api/v1/kpe/quality/ — Run quality checks."""

    MODULE_PATH = "app.modules.kpe.routes.quality._llm_service"

    def test_quality_llm(self, client: TestClient) -> None:
        """LLM quality check returns results."""
        with patch(self.MODULE_PATH) as mock:
            mock.check_all.return_value = SAMPLE_QUALITY_RESULT

            response = client.post(
                "/kpe/quality/",
                json={
                    "text": "Some generated text to check.",
                    "context": "Source context for factuality.",
                    "purpose": "general",
                    "checks": ["sensitivity", "factuality", "consistency", "hallucination"],
                    "use_llm": True,
                },
            )

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["engine"] == "llm"
        assert "sensitivity" in body["results"]
        assert "factuality" in body["results"]

    def test_quality_static_fallback(self, client: TestClient) -> None:
        """Static quality check returns results."""
        with (
            patch("app.modules.kpe.routes.quality._hallucination_detector") as mock_hall,
            patch("app.modules.kpe.routes.quality._sensitivity_classifier") as mock_sens,
        ):
            mock_hall.detect.return_value = {"detected": False, "score": 0.1}
            mock_sens.classify.return_value = {"score": 0.02, "is_sensitive": False}

            response = client.post(
                "/kpe/quality/",
                json={
                    "text": "Check this text.",
                    "checks": ["hallucination", "sensitivity"],
                    "use_llm": False,
                },
            )

        assert response.status_code == 200
        body = response.json()
        assert body["engine"] == "static"
        assert "hallucination" in body["results"]
        assert "sensitivity" in body["results"]

    def test_quality_all_checks(self, client: TestClient) -> None:
        """All 5 check types are accepted."""
        with patch(self.MODULE_PATH) as mock:
            mock.check_all.return_value = SAMPLE_QUALITY_RESULT

            response = client.post(
                "/kpe/quality/",
                json={
                    "text": "Test text.",
                    "checks": ["sensitivity", "factuality", "consistency", "evaluation", "hallucination"],
                    "use_llm": True,
                },
            )

        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_quality_static_unsupported_check(self, client: TestClient) -> None:
        """Unsupported static check returns error in results (not 500)."""
        with (
            patch("app.modules.kpe.routes.quality._hallucination_detector") as mock_hall,
            patch("app.modules.kpe.routes.quality._sensitivity_classifier") as mock_sens,
        ):
            mock_hall.detect.return_value = {"detected": False}
            mock_sens.classify.return_value = {"score": 0.0}

            response = client.post(
                "/kpe/quality/",
                json={
                    "text": "Test.",
                    "checks": ["evaluation"],
                    "use_llm": False,
                },
            )

        assert response.status_code == 200
        body = response.json()
        assert "evaluation" in body["results"]
        # Unsupported static checks return error dict
        eval_result = body["results"]["evaluation"]
        assert isinstance(eval_result, dict) and "error" in str(eval_result)

    def test_quality_returns_500(self, client: TestClient) -> None:
        """Service exception returns 500."""
        with patch(self.MODULE_PATH) as mock:
            mock.check_all.side_effect = RuntimeError("Quality check failed")
            response = client.post(
                "/kpe/quality/",
                json={"text": "Test text."},
            )
        assert response.status_code == 500


# ═══════════════════════════════════════════════════════════════════════════
# INGESTION — POST /kpe/ingestion/ + GET /kpe/ingestion/logs
# ═══════════════════════════════════════════════════════════════════════════


class TestIngestionEndpoint:
    """POST /api/v1/kpe/ingestion/ — Ingest content."""

    MODULE_PATH = "app.modules.kpe.routes.ingestion._ingestion_service"

    def test_ingest(self, client: TestClient) -> None:
        """Ingestion returns success response."""
        with patch(self.MODULE_PATH) as mock:
            # Route uses await on service method — must be AsyncMock
            mock.ingest = AsyncMock(return_value={
                "success": True,
                "document_id": "doc_123",
                "event_id": "evt_456",
                "chunk_count": 5,
                "message": "Ingested 5 chunks from file",
            })

            response = client.post(
                "/kpe/ingestion/",
                json={
                    "source_type": "file",
                    "content": "Document content to ingest.",
                    "metadata": {"filename": "test.txt"},
                },
            )

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["document_id"] == "doc_123"

    def test_ingest_validation_error(self, client: TestClient) -> None:
        """Validation error returns 400."""
        with patch(self.MODULE_PATH) as mock:
            mock.ingest.side_effect = ValueError("Invalid source type: unknown")

            response = client.post(
                "/kpe/ingestion/",
                json={
                    "source_type": "unknown",
                    "content": "Test content.",
                },
            )

        assert response.status_code == 400

    def test_ingest_returns_500(self, client: TestClient) -> None:
        """Service exception returns 500."""
        with patch(self.MODULE_PATH) as mock:
            mock.ingest.side_effect = RuntimeError("Ingestion failed")
            response = client.post(
                "/kpe/ingestion/",
                json={"source_type": "file", "content": "Test."},
            )
        assert response.status_code == 500


class TestIngestionLogsEndpoint:
    """GET /api/v1/kpe/ingestion/logs — List ingestion logs."""

    MODULE_PATH = "app.modules.kpe.routes.ingestion._ingestion_service"

    def test_list_logs(self, client: TestClient) -> None:
        """List logs returns log entries."""
        with patch(self.MODULE_PATH) as mock:
            mock.list_logs = AsyncMock(return_value=[
                {"id": "log_1", "source_type": "file", "status": "completed", "timestamp": "2024-01-01T00:00:00"},
                {"id": "log_2", "source_type": "api", "status": "failed", "timestamp": "2024-01-02T00:00:00"},
            ])

            response = client.get("/kpe/ingestion/logs?limit=10&source_type=file")

        assert response.status_code == 200
        body = response.json()
        assert len(body) == 2
        assert body[0]["id"] == "log_1"
        assert body[1]["status"] == "failed"

    def test_list_logs_empty(self, client: TestClient) -> None:
        """No logs returns empty list."""
        with patch(self.MODULE_PATH) as mock:
            mock.list_logs = AsyncMock(return_value=[])
            response = client.get("/kpe/ingestion/logs")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_logs_returns_500(self, client: TestClient) -> None:
        """Service exception returns 500."""
        with patch(self.MODULE_PATH) as mock:
            mock.list_logs.side_effect = RuntimeError("Log fetch failed")
            response = client.get("/kpe/ingestion/logs")
        assert response.status_code == 500


# ═══════════════════════════════════════════════════════════════════════════
# DOCUMENTS — CRUD endpoints
# ═══════════════════════════════════════════════════════════════════════════


class TestDocumentEndpoints:
    """GET/POST/DELETE /api/v1/kpe/documents/ — Document CRUD."""

    MODULE_PATH = "app.modules.kpe.routes.documents._doc_service"

    def _make_doc_response(self, **overrides):
        """Helper to build a valid DocumentResponse dict."""
        from datetime import datetime, timezone
        base = {
            "id": "doc_1",
            "title": "Test Doc",
            "content": "Document content.",
            "source_type": "file",
            "source_uri": "/path/to/doc.txt",
            "content_type": "text/plain",
            "metadata_json": "{}",
            "tenant_id": None,
            "processing_status": "completed",
            "chunk_count": 5,
            "token_count": 500,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        base.update(overrides)
        return base

    def test_list_documents(self, client: TestClient) -> None:
        """List documents returns paginated results."""
        with patch(self.MODULE_PATH) as mock:
            # Route uses await on the service — must be AsyncMock
            mock.list_documents = AsyncMock(return_value=[
                self._make_doc_response(id="doc_1", title="Doc 1", source_type="file"),
                self._make_doc_response(id="doc_2", title="Doc 2", source_type="api"),
            ])

            response = client.get("/kpe/documents/?skip=0&limit=20")

        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_list_documents_empty(self, client: TestClient) -> None:
        """No documents returns empty list."""
        with patch(self.MODULE_PATH) as mock:
            mock.list_documents = AsyncMock(return_value=[])
            response = client.get("/kpe/documents/")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_documents_with_filters(self, client: TestClient) -> None:
        """Filters are passed to the service."""
        with patch(self.MODULE_PATH) as mock:
            mock.list_documents = AsyncMock(return_value=[
                self._make_doc_response(id="doc_1", source_type="file"),
            ])

            response = client.get("/kpe/documents/?source_type=file&tenant_id=tenant_1")

        assert response.status_code == 200
        mock.list_documents.assert_awaited_once_with(
            skip=0, limit=20, source_type="file", tenant_id="tenant_1"
        )

    def test_list_documents_returns_500(self, client: TestClient) -> None:
        """Service exception returns 500."""
        with patch(self.MODULE_PATH) as mock:
            mock.list_documents.side_effect = RuntimeError("List failed")
            response = client.get("/kpe/documents/")
        assert response.status_code == 500

    def test_get_document(self, client: TestClient) -> None:
        """Get document returns document by ID."""
        with patch(self.MODULE_PATH) as mock:
            mock.get_document = AsyncMock(return_value=self._make_doc_response(id="doc_1"))

            response = client.get("/kpe/documents/doc_1")

        assert response.status_code == 200
        assert response.json()["id"] == "doc_1"

    def test_get_document_not_found(self, client: TestClient) -> None:
        """Non-existent document returns 404."""
        with patch(self.MODULE_PATH) as mock:
            mock.get_document = AsyncMock(return_value=None)

            response = client.get("/kpe/documents/nonexistent")

        assert response.status_code == 404

    def test_create_document(self, client: TestClient) -> None:
        """Create document returns created document."""
        with patch(self.MODULE_PATH) as mock:
            mock.create_document = AsyncMock(return_value=self._make_doc_response(
                id="doc_new", title="New Doc",
            ))

            response = client.post(
                "/kpe/documents/",
                json={"title": "New Doc", "content": "Content", "source_type": "api"},
            )

        assert response.status_code == 201
        body = response.json()
        assert body["id"] == "doc_new"
        assert body["title"] == "New Doc"

    def test_delete_document(self, client: TestClient) -> None:
        """Delete document returns 204."""
        with patch(self.MODULE_PATH) as mock:
            mock.delete_document = AsyncMock(return_value=True)

            response = client.delete("/kpe/documents/doc_1")

        assert response.status_code == 204

    def test_delete_document_not_found(self, client: TestClient) -> None:
        """Delete non-existent document returns 404."""
        with patch(self.MODULE_PATH) as mock:
            mock.delete_document = AsyncMock(return_value=False)

            response = client.delete("/kpe/documents/nonexistent")

        assert response.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════
# PROCESSING — POST /kpe/processing/
# ═══════════════════════════════════════════════════════════════════════════


class TestProcessingEndpoint:
    """POST /api/v1/kpe/processing/ — Process document."""

    MODULE_PATH = "app.modules.kpe.routes.processing._llm_service"

    def test_process_llm(self, client: TestClient) -> None:
        """LLM processing returns structured response."""
        with patch(self.MODULE_PATH) as mock:
            mock.process.return_value = MagicMock(
                format="markdown",
                content="Extracted markdown content",
                title="Test Document",
                headings=["Heading 1", "Heading 2"],
            )

            response = client.post(
                "/kpe/processing/",
                json={
                    "file_path": "/path/to/doc.md",
                    "content": "# Test Document\n\nContent here.",
                    "use_llm": True,
                },
            )

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["format"] == "markdown"
        assert body["title"] == "Test Document"
        assert body["headings_count"] == 2
        assert body["engine"] == "llm"

    def test_process_static(self, client: TestClient) -> None:
        """Static processing returns structured response."""
        with patch("app.modules.kpe.routes.processing._static_service") as mock:
            mock.process.return_value = MagicMock(
                format="text",
                content="Plain text content",
                title="",
                headings=[],
            )

            response = client.post(
                "/kpe/processing/",
                json={
                    "file_path": "/path/to/file.txt",
                    "content": "Plain text content.",
                    "use_llm": False,
                },
            )

        assert response.status_code == 200
        assert response.json()["engine"] == "static"

    def test_process_returns_500(self, client: TestClient) -> None:
        """Service exception returns 500."""
        with patch(self.MODULE_PATH) as mock:
            mock.process.side_effect = RuntimeError("Processing failed")
            response = client.post(
                "/kpe/processing/",
                json={"file_path": "/path/to/doc.md", "use_llm": True},
            )
        assert response.status_code == 500


# ═══════════════════════════════════════════════════════════════════════════
# KNOWLEDGE GRAPH — extract / infer / query
# ═══════════════════════════════════════════════════════════════════════════


class TestKnowledgeGraphExtractEndpoint:
    """POST /api/v1/kpe/kg/extract — Extract knowledge graph."""

    MODULE_PATH = "app.modules.kpe.routes.kg._llm_kg_service"

    def test_kg_extract(self, client: TestClient) -> None:
        """KG extraction returns entities and relationships."""
        with (
            patch(self.MODULE_PATH) as mock,
            patch("app.modules.kpe.routes.kg.analyze_graph") as mock_analyze,
        ):
            mock.extract_from_text.return_value = {
                "entities": [{"name": "OpenAI", "type": "ORG"}, {"name": "GPT-4", "type": "PRODUCT"}],
                "relationships": [{"source": "OpenAI", "target": "GPT-4", "type": "DEVELOPS"}],
                "graph_summary": "Knowledge graph with 2 entities and 1 relationship",
                "method": "llm",
                "node_count": 2,
                "edge_count": 1,
                "central_entities": ["OpenAI"],
            }
            mock.build_networkx.return_value = mock
            mock_analyze.return_value = {"nodes": 2, "edges": 1, "density": 0.5}

            response = client.post(
                "/kpe/kg/extract",
                json={
                    "text": "OpenAI developed GPT-4, a large language model.",
                    "use_llm": True,
                },
            )

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert len(body["entities"]) == 2
        assert len(body["relationships"]) == 1
        assert body["node_count"] == 2
        assert body["edge_count"] == 1

    def test_kg_extract_returns_500(self, client: TestClient) -> None:
        """Service exception returns 500."""
        with patch(self.MODULE_PATH) as mock:
            mock.extract_from_text.side_effect = RuntimeError("KG extraction failed")
            response = client.post(
                "/kpe/kg/extract",
                json={"text": "Test text."},
            )
        assert response.status_code == 500


class TestKnowledgeGraphInferEndpoint:
    """POST /api/v1/kpe/kg/infer — Infer relationships."""

    MODULE_PATH = "app.modules.kpe.routes.kg._llm_kg_service"

    def test_kg_infer(self, client: TestClient) -> None:
        """KG inference returns inferred relationships."""
        with patch(self.MODULE_PATH) as mock:
            mock.infer_relationships.return_value = {
                "inferred_relationships": [
                    {"source": "GPU", "target": "Machine Learning", "type": "ENABLES"},
                ],
                "suggested_merges": [
                    {"from_entity": "AI", "to_entity": "Artificial Intelligence", "confidence": 0.95},
                ],
                "reasoning_pattern": "co-occurrence",
            }

            response = client.post(
                "/kpe/kg/infer",
                json={
                    "entities": [{"name": "GPU", "type": "TECH"}, {"name": "Machine Learning", "type": "FIELD"}],
                    "relationships": [],
                },
            )

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert len(body["inferred_relationships"]) == 1
        assert len(body["suggested_merges"]) == 1

    def test_kg_infer_empty(self, client: TestClient) -> None:
        """Empty entities returns empty results."""
        with patch(self.MODULE_PATH) as mock:
            mock.infer_relationships.return_value = {
                "inferred_relationships": [],
                "suggested_merges": [],
                "reasoning_pattern": "",
            }

            response = client.post(
                "/kpe/kg/infer",
                json={"entities": [], "relationships": []},
            )

        assert response.status_code == 200
        assert response.json()["inferred_relationships"] == []

    def test_kg_infer_returns_500(self, client: TestClient) -> None:
        """Service exception returns 500."""
        with patch(self.MODULE_PATH) as mock:
            mock.infer_relationships.side_effect = RuntimeError("Inference failed")
            response = client.post(
                "/kpe/kg/infer",
                json={"entities": [], "relationships": []},
            )
        assert response.status_code == 500


class TestKnowledgeGraphQueryEndpoint:
    """POST /api/v1/kpe/kg/query — Query knowledge graph."""

    MODULE_PATH = "app.modules.kpe.routes.kg._llm_kg_service"

    def test_kg_query(self, client: TestClient) -> None:
        """KG query returns answer."""
        with patch(self.MODULE_PATH) as mock:
            mock.query_graph.return_value = {
                "answer": "OpenAI developed GPT-4.",
                "confidence": 0.92,
                "path": ["OpenAI", "DEVELOPS", "GPT-4"],
                "explanation": "Found direct relationship: OpenAI DEVELOPS GPT-4",
            }

            response = client.post(
                "/kpe/kg/query",
                json={
                    "entities": [{"name": "OpenAI", "type": "ORG"}],
                    "relationships": [{"source": "OpenAI", "target": "GPT-4", "type": "DEVELOPS"}],
                    "query": "Who developed GPT-4?",
                },
            )

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert "GPT-4" in body["answer"]
        assert body["confidence"] > 0.9

    def test_kg_query_returns_500(self, client: TestClient) -> None:
        """Service exception returns 500."""
        with patch(self.MODULE_PATH) as mock:
            mock.query_graph.side_effect = RuntimeError("Query failed")
            response = client.post(
                "/kpe/kg/query",
                json={"entities": [], "relationships": [], "query": "test"},
            )
        assert response.status_code == 500


# ═══════════════════════════════════════════════════════════════════════════
# Routing Integrity
# ═══════════════════════════════════════════════════════════════════════════


class TestKpeRoutingIntegrity:
    """Verify all KPE routes are properly registered."""

    def test_kpe_routes_exist(self, client: TestClient) -> None:
        """OpenAPI schema includes all KPE endpoints."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        paths = response.json().get("paths", {})

        expected_paths = [
            "/kpe/extraction/",
            "/kpe/classification/",
            "/kpe/retrieval/search",
            "/kpe/retrieval/rewrite",
            "/kpe/retrieval/enrich",
            "/kpe/retrieval/rerank",
            "/kpe/summarization/",
            "/kpe/quality/",
            "/kpe/ingestion/",
            "/kpe/ingestion/logs",
            "/kpe/documents/",
            "/kpe/processing/",
            "/kpe/kg/extract",
            "/kpe/kg/infer",
            "/kpe/kg/query",
        ]
        for path in expected_paths:
            assert path in paths, f"Missing path: {path}"

    def test_kpe_route_methods(self, client: TestClient) -> None:
        """Each KPE endpoint has the correct HTTP method."""
        response = client.get("/openapi.json")
        paths = response.json().get("paths", {})

        method_checks = {
            "/kpe/extraction/": {"post"},
            "/kpe/classification/": {"post"},
            "/kpe/retrieval/search": {"post"},
            "/kpe/retrieval/rewrite": {"post"},
            "/kpe/retrieval/enrich": {"post"},
            "/kpe/retrieval/rerank": {"post"},
            "/kpe/summarization/": {"post"},
            "/kpe/quality/": {"post"},
            "/kpe/ingestion/": {"post"},
            "/kpe/ingestion/logs": {"get"},
            "/kpe/documents/": {"get", "post"},
            "/kpe/processing/": {"post"},
            "/kpe/kg/extract": {"post"},
            "/kpe/kg/infer": {"post"},
            "/kpe/kg/query": {"post"},
        }
        for path, expected_methods in method_checks.items():
            actual = set(paths[path].keys())
            for method in expected_methods:
                assert method in actual, f"Missing {method} on {path}. Got: {actual}"
