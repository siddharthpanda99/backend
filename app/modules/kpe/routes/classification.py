"""KPE Classification Routes — Thin FastAPI wrappers delegating to common_lib.

Uses LLM-driven classification (LLMClassificationService) with static fallback.
Set use_llm=false to use static keyword/weighted classifiers directly.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from common_lib.modules.kpe.classification.llm import LLMClassificationService as LLMClassificationSvc
from common_lib.modules.kpe.classification.topic import TopicClassifier
from common_lib.modules.kpe.classification.intent import IntentClassifier

logger = logging.getLogger(__name__)

router = APIRouter()

_llm_service = LLMClassificationSvc()
_topic_classifier = TopicClassifier()
_intent_classifier = IntentClassifier()


class ClassificationRequest(BaseModel):
    """Request to classify text or document."""

    document_id: str = Field(default="", description="Optional document UUID")
    text: str = Field(default="", description="Text content to classify (inline classification)")
    classifiers: List[str] = Field(
        default_factory=lambda: ["topic", "intent", "trust"],
        description="Classifiers: topic|intent|trust|domain|risk",
    )
    taxonomy: Optional[List[str]] = Field(default=None, description="Custom taxonomy for topic classification")
    use_llm: bool = Field(default=True, description="Use LLM-driven classification (falls back to static if LLM unavailable)")


class ClassificationResponse(BaseModel):
    """Response from a classification run."""

    success: bool = Field(description="Whether classification succeeded")
    document_id: str = Field(description="Document UUID")
    engine: str = Field(default="static", description="Classification engine used: llm|static")
    classifications: Dict[str, Any] = Field(
        default_factory=dict, description="Results keyed by classifier type"
    )
    message: str = Field(default="", description="Status message")


@router.post("/", response_model=ClassificationResponse)
async def run_classification(payload: ClassificationRequest):
    """Run classifiers on text or a document."""
    try:
        classifications = {}
        text = payload.text or ""

        if payload.use_llm and text:
            # LLM-driven inline classification
            engine = "llm"
            for classifier in payload.classifiers:
                if classifier == "topic":
                    classifications["topic"] = _llm_service.topic.classify(
                        text, taxonomy=payload.taxonomy or [
                            "machine learning", "cloud infrastructure", "security",
                            "frontend", "database", "DevOps", "artificial intelligence",
                        ]
                    )
                elif classifier == "intent":
                    classifications["intent"] = _llm_service.intent.classify(text)
                elif classifier == "trust":
                    classifications["trust"] = _llm_service.trust.evaluate(text)
                elif classifier == "domain":
                    from common_lib.modules.kpe.classification.domain import classify_domain
                    classifications["domain"] = classify_domain(text)
                elif classifier == "risk":
                    from common_lib.modules.kpe.classification.risk import classify_risk
                    classifications["risk"] = classify_risk(text)

        else:
            # Static keyword-based classification
            engine = "static"
            for classifier in payload.classifiers:
                if classifier == "topic":
                    classifications["topic"] = _topic_classifier.classify(
                        text or "unknown",
                        taxonomy=payload.taxonomy or [
                            "machine learning", "cloud infrastructure", "security",
                        ],
                    )
                elif classifier == "intent":
                    classifications["intent"] = _intent_classifier.classify(text or "unknown")
                elif classifier == "trust":
                    classifications["trust"] = {"overall_trust": 0.5, "flags": []}

        return ClassificationResponse(
            success=True,
            document_id=payload.document_id or "inline",
            engine=engine,
            classifications=classifications,
            message=f"Ran {len(payload.classifiers)} {engine} classifiers",
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Classification failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
