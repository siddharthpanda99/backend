"""
Comprehensive unit tests for all KPE MCP Tools.

Covers:
  - kpe_extract        — entity/relation/fact/keyword/event/sentiment extraction
  - kpe_classify       — LLM-based topic/intent/trust/domain/risk classification
  - kpe_classify_static — static keyword-based classification
  - kpe_summarize      — abstractive summarization
  - kpe_check_quality  — multi-dimensional quality assessment
  - kpe_detect_hallucination — hallucination detection
  - kpe_check_sensitivity    — sensitive content detection
  - kpe_score_confidence     — quality/relevance/confidence scoring

Usage:
    cd Backend Monorepo/Backend
    uv run python -m pytest app/mcp/tools/tests/test_mcp_kpe_full.py -v
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.mcp.fastmcp_compat import FastMCP

from app.mcp.tools.kpe import register_kpe_tools


# ── Helpers ───────────────────────────────────────────────────────────────


def extract_call_tool_data(result: tuple) -> Any:
    """Extract response data from a FastMCP call_tool result tuple."""
    if isinstance(result, tuple) and len(result) >= 2:
        raw = result[1]
        if isinstance(raw, dict) and "result" in raw:
            return raw["result"]
        return raw
    return result


def _new_server() -> FastMCP:
    srv = FastMCP("test-kpe-full")
    register_kpe_tools(srv)
    return srv


# ═══════════════════════════════════════════════════════════════════════════
# kpe_extract
# ═══════════════════════════════════════════════════════════════════════════


SAMPLE_ENTITIES = [
    {"name": "Python", "type": "PROGRAMMING_LANGUAGE", "confidence": 0.98},
    {"name": "FastAPI", "type": "FRAMEWORK", "confidence": 0.95},
]
SAMPLE_RELATIONSHIPS = [
    {"source": "FastAPI", "target": "Python", "relation": "built_with", "confidence": 0.9},
]
SAMPLE_FACTS = [
    {"fact": "FastAPI is a modern web framework", "confidence": 0.97},
]
SAMPLE_EVENTS = [
    {"event": "Python 3.12 release", "date": "2023-10-02", "confidence": 0.85},
]
SAMPLE_KEYWORDS = ["FastAPI", "Python", "web framework", "async"]
SAMPLE_SENTIMENT = {"sentiment": "positive", "score": 0.92, "magnitude": 0.7}


class TestKpeExtract:
    """kpe_extract — response shape and dispatch verification."""

    EXTRACT_PATH = "app.mcp.tools.kpe._extraction_service"

    @pytest.fixture
    def mock_extraction(self) -> MagicMock:
        """Patch the module-level _extraction_service with mocked sub-services."""
        mock_svc = MagicMock()
        mock_svc.entity_extractor = MagicMock()
        mock_svc.entity_extractor.extract.return_value = SAMPLE_ENTITIES
        mock_svc.event_extractor = MagicMock()
        mock_svc.event_extractor.extract.return_value = SAMPLE_EVENTS
        mock_svc.keyword_extractor = MagicMock()
        mock_svc.keyword_extractor.extract.return_value = SAMPLE_KEYWORDS
        mock_svc.sentiment_analyzer = MagicMock()
        mock_svc.sentiment_analyzer.analyze.return_value = SAMPLE_SENTIMENT
        return mock_svc

    def _run(self, params: dict, mock_svc: MagicMock) -> dict:
        with patch(self.EXTRACT_PATH, mock_svc):
            server = _new_server()
            result = asyncio.run(server.call_tool("kpe_extract", params))
            return extract_call_tool_data(result)

    def test_basic_extraction(self, mock_extraction: MagicMock) -> None:
        """Default extractors (entities, relationships, facts) produce correct keys."""
        # relationships & facts aren't handled by the tool — they silently pass
        # since the tool only dispatches entities|events|keywords|sentiment
        data = self._run({"text": "FastAPI is built with Python"}, mock_extraction)

        assert data["success"] is True
        assert data["text_length"] == 28
        assert "entities" in data["results"]
        assert data["extractors_used"] == ["entities", "relationships", "facts"]

    def test_custom_extractors(self, mock_extraction: MagicMock) -> None:
        """Custom extractor list is reflected in response."""
        data = self._run(
            {"text": "Python 3.12 was released", "extractors": ["entities", "events", "keywords"]},
            mock_extraction,
        )
        assert data["extractors_used"] == ["entities", "events", "keywords"]
        assert "entities" in data["results"]
        assert "events" in data["results"]
        assert "keywords" in data["results"]
        assert data["extractors_completed"] == 3

    def test_sentiment_extractor(self, mock_extraction: MagicMock) -> None:
        """Sentiment analyzer returns structured result."""
        data = self._run(
            {"text": "I love this!", "extractors": ["sentiment"]},
            mock_extraction,
        )
        assert "sentiment" in data["results"]
        assert data["results"]["sentiment"]["sentiment"] == "positive"
        assert data["results"]["sentiment"]["score"] == 0.92

    def test_extractor_error_handling(self, mock_extraction: MagicMock) -> None:
        """If an extractor raises, the tool returns error dict per extractor."""
        mock_extraction.entity_extractor.extract.side_effect = ValueError("Model not loaded")

        data = self._run(
            {"text": "test", "extractors": ["entities", "keywords"]},
            mock_extraction,
        )
        assert "entities" in data["results"]
        assert "error" in data["results"]["entities"]
        assert "Model not loaded" in data["results"]["entities"]["error"]
        assert "keywords" in data["results"]

    def test_response_keys(self, mock_extraction: MagicMock) -> None:
        """Verify all expected response keys."""
        data = self._run({"text": "hello"}, mock_extraction)
        assert set(data.keys()) == {
            "success", "text_length", "extractors_used",
            "extractors_completed", "results",
        }

    def test_text_length_accurate(self, mock_extraction: MagicMock) -> None:
        """Text length is correctly reported."""
        data = self._run({"text": "Hello world!"}, mock_extraction)
        assert data["text_length"] == 12


# ═══════════════════════════════════════════════════════════════════════════
# kpe_classify
# ═══════════════════════════════════════════════════════════════════════════


SAMPLE_TOPIC = {"label": "machine learning", "confidence": 0.94}
SAMPLE_INTENT = {"intent": "informational", "confidence": 0.88}
SAMPLE_TRUST = {"trustworthiness": 0.82, "flags": []}
SAMPLE_DOMAIN = {"domain": "technology", "confidence": 0.91}
SAMPLE_RISK = {"risk_level": "low", "score": 0.12}


class TestKpeClassify:
    """kpe_classify — response shape and dispatch verification."""

    CLASSIFY_PATH = "app.mcp.tools.kpe._classification_service"

    @pytest.fixture
    def mock_classification(self) -> MagicMock:
        mock_svc = MagicMock()
        mock_svc.topic = MagicMock()
        mock_svc.topic.classify.return_value = SAMPLE_TOPIC
        mock_svc.intent = MagicMock()
        mock_svc.intent.classify.return_value = SAMPLE_INTENT
        mock_svc.trust = MagicMock()
        mock_svc.trust.evaluate.return_value = SAMPLE_TRUST
        return mock_svc

    def _run(self, params: dict, mock_svc: MagicMock) -> dict:
        with patch(self.CLASSIFY_PATH, mock_svc):
            server = _new_server()
            result = asyncio.run(server.call_tool("kpe_classify", params))
            return extract_call_tool_data(result)

    def test_basic_classification(self, mock_classification: MagicMock) -> None:
        """Default classifiers (topic, intent, trust) return results."""
        data = self._run({"text": "Machine learning is transforming AI"}, mock_classification)

        assert data["success"] is True
        assert "topic" in data["classifications"]
        assert "intent" in data["classifications"]
        assert "trust" in data["classifications"]
        assert data["classifiers_used"] == ["topic", "intent", "trust"]

    def test_custom_classifiers(self, mock_classification: MagicMock) -> None:
        """Custom classifier list is reflected."""
        data = self._run(
            {"text": "test", "classifiers": ["topic", "intent"]},
            mock_classification,
        )
        assert data["classifiers_used"] == ["topic", "intent"]
        assert data["classifiers_completed"] == 2

    def test_domain_classifier(self, mock_classification: MagicMock) -> None:
        """Domain classifier dispatches correctly (lazy-imported)."""
        with patch("app.mcp.tools.kpe.DenseEmbedder"):  # avoid import side effects
            data = self._run(
                {"text": "technology news", "classifiers": ["domain"]},
                mock_classification,
            )
        assert data["classifiers_used"] == ["domain"]
        assert data["classifiers_completed"] == 1

    def test_all_classifiers(self, mock_classification: MagicMock) -> None:
        """All 5 classifiers run without error."""
        data = self._run(
            {"text": "test", "classifiers": ["topic", "intent", "trust", "domain", "risk"]},
            mock_classification,
        )
        assert data["classifiers_completed"] == 5

    def test_response_keys(self, mock_classification: MagicMock) -> None:
        """Verify all expected response keys."""
        data = self._run({"text": "hello"}, mock_classification)
        assert set(data.keys()) == {
            "success", "text_length", "classifiers_used",
            "classifiers_completed", "classifications",
        }


# ═══════════════════════════════════════════════════════════════════════════
# kpe_classify_static
# ═══════════════════════════════════════════════════════════════════════════


SAMPLE_STATIC_TOPIC = {"label": "security", "confidence": 0.72}
SAMPLE_STATIC_INTENT = {"intent": "informational", "confidence": 0.65}


class TestKpeClassifyStatic:
    """kpe_classify_static — response shape and dispatch."""

    @staticmethod
    def _run(params: dict) -> dict:
        with (
            patch("app.mcp.tools.kpe._topic_classifier.classify", return_value=SAMPLE_STATIC_TOPIC),
            patch("app.mcp.tools.kpe._intent_classifier.classify", return_value=SAMPLE_STATIC_INTENT),
        ):
            server = _new_server()
            result = asyncio.run(server.call_tool("kpe_classify_static", params))
            return extract_call_tool_data(result)

    def test_basic_static_classification(self) -> None:
        """Returns topic and intent with static engine."""
        data = self._run({"text": "cloud security best practices"})
        assert data["success"] is True
        assert data["engine"] == "static"
        assert data["topic"]["label"] == "security"
        assert data["intent"]["intent"] == "informational"

    def test_custom_taxonomy(self) -> None:
        """Custom taxonomy is accepted."""
        data = self._run({"text": "hello", "taxonomy": ["python", "rust", "go"]})
        assert data["success"] is True
        assert data["text_length"] == 5

    def test_response_keys(self) -> None:
        """Verify all expected response keys."""
        data = self._run({"text": "hello"})
        assert set(data.keys()) == {
            "success", "engine", "topic", "intent", "text_length",
        }


# ═══════════════════════════════════════════════════════════════════════════
# kpe_summarize
# ═══════════════════════════════════════════════════════════════════════════


SAMPLE_SUMMARY_RESULT = {
    "summary": "FastAPI is a modern Python web framework.",
    "compression_ratio": 3.2,
    "method": "llm",
    "original_length": 50,
    "summary_length": 10,
    "key_points": ["FastAPI is modern", "Built on Python"],
    "tone": "neutral",
}


class TestKpeSummarize:
    """kpe_summarize — response shape and dispatch verification."""

    SUMMARIZE_PATH = "app.mcp.tools.kpe._summarizer.summarize"

    @staticmethod
    def _run(params: dict) -> dict:
        with patch(TestKpeSummarize.SUMMARIZE_PATH, return_value=SAMPLE_SUMMARY_RESULT):
            server = _new_server()
            result = asyncio.run(server.call_tool("kpe_summarize", params))
            return extract_call_tool_data(result)

    def test_basic_summarization(self) -> None:
        """Default params produce a summary with metadata."""
        data = self._run({"text": "FastAPI is a modern Python web framework for building APIs."})
        assert data["success"] is True
        assert data["summary"] == SAMPLE_SUMMARY_RESULT["summary"]
        assert data["compression_ratio"] == 3.2
        assert data["engine"] == "llm"

    def test_custom_style(self) -> None:
        """Custom style is reflected in tone (via side_effect mock)."""
        # Use side_effect so the mock reflects the passed style back
        def summarize_side_effect(**kwargs):
            return {
                **SAMPLE_SUMMARY_RESULT,
                "tone": kwargs.get("style", "neutral"),
            }

        with patch(TestKpeSummarize.SUMMARIZE_PATH, side_effect=summarize_side_effect):
            server = _new_server()
            result = asyncio.run(server.call_tool(
                "kpe_summarize",
                {"text": "Technical documentation text here. " * 10, "style": "technical"},
            ))
            data = extract_call_tool_data(result)

        assert data["tone"] == "technical"

    def test_custom_format(self) -> None:
        """Custom format produces valid response."""
        data = self._run({
            "text": "Some text to summarize. " * 20,
            "format_type": "bullets",
        })
        assert data["success"] is True

    def test_custom_focus(self) -> None:
        """Custom focus area works."""
        data = self._run({
            "text": "Event timeline text. " * 30,
            "focus": "timeline",
        })
        assert data["success"] is True

    def test_response_keys(self) -> None:
        """Verify all expected response keys."""
        data = self._run({"text": "Short text for testing purposes."})
        assert set(data.keys()) == {
            "success", "summary", "compression_ratio", "method",
            "original_length", "summary_length", "key_points",
            "tone", "engine",
        }


# ═══════════════════════════════════════════════════════════════════════════
# kpe_check_quality
# ═══════════════════════════════════════════════════════════════════════════


SAMPLE_QUALITY_RESULTS = {
    "sensitivity": {"is_sensitive": False, "score": 0.01, "flags": []},
    "factuality": {"supported": True, "score": 0.95, "details": "All claims verifiable"},
    "consistency": {"internal_consistency": True, "score": 0.91},
    "evaluation": {"overall": 0.88, "clarity": 0.85, "coherence": 0.90},
    "hallucination": {"detected": False, "score": 0.02, "flagged_statements": []},
}

SAMPLE_QUALITY_RESULTS_ISSUES = {
    "sensitivity": {"is_sensitive": True, "score": 0.85, "flags": ["offensive_language"]},
    "factuality": {"supported": False, "score": 0.30, "details": "Unsupported claims"},
    "consistency": {"internal_consistency": False, "score": 0.40},
    "evaluation": {"overall": 0.45, "clarity": 0.40, "coherence": 0.50},
    "hallucination": {"detected": True, "score": 0.78, "flagged_statements": ["Claim X is false"]},
}


class TestKpeCheckQuality:
    """kpe_check_quality — response shape and dispatch."""

    QUALITY_PATH = "app.mcp.tools.kpe._quality_service.check_all"

    @staticmethod
    def _run(params: dict, return_value: dict | None = None) -> dict:
        rv = return_value if return_value is not None else SAMPLE_QUALITY_RESULTS
        with patch(TestKpeCheckQuality.QUALITY_PATH, return_value=rv):
            server = _new_server()
            result = asyncio.run(server.call_tool("kpe_check_quality", params))
            return extract_call_tool_data(result)

    def test_all_checks(self) -> None:
        """All 5 checks return results."""
        data = self._run({"text": "Some generated text to check."})
        assert data["success"] is True
        assert data["checks_completed"] == 5
        for check in ("sensitivity", "factuality", "consistency", "evaluation", "hallucination"):
            assert check in data["results"]

    def test_custom_checks(self) -> None:
        """Only requested checks are performed."""
        data = self._run({
            "text": "test",
            "checks": ["sensitivity", "hallucination"],
        })
        assert data["checks_completed"] == 2

    def test_with_context(self) -> None:
        """Context is passed through to quality service."""
        data = self._run({
            "text": "Generated summary",
            "context": "Source document context here",
        })
        assert data["success"] is True
        assert data["text_length"] == 17

    def test_issues_generate_recommendation(self) -> None:
        """When issues are detected, recommendation lists them."""
        data = self._run(
            {"text": "Bad content with issues"},
            return_value=SAMPLE_QUALITY_RESULTS_ISSUES,
        )
        assert "sensitive content" in data["recommendation"]
        assert "hallucination" in data["recommendation"]
        assert "unsupported factual claims" in data["recommendation"]

    def test_clean_generates_positive_recommendation(self) -> None:
        """When no issues, recommendation says clean."""
        data = self._run({"text": "Clean content."})
        assert "No quality issues detected" in data["recommendation"]

    def test_response_keys(self) -> None:
        """Verify all expected response keys."""
        data = self._run({"text": "test"})
        assert set(data.keys()) == {
            "success", "text_length", "checks_completed",
            "results", "recommendation",
        }


# ═══════════════════════════════════════════════════════════════════════════
# kpe_detect_hallucination
# ═══════════════════════════════════════════════════════════════════════════


HALLUCINATION_DETECTED_RESULT = {
    "detected": True,
    "score": 0.85,
    "flagged_statements": ["Claim A is not in the source"],
}

HALLUCINATION_CLEAN_RESULT = {
    "detected": False,
    "score": 0.05,
    "flagged_statements": [],
}


class TestKpeDetectHallucination:
    """kpe_detect_hallucination — response shape and dispatch."""

    # Note: HallucinationDetector is lazily imported inside the tool function body
    # (from common_lib.modules.knowledge_engine.kpe.quality.hallucination), so we patch the source
    # module rather than app.mcp.tools.kpe where it's NOT a module-level name.
    HALLUC_PATH = "common_lib.modules.knowledge_engine.kpe.quality.hallucination.HallucinationDetector"

    @staticmethod
    def _run(params: dict, detect_result: dict | None = None) -> dict:
        dr = detect_result if detect_result is not None else HALLUCINATION_CLEAN_RESULT
        mock_instance = MagicMock()
        mock_instance.detect.return_value = dr

        with patch(TestKpeDetectHallucination.HALLUC_PATH, return_value=mock_instance):
            server = _new_server()
            result = asyncio.run(server.call_tool("kpe_detect_hallucination", params))
            return extract_call_tool_data(result)

    def test_hallucination_detected(self) -> None:
        """When hallucination is detected, verdict reflects it."""
        data = self._run(
            {"text": "Claim A is false", "source_context": "Source says B is true"},
            HALLUCINATION_DETECTED_RESULT,
        )
        assert data["success"] is True
        assert data["hallucination_detected"] is True
        assert data["hallucination_score"] == 0.85
        assert len(data["flagged_statements"]) == 1
        assert data["verdict"] == "likely hallucinated"

    def test_no_hallucination(self) -> None:
        """When no hallucination, verdict says factual."""
        data = self._run(
            {"text": "Claim B is true", "source_context": "Source says B is true"},
            HALLUCINATION_CLEAN_RESULT,
        )
        assert data["hallucination_detected"] is False
        assert data["hallucination_score"] == 0.05
        assert data["verdict"] == "likely factual"

    def test_response_keys(self) -> None:
        """Verify all expected response keys."""
        data = self._run({"text": "test", "source_context": "context"})
        assert set(data.keys()) == {
            "success", "hallucination_detected", "hallucination_score",
            "flagged_statements", "verdict",
        }


# ═══════════════════════════════════════════════════════════════════════════
# kpe_check_sensitivity
# ═══════════════════════════════════════════════════════════════════════════


SENSITIVE_RESULT = {
    "is_sensitive": True,
    "score": 0.92,
    "flagged_categories": ["offensive_language"],
    "details": {"category_scores": {"offensive_language": 0.92}},
}

CLEAN_RESULT = {
    "is_sensitive": False,
    "score": 0.01,
    "flagged_categories": [],
    "details": {},
}


class TestKpeCheckSensitivity:
    """kpe_check_sensitivity — response shape and dispatch."""

    # Note: SensitivityClassifier is lazily imported inside the tool function body
    # (from common_lib.modules.knowledge_engine.kpe.quality.sensitivity), so we patch the source
    # module rather than app.mcp.tools.kpe.
    SENS_PATH = "common_lib.modules.knowledge_engine.kpe.quality.sensitivity.SensitivityClassifier"

    @staticmethod
    def _run(params: dict, result: dict | None = None) -> dict:
        rv = result if result is not None else CLEAN_RESULT
        mock_instance = MagicMock()
        mock_instance.classify.return_value = rv

        with patch(TestKpeCheckSensitivity.SENS_PATH, return_value=mock_instance):
            server = _new_server()
            result_data = asyncio.run(server.call_tool("kpe_check_sensitivity", params))
            return extract_call_tool_data(result_data)

    def test_sensitive_content_flagged(self) -> None:
        """Sensitive content returns flagged categories."""
        data = self._run({"text": "Offensive text here"}, SENSITIVE_RESULT)
        assert data["success"] is True
        assert data["is_sensitive"] is True
        assert data["sensitivity_score"] == 0.92
        assert "offensive_language" in data["flagged_categories"]

    def test_clean_content(self) -> None:
        """Clean content passes all checks."""
        data = self._run({"text": "Clean text here"})
        assert data["is_sensitive"] is False
        assert data["sensitivity_score"] == 0.01
        assert data["flagged_categories"] == []

    def test_response_keys(self) -> None:
        """Verify all expected response keys."""
        data = self._run({"text": "test"})
        assert set(data.keys()) == {
            "success", "is_sensitive", "sensitivity_score",
            "flagged_categories", "details",
        }


# ═══════════════════════════════════════════════════════════════════════════
# kpe_score_confidence
# ═══════════════════════════════════════════════════════════════════════════


SCORE_RESULTS = {
    "consistency": {"internal_consistency": True, "score": 0.91},
    "evaluation": {"overall": 0.88, "clarity": 0.85, "coherence": 0.90},
    "factuality": {"supported": True, "score": 0.95},
}

SCORE_RESULTS_NO_SCORE = {
    "consistency": {"internal_consistency": True},
    "evaluation": {"clarity": 0.85},
}


class TestKpeScoreConfidence:
    """kpe_score_confidence — response shape and dispatch."""

    SCORE_PATH = "app.mcp.tools.kpe._quality_service.check_all"

    @staticmethod
    def _run(params: dict, return_value: dict | None = None) -> dict:
        rv = return_value if return_value is not None else SCORE_RESULTS
        with patch(TestKpeScoreConfidence.SCORE_PATH, return_value=rv):
            server = _new_server()
            result = asyncio.run(server.call_tool("kpe_score_confidence", params))
            return extract_call_tool_data(result)

    def test_quality_scoring(self) -> None:
        """Quality scoring returns overall and dimension scores."""
        data = self._run({"text": "Some text to score"})
        assert data["success"] is True
        assert data["score_type"] == "quality"
        assert isinstance(data["overall_score"], float)
        assert "consistency" in data["dimension_scores"]
        assert "evaluation" in data["dimension_scores"]
        assert data["has_context"] is False

    def test_confidence_scoring(self) -> None:
        """Confidence scoring includes factuality check."""
        data = self._run({
            "text": "text",
            "score_type": "confidence",
        })
        assert data["score_type"] == "confidence"
        assert "factuality" in data["dimension_scores"]

    def test_scoring_with_context(self) -> None:
        """Context flag reflected in response."""
        data = self._run({
            "text": "text",
            "context": "Relevant context",
        })
        assert data["has_context"] is True

    def test_fallback_scores_when_missing(self) -> None:
        """When results have no numeric scores, falls back to 0.5."""
        data = self._run(
            {"text": "text"},
            SCORE_RESULTS_NO_SCORE,
        )
        # consistency has internal_consistency=True but no 'score' key
        assert data["overall_score"] == 0.5

    def test_response_keys(self) -> None:
        """Verify all expected response keys."""
        data = self._run({"text": "hello"})
        assert set(data.keys()) == {
            "success", "score_type", "overall_score",
            "dimension_scores", "has_context",
        }


# ═══════════════════════════════════════════════════════════════════════════
# Registration Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestRegistration:
    """Verify all 10 MCP tools are registrable and callable."""

    def test_all_kpe_tools_registered(self) -> None:
        """All 10 tools + embed tools can be invoked without KeyError."""
        # Patch all service dependencies to avoid real imports
        # Note: HallucinationDetector and SensitivityClassifier are lazily imported
        # inside their tool functions, so we patch their source modules.
        with (
            patch("app.mcp.tools.kpe._extraction_service") as ext,
            patch("app.mcp.tools.kpe._classification_service") as cls,
            patch("app.mcp.tools.kpe._summarizer.summarize") as summ,
            patch("app.mcp.tools.kpe._quality_service.check_all") as qa,
            patch("app.mcp.tools.kpe._topic_classifier.classify") as tc,
            patch("app.mcp.tools.kpe._intent_classifier.classify") as ic,
            patch("common_lib.modules.knowledge_engine.kpe.quality.hallucination.HallucinationDetector") as hd,
            patch("common_lib.modules.knowledge_engine.kpe.quality.sensitivity.SensitivityClassifier") as sc,
            patch("app.mcp.tools.kpe.DenseEmbedder") as de,
        ):
            # Configure mocks
            ext.entity_extractor = MagicMock()
            ext.entity_extractor.extract.return_value = []
            ext.event_extractor = MagicMock()
            ext.event_extractor.extract.return_value = []
            ext.keyword_extractor = MagicMock()
            ext.keyword_extractor.extract.return_value = []
            ext.sentiment_analyzer = MagicMock()
            ext.sentiment_analyzer.analyze.return_value = {}

            cls.topic = MagicMock()
            cls.topic.classify.return_value = {}
            cls.intent = MagicMock()
            cls.intent.classify.return_value = {}
            cls.trust = MagicMock()
            cls.trust.evaluate.return_value = {}

            summ.return_value = {"summary": "test", "compression_ratio": 1.0}
            qa.return_value = {}
            tc.return_value = {}
            ic.return_value = {}
            hd_instance = MagicMock()
            hd_instance.detect.return_value = {"detected": False, "score": 0.0, "flagged_statements": []}
            hd.return_value = hd_instance
            sc_instance = MagicMock()
            sc_instance.classify.return_value = {"is_sensitive": False, "score": 0.0, "flagged_categories": [], "details": {}}
            sc.return_value = sc_instance
            de_instance = MagicMock()
            de_instance.embed.return_value = [[0.1]]
            de_instance.model = "test"
            de.return_value = de_instance

            server = _new_server()

            # All 10 tools should respond
            for tool_name in (
                "kpe_extract", "kpe_classify", "kpe_classify_static",
                "kpe_summarize", "kpe_check_quality",
                "kpe_detect_hallucination", "kpe_check_sensitivity",
                "kpe_score_confidence", "kpe_embed", "kpe_embed_batch",
            ):
                params = {"text": "test"}
                if tool_name == "kpe_embed_batch":
                    params = {"texts": ["test"]}
                if tool_name == "kpe_detect_hallucination":
                    params = {"text": "test", "source_context": "ctx"}
                if tool_name == "kpe_score_confidence":
                    params = {"text": "test"}

                result = asyncio.run(server.call_tool(tool_name, params))
                data = extract_call_tool_data(result)
                assert data["success"] is True, f"{tool_name} did not return success"

    def test_descriptions_meaningful(self) -> None:
        """All KPE tools have meaningful descriptions."""
        server = _new_server()
        tools = server._tool_manager.list_tools()
        kpe_tools = [t for t in tools if t.name.startswith("kpe_")]

        for t in kpe_tools:
            assert t.description, f"Tool {t.name} has empty description"
            assert len(t.description) > 20, f"Tool {t.name} description too short"

    def test_all_ten_tools_present(self) -> None:
        """Exactly 10 kpe_* tools are registered."""
        server = _new_server()
        tools = server._tool_manager.list_tools()
        kpe_names = {t.name for t in tools if t.name.startswith("kpe_")}

        expected = {
            "kpe_extract", "kpe_classify", "kpe_classify_static",
            "kpe_summarize", "kpe_check_quality",
            "kpe_detect_hallucination", "kpe_check_sensitivity",
            "kpe_score_confidence", "kpe_embed", "kpe_embed_batch",
        }
        missing = expected - kpe_names
        extra = kpe_names - expected
        assert not missing, f"Missing tools: {missing}"
        assert not extra, f"Unexpected tools: {extra}"
        assert len(kpe_names) == 10
