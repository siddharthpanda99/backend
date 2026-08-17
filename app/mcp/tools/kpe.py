"""
KPE — MCP Tool Registration.

Registers KPE capabilities (extraction, classification, summarization, quality)
as MCP tools for agent consumption.

Usage:
    # In app/mcp/server.py:
    from app.mcp.tools.kpe import register_kpe_tools
    register_kpe_tools(mcp_server)
"""

from __future__ import annotations

import logging
from typing import Any, List, Optional

from app.mcp.fastmcp_compat import FastMCP

from common_lib.modules.knowledge_engine.kpe.extraction.llm import LLMExtractionService
from common_lib.modules.knowledge_engine.kpe.classification.llm import LLMClassificationService
from common_lib.modules.knowledge_engine.kpe.summarization.llm import LLMSummarizer
from common_lib.modules.knowledge_engine.kpe.quality.llm import LLMQualityService
from common_lib.modules.knowledge_engine.kpe.classification.topic import TopicClassifier
from common_lib.modules.knowledge_engine.kpe.classification.intent import IntentClassifier
from common_lib.modules.knowledge_engine.kpe.embeddings.dense import DenseEmbedder

logger = logging.getLogger("mcp.tools.kpe")

# Singleton service instances
_extraction_service = LLMExtractionService()
_classification_service = LLMClassificationService()
_summarizer = LLMSummarizer()
_quality_service = LLMQualityService()
_topic_classifier = TopicClassifier()
_intent_classifier = IntentClassifier()


