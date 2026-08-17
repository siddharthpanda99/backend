"""KPE Extraction Routes — Thin FastAPI wrappers delegating to common_lib.

Uses LLM-driven extraction (LLMExtractionService) with static fallback.
Set use_llm=false to use static spaCy/regex/lexicon extractors directly.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from common_lib.modules.knowledge_engine.kpe.services.extraction_service import ExtractionService
from common_lib.modules.knowledge_engine.kpe.extraction.llm import LLMExtractionService as LLMExtractionSvc

logger = logging.getLogger(__name__)

router = APIRouter()

_static_service = ExtractionService()
_llm_service = LLMExtractionSvc()


class ExtractionRequest(BaseModel):
    """Request to run extractors on a document."""

    document_id: str = Field(description="Document to extract from")
    text: str = Field(default="", description="Text content to extract from (instead of document_id)")
    extractors: List[str] = Field(
        default_factory=lambda: ["entities", "relationships", "facts"],
        description="Extractors to run: entities|relationships|facts|events|keywords|sentiment",
    )
    use_llm: bool = Field(default=True, description="Use LLM-driven extraction (falls back to static if LLM unavailable)")


class ExtractionResponse(BaseModel):
    """Response from an extraction run."""

    success: bool = Field(description="Whether extraction succeeded")
    document_id: str = Field(description="Document UUID")
    engine: str = Field(default="static", description="Extraction engine used: llm|static")
    results: Dict[str, Any] = Field(
        default_factory=dict, description="Extractor outputs keyed by extractor type"
    )
    message: str = Field(default="", description="Status message")


@router.post("/", response_model=ExtractionResponse)
async def run_extraction(payload: ExtractionRequest):
    """Run extractors on a document."""
    try:
        # If text is provided directly, use LLM-driven inline extraction
        if payload.text and payload.use_llm:
            text = payload.text
            results = {}
            engine = "llm"
            for extractor in payload.extractors:
                if extractor == "entities":
                    results["entities"] = _llm_service.entity_extractor.extract(text)
                elif extractor == "events":
                    results["events"] = _llm_service.event_extractor.extract(text)
                elif extractor == "keywords":
                    results["keywords"] = _llm_service.keyword_extractor.extract(text)
                elif extractor == "sentiment":
                    results["sentiment"] = _llm_service.sentiment_analyzer.analyze(text)

            return ExtractionResponse(
                success=True,
                document_id=payload.document_id or "inline",
                engine=engine,
                results=results,
                message=f"Ran {len(payload.extractors)} LLM-driven extractors on inline text",
            )

        # Otherwise use the existing document-based service
        results = await _static_service.run_extractors(
            document_id=payload.document_id,
            extractors=payload.extractors,
        )
        return ExtractionResponse(
            success=True,
            document_id=payload.document_id,
            engine="static",
            results=results,
            message=f"Ran {len(payload.extractors)} extractors",
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Extraction failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
