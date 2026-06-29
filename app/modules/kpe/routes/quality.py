"""KPE Quality Route — Thin FastAPI wrapper for quality checks.

Uses LLM-driven quality assessment (LLMQualityService) with static fallback.
Set use_llm=false to use static Presidio/regex checkers directly.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from common_lib.modules.kpe.quality.llm import LLMQualityService
from common_lib.modules.kpe.quality.hallucination import HallucinationDetector
from common_lib.modules.kpe.quality.sensitivity import SensitivityClassifier

logger = logging.getLogger(__name__)

router = APIRouter()

_llm_service = LLMQualityService()
_hallucination_detector = HallucinationDetector()
_sensitivity_classifier = SensitivityClassifier()


class QualityCheckRequest(BaseModel):
    """Request to run quality checks on text."""

    text: str = Field(description="Text to check")
    context: str = Field(default="", description="Optional source context for factuality checks")
    purpose: str = Field(default="general", description="Purpose for quality evaluation")
    checks: List[str] = Field(
        default_factory=lambda: ["sensitivity", "factuality", "consistency", "evaluation"],
        description="Checks: sensitivity|factuality|consistency|evaluation|hallucination",
    )
    use_llm: bool = Field(default=True, description="Use LLM-driven checks (falls back to static if LLM unavailable)")


@router.post("/")
async def run_quality_checks(payload: QualityCheckRequest):
    """Run quality checks on text."""
    try:
        if payload.use_llm:
            # LLM-driven quality assessment
            results = _llm_service.check_all(
                text=payload.text,
                context=payload.context,
                purpose=payload.purpose,
                checks=payload.checks,
            )
            return {"success": True, "engine": "llm", "results": results}

        # Static fallback checks
        results = {}
        for check in payload.checks:
            if check == "hallucination":
                results["hallucination"] = _hallucination_detector.detect(
                    payload.context or payload.text, payload.text
                )
            elif check == "sensitivity":
                results["sensitivity"] = _sensitivity_classifier.classify(payload.text)
            elif check == "factuality":
                results["factuality"] = _hallucination_detector.detect(
                    payload.context or payload.text, payload.text
                )
            else:
                results[check] = {"error": f"Check '{check}' not available in static mode"}
        return {"success": True, "engine": "static", "results": results}
    except Exception as e:
        logger.error("Quality check failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
