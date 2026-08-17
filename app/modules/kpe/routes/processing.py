"""KPE Processing Route — Thin FastAPI wrapper for document processing.

Uses LLM-driven processing (LLMProcessingService) with static fallback.
Set use_llm=false in request body to use heuristic parsing directly.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from common_lib.modules.knowledge_engine.kpe.processing.llm import LLMProcessingService
from common_lib.modules.knowledge_engine.kpe.processing.service import ProcessingService

logger = logging.getLogger(__name__)

router = APIRouter()

_llm_service = LLMProcessingService()
_static_service = ProcessingService()


class ProcessingRequest(BaseModel):
    """Request to process a document."""

    file_path: str = Field(description="Path to the document file")
    content: str = Field(default="", description="Optional pre-read content")
    use_llm: bool = Field(default=True, description="Use LLM-driven processing (falls back to static if LLM unavailable)")


class ProcessingResponse(BaseModel):
    """Response from document processing."""

    success: bool = Field(description="Whether processing succeeded")
    format: str = Field(description="Detected document format")
    content_length: int = Field(default=0, description="Length of extracted content")
    title: str = Field(default="", description="Document title")
    headings_count: int = Field(default=0, description="Number of headings found")
    engine: str = Field(default="static", description="Processing engine used: llm|static|llm_fallback")
    message: str = Field(default="", description="Status message")


@router.post("/", response_model=ProcessingResponse)
async def process_document(payload: ProcessingRequest):
    """Process a document file using LLM-driven engine with static fallback."""
    try:
        if payload.use_llm:
            result = _llm_service.process(
                file_path=payload.file_path,
                content=payload.content or None,
            )
            engine = "llm"
        else:
            result = _static_service.process(
                file_path=payload.file_path,
                content=payload.content or None,
            )
            engine = "static"

        return ProcessingResponse(
            success=result.format != "error",
            format=result.format,
            content_length=len(result.content),
            title=result.title,
            headings_count=len(result.headings),
            engine=engine,
            message=f"Processed {payload.file_path} as {result.format} via {engine}",
        )
    except Exception as e:
        logger.error("Processing failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