def register_kpe_tools(mcp: FastMCP) -> None:
    """Register all KPE tools with the MCP server.

    Registers 9 tools covering extraction, classification, summarization,
    and quality checking.
    """

    # ── Extraction ─────────────────────────────────────────────

    @mcp.tool()
    async def kpe_extract(
        text: str,
        extractors: Optional[List[str]] = None,
    ) -> dict[str, Any]:
        """Extract structured information from text using LLM.

        Runs one or more extractors on the provided text to extract:
        - entities: Named entities (people, orgs, locations, products, etc.)
        - relationships: Semantic relationships between entities
        - facts: Factual statements extracted from the text
        - events: Notable events mentioned
        - keywords: Key terms and phrases
        - sentiment: Overall sentiment analysis

        Args:
            text: Text content to extract from.
            extractors: Extractors to run (default: ['entities', 'relationships', 'facts']).
                       Available: entities, relationships, facts, events, keywords, sentiment.

        Returns:
            Dict with extraction results keyed by extractor type,
            each containing extracted items with confidence scores.
        """
        if extractors is None:
            extractors = ["entities", "relationships", "facts"]

        results = {}
        for extractor in extractors:
            try:
                if extractor == "entities":
                    results["entities"] = _extraction_service.entity_extractor.extract(text)
                elif extractor == "events":
                    results["events"] = _extraction_service.event_extractor.extract(text)
                elif extractor == "keywords":
                    results["keywords"] = _extraction_service.keyword_extractor.extract(text)
                elif extractor == "sentiment":
                    results["sentiment"] = _extraction_service.sentiment_analyzer.analyze(text)
            except Exception as e:
                logger.warning("Extractor '%s' failed: %s", extractor, e)
                results[extractor] = {"error": str(e)}

        return {
            "success": True,
            "text_length": len(text),
            "extractors_used": extractors,
            "extractors_completed": len(results),
            "results": results,
        }

    # ── Classification ─────────────────────────────────────────

    @mcp.tool()
    async def kpe_classify(
        text: str,
        classifiers: Optional[List[str]] = None,
        taxonomy: Optional[List[str]] = None,
    ) -> dict[str, Any]:
        """Classify text across multiple dimensions using LLM.

        Runs one or more classifiers on the provided text:
        - topic: Subject/topic classification with taxonomy matching
        - intent: User intent detection (informational, transactional, etc.)
        - trust: Trustworthiness evaluation and flagging
        - domain: Knowledge domain identification
        - risk: Risk level assessment

        Args:
            text: Text content to classify.
            classifiers: Classifiers to run (default: ['topic', 'intent', 'trust']).
                        Available: topic, intent, trust, domain, risk.
            taxonomy: Optional custom taxonomy list for topic classification.
                     Default taxonomy includes common knowledge domains.

        Returns:
            Dict with classification results keyed by classifier type,
            each containing labels, confidence scores, and metadata.
        """
        if classifiers is None:
            classifiers = ["topic", "intent", "trust"]

        if taxonomy is None:
            taxonomy = [
                "machine learning", "cloud infrastructure", "security",
                "frontend", "database", "DevOps", "artificial intelligence",
                "data engineering", "networking", "software architecture",
            ]

        results = {}
        for classifier in classifiers:
            try:
                if classifier == "topic":
                    results["topic"] = _classification_service.topic.classify(text, taxonomy=taxonomy)
                elif classifier == "intent":
                    results["intent"] = _classification_service.intent.classify(text)
                elif classifier == "trust":
                    results["trust"] = _classification_service.trust.evaluate(text)
                elif classifier == "domain":
                    from common_lib.modules.knowledge_engine.kpe.classification.domain import classify_domain
                    results["domain"] = classify_domain(text)
                elif classifier == "risk":
                    from common_lib.modules.knowledge_engine.kpe.classification.risk import classify_risk
                    results["risk"] = classify_risk(text)
            except Exception as e:
                logger.warning("Classifier '%s' failed: %s", classifier, e)
                results[classifier] = {"error": str(e)}

        return {
            "success": True,
            "text_length": len(text),
            "classifiers_used": classifiers,
            "classifiers_completed": len(results),
            "classifications": results,
        }

    @mcp.tool()
    async def kpe_classify_static(
        text: str,
        taxonomy: Optional[List[str]] = None,
    ) -> dict[str, Any]:
        """Classify text using fast keyword-based static classifiers.

        Lightweight alternative to LLM-based classification. Uses pre-built
        keyword dictionaries and pattern matching for topic and intent detection.
        No LLM calls, no API costs.

        Args:
            text: Text content to classify.
            taxonomy: Optional custom taxonomy list for topic classification.

        Returns:
            Dict with topic and intent classifications using keyword matching.
        """
        if taxonomy is None:
            taxonomy = [
                "machine learning", "cloud infrastructure", "security",
                "frontend", "database",
            ]

        topic = _topic_classifier.classify(text, taxonomy=taxonomy)
        intent = _intent_classifier.classify(text)

        return {
            "success": True,
            "engine": "static",
            "topic": topic,
            "intent": intent,
            "text_length": len(text),
        }

    # ── Summarization ──────────────────────────────────────────

    @mcp.tool()
    async def kpe_summarize(
        text: str,
        max_length: int = 200,
        style: str = "neutral",
        focus: str = "comprehensive",
        format_type: str = "paragraph",
    ) -> dict[str, Any]:
        """Summarize text using LLM-driven abstractive summarization.

        Produces concise, coherent summaries that capture the essential
        information from the input text. Supports multiple styles, focus
        areas, and output formats.

        Args:
            text: Text content to summarize (minimum 50 characters).
            max_length: Maximum summary length in words (10-5000, default: 200).
            style: Summary writing style:
                  - neutral: Objective, balanced summary
                  - technical: Technical, precise language
                  - simple: Easy-to-understand, plain language
                  - persuasive: Compelling, opinion-oriented
                  - academic: Formal, scholarly tone
            focus: Summary focus area:
                  - comprehensive: Full coverage of all important points
                  - key_points: Only the most critical takeaways
                  - entities: Entity-centric summary
                  - timeline: Chronological summary of events
            format_type: Output format:
                       - paragraph: Flowing paragraph text
                       - bullets: Bullet point list (best for key_points)
                       - structured: Structured sections with headers
                       - tl_dr: Ultra-concise "too long; didn't read"

        Returns:
            Dict with summary, key_points, compression_ratio, tone, and metadata.
        """
        result = _summarizer.summarize(
            text=text,
            max_length=max_length,
            style=style,
            focus=focus,
            format_type=format_type,
        )

        return {
            "success": True,
            "summary": result.get("summary", ""),
            "compression_ratio": result.get("compression_ratio", 1.0),
            "method": result.get("method", "llm"),
            "original_length": result.get("original_length", len(text.split())),
            "summary_length": result.get("summary_length", 0),
            "key_points": result.get("key_points", []),
            "tone": result.get("tone", style),
            "engine": "llm",
        }

    # ── Quality Checking ───────────────────────────────────────

    @mcp.tool()
    async def kpe_check_quality(
        text: str,
        context: str = "",
        checks: Optional[List[str]] = None,
    ) -> dict[str, Any]:
        """Run comprehensive quality checks on generated text.

        Evaluates text quality across multiple dimensions using LLM:
        - sensitivity: Detects offensive, biased, or sensitive content
        - factuality: Verifies claims against provided context
        - consistency: Checks internal consistency of the text
        - evaluation: Overall quality evaluation with scores
        - hallucination: Detects fabrications not supported by context

        Args:
            text: Text content to check for quality issues.
            context: Source context for factuality/hallucination verification.
            checks: Quality checks to run (default: all available checks).
                   Available: sensitivity, factuality, consistency,
                   evaluation, hallucination.

        Returns:
            Dict with per-check results including scores, flags,
            and detailed analysis for each quality dimension.
        """
        if checks is None:
            checks = ["sensitivity", "factuality", "consistency", "evaluation", "hallucination"]

        results = _quality_service.check_all(
            text=text,
            context=context,
            purpose="general",
            checks=checks,
        )

        return {
            "success": True,
            "text_length": len(text),
            "checks_completed": len(checks),
            "results": results,
            "recommendation": _generate_quality_recommendation(results),
        }

    @mcp.tool()
    async def kpe_detect_hallucination(
        text: str,
        source_context: str,
    ) -> dict[str, Any]:
        """Detect hallucinated content in generated text.

        Compares generated text against provided source context to identify
        statements that are not supported by or contradict the source.

        Args:
            text: Generated text to check for hallucinations.
            source_context: Source material the text should be based on.

        Returns:
            Dict with hallucination detection results including score,
            flagged statements, and verdict.
        """
        from common_lib.modules.knowledge_engine.kpe.quality.hallucination import HallucinationDetector

        detector = HallucinationDetector()
        result = detector.detect(source_context, text)

        return {
            "success": True,
            "hallucination_detected": result.get("detected", False),
            "hallucination_score": result.get("score", 0.0),
            "flagged_statements": result.get("flagged_statements", []),
            "verdict": "likely hallucinated" if result.get("detected") else "likely factual",
        }

    @mcp.tool()
    async def kpe_check_sensitivity(
        text: str,
    ) -> dict[str, Any]:
        """Check text for sensitive or inappropriate content.

        Scans text for offensive language, hate speech, harassment,
        NSFW content, and other sensitive categories.

        Args:
            text: Text content to analyze for sensitivity.

        Returns:
            Dict with sensitivity analysis including overall score,
            flagged categories, and detailed breakdown.
        """
        from common_lib.modules.knowledge_engine.kpe.quality.sensitivity import SensitivityClassifier

        classifier = SensitivityClassifier()
        result = classifier.classify(text)

        return {
            "success": True,
            "is_sensitive": result.get("is_sensitive", False),
            "sensitivity_score": result.get("score", 0.0),
            "flagged_categories": result.get("flagged_categories", []),
            "details": result.get("details", {}),
        }


    # ── Scoring ────────────────────────────────────────────────

    @mcp.tool()
    async def kpe_score_confidence(
        text: str,
        context: str = "",
        score_type: str = "quality",
    ) -> dict[str, Any]:
        """Score text quality, relevance, or confidence across multiple dimensions.

        Evaluates and scores text on various quality and confidence metrics.
        Uses the LLM quality assessment engine to produce structured scores.

        Args:
            text: Text content to score.
            context: Optional context for relevance scoring.
            score_type: Type of scoring to perform:
                       - quality: Overall quality score (grammar, clarity, coherence)
                       - relevance: Relevance to the provided context
                       - confidence: Confidence/trustworthiness assessment
                       - completeness: How complete/thorough the text is

        Returns:
            Dict with scores for each dimension, overall score,
            and detailed breakdown.
        """
        checks = ["consistency", "evaluation"]
        if score_type == "confidence":
            checks = ["factuality", "consistency", "evaluation"]

        results = _quality_service.check_all(
            text=text,
            context=context,
            purpose=score_type,
            checks=checks,
        )

        # Extract numeric scores from results
        scores = {}
        for check, result in results.items():
            if isinstance(result, dict):
                score = result.get("score") or result.get("confidence") or result.get("overall", 0.5)
                if isinstance(score, (int, float)):
                    scores[check] = round(float(score), 3)

        overall = sum(scores.values()) / max(len(scores), 1) if scores else 0.5

        return {
            "success": True,
            "score_type": score_type,
            "overall_score": round(overall, 3),
            "dimension_scores": scores,
            "has_context": bool(context),
        }

    # ── Embedding ────────────────────────────────────────────────

    @mcp.tool()
    async def kpe_embed(
        text: str,
        provider: str = "openai",
        model: Optional[str] = None,
    ) -> dict[str, Any]:
        """Generate a dense vector embedding for text using the KPE embedding module.

        Uses the KPE DenseEmbedder adapter which supports multiple providers:
        - openai: text-embedding-3-small / text-embedding-3-large / text-embedding-ada-002
        - bge: BAAI/bge-small-en-v1.5 / BAAI/bge-base-en-v1.5 / BAAI/bge-large-en-v1.5
        - voyage: voyage-2 / voyage-3 / voyage-code-2
        - gemini: text-embedding-004

        Falls back gracefully to a zero-vector if no embedding provider is configured.
        For production-grade embedding with hybrid search support, use knowledge_embed.

        Args:
            text: Text content to embed (minimum 1 character).
            provider: Embedding provider (openai, bge, voyage, gemini).
            model: Specific model ID within the provider. If omitted, uses
                   the provider's default model.

        Returns:
            Dict with the dense vector, dimensions, provider, and model used.
        """
        embedder = DenseEmbedder(provider=provider, model=model) if model else DenseEmbedder(provider=provider)
        vectors = embedder.embed([text])
        vector = vectors[0] if vectors else []

        return {
            "success": True,
            "vector": vector,
            "dimensions": len(vector),
            "provider": provider,
            "model": model or embedder.model,
            "provider_model": embedder.model,
            "text_length": len(text),
        }

    @mcp.tool()
    async def kpe_embed_batch(
        texts: list[str],
        provider: str = "openai",
        model: Optional[str] = None,
    ) -> dict[str, Any]:
        """Generate dense vector embeddings for multiple texts in batch.

        More efficient than calling kpe_embed repeatedly. Uses the same
        DenseEmbedder under the hood with provider-agnostic adapter.
        Maximum 100 texts per batch.

        Args:
            texts: List of texts to embed (1-100).
            provider: Embedding provider (openai, bge, voyage, gemini).
            model: Specific model ID within the provider. If omitted, uses
                   the provider's default model.

        Returns:
            Dict with list of vectors, count, dimensions, and metadata.
        """
        embedder = DenseEmbedder(provider=provider, model=model) if model else DenseEmbedder(provider=provider)
        vectors = embedder.embed(texts)

        return {
            "success": True,
            "vectors": vectors,
            "count": len(vectors),
            "dimensions": len(vectors[0]) if vectors else 0,
            "provider": provider,
            "model": model or embedder.model,
            "provider_model": embedder.model,
        }

    logger.info("KPE: 10 MCP tools registered (extraction, classification, summarization, quality, scoring, embedding)")


def _generate_quality_recommendation(results: dict) -> str:
    """Generate a human-readable quality recommendation."""
    issues = []

    sensitivity = results.get("sensitivity", {})
    if isinstance(sensitivity, dict) and sensitivity.get("is_sensitive"):
        issues.append("sensitive content")

    hallucination = results.get("hallucination", {})
    if isinstance(hallucination, dict) and hallucination.get("detected"):
        issues.append("potential hallucination")

    factuality = results.get("factuality", {})
    if isinstance(factuality, dict) and not factuality.get("supported", True):
        issues.append("unsupported factual claims")

    consistency = results.get("consistency", {})
    if isinstance(consistency, dict) and not consistency.get("internal_consistency", True):
        issues.append("inconsistencies")

    if not issues:
        return "No quality issues detected — text appears clean and well-formed."
    return f"Quality issues detected: {', '.join(issues)}. Review flagged sections before using."
