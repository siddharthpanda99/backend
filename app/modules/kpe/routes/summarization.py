"""KPE Summarization Route — Thin FastAPI wrapper for text summarization.

Uses LLM-driven summarization (LLMSummarizer) with configurable style, focus, and format.
Set use_llm=false to use static TextRank extractive summarization.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from common_lib.modules.knowledge_engine.kpe.summarization.llm import LLMSummarizer
from common_lib.modules.knowledge_engine.kpe.summarization.extractive import ExtractiveSummarizer

logger = logging.getLogger(__name__)

router = APIRouter()

_llm_summarizer = LLMSummarizer()
_extractive = ExtractiveSummarizer()


class SummarizeRequest(BaseModel):
    """Request to summarize text."""

    text: str = Field(description="Text to summarize")
    max_length: int = Field(default=200, ge=10, le=5000, description="Max summary length in words")
    style: str = Field(default="neutral", description="neutral|technical|simple|persuasive|academic")
    focus: str = Field(default="comprehensive", description="comprehensive|key_points|entities|timeline")
    format: str = Field(default="paragraph", description="paragraph|bullets|structured|tl_dr")
    use_llm: bool = Field(default=True, description="Use LLM summarization (falls back to extractive if unavailable)")


class SummarizeResponse(BaseModel):
    """Response from summarization."""

    summary: str = Field(description="Generated summary")
    compression_ratio: float = Field(default=1.0, description="Compression ratio")
    method: str = Field(default="extractive", description="Method used")
    original_length: int = Field(default=0, description="Original text length")
    summary_length: int = Field(default=0, description="Summary length in words")
    key_points: List[str] = Field(default_factory=list, description="Key takeaways")
    tone: str = Field(default="neutral", description="Summary tone")
    engine: str = Field(default="static", description="Engine used: llm|extractive")


@router.post("/", response_model=SummarizeResponse)
async def summarize(payload: SummarizeRequest):
    """Summarize text using LLM-driven or extractive methods."""
    try:
        if payload.use_llm:
            result = _llm_summarizer.summarize(
                text=payload.text,
                max_length=payload.max_length,
                style=payload.style,
                focus=payload.focus,
                format_type=payload.format,
            )
            return SummarizeResponse(
                summary=result.get("summary", ""),
                compression_ratio=result.get("compression_ratio", 1.0),
                method=result.get("method", "llm"),
                original_length=result.get("original_length", len(payload.text.split())),
                summary_length=result.get("summary_length", 0),
                key_points=result.get("key_points", []),
                tone=result.get("tone", payload.style),
                engine="llm" if result.get("method") != "extractive_fallback" else "llm_fallback",
            )

        # Static extractive fallback
        summary = _extractive.summarize(
            text=payload.text, num_sentences=max(3, payload.max_length // 20)
        )
        original_words = len(payload.text.split())
        summary_words = len(summary.split())
        return SummarizeResponse(
            summary=summary,
            compression_ratio=round(original_words / max(summary_words, 1), 2),
            method="extractive",
            original_length=original_words,
            summary_length=summary_words,
            key_points=[],
            tone="neutral",
            engine="extractive",
        )
    except Exception as e:
        logger.error("Summarization failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
