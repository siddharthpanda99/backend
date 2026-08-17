"""KPE Embedding Routes — Thin FastAPI wrapper delegating to DenseEmbedder.

Provides a REST endpoint for generating dense vector embeddings from text,
supporting multiple providers (openai, bge, voyage, gemini). Follows the
same pattern as the kpe_embed MCP tool.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from common_lib.modules.knowledge_engine.kpe.embeddings.dense import DenseEmbedder

logger = logging.getLogger(__name__)

router = APIRouter()


class EmbeddingRequest(BaseModel):
    """Request to generate embeddings for text."""

    text: str = Field(description="Text content to embed (minimum 1 character)")
    texts: Optional[List[str]] = Field(
        default=None,
        description="Batch texts to embed (1-100). If provided, overrides 'text'.",
    )
    provider: str = Field(
        default="openai",
        description="Embedding provider: openai|bge|voyage|gemini",
    )
    model: Optional[str] = Field(
        default=None,
        description="Specific model ID within the provider. Uses provider default if omitted.",
    )


class EmbeddingResponse(BaseModel):
    """Response from an embedding request."""

    success: bool = Field(description="Whether embedding succeeded")
    vector: List[float] = Field(
        default_factory=list,
        description="Dense vector for single text (only when 'text' is used)",
    )
    vectors: List[List[float]] = Field(
        default_factory=list,
        description="Dense vectors for batch texts (only when 'texts' is used)",
    )
    count: int = Field(default=0, description="Number of vectors returned")
    dimensions: int = Field(default=0, description="Vector dimension count")
    provider: str = Field(description="Embedding provider used")
    model: str = Field(description="Model ID used")
    text_length: int = Field(default=0, description="Length of input text")


@router.post("/", response_model=EmbeddingResponse)
async def run_embedding(payload: EmbeddingRequest):
    """Generate dense vector embeddings for text.

    Supports single text and batch embedding through the KPE DenseEmbedder
    adapter, which wraps multiple providers: openai, bge, voyage, gemini.
    """
    try:
        embedder = (
            DenseEmbedder(provider=payload.provider, model=payload.model)
            if payload.model
            else DenseEmbedder(provider=payload.provider)
        )

        if payload.texts:
            # Batch mode
            vectors = embedder.embed(payload.texts)
            return EmbeddingResponse(
                success=True,
                vectors=vectors,
                count=len(vectors),
                dimensions=len(vectors[0]) if vectors else 0,
                provider=payload.provider,
                model=payload.model or embedder.model,
                text_length=sum(len(t) for t in payload.texts),
            )
        else:
            # Single mode
            vectors = embedder.embed([payload.text])
            vector = vectors[0] if vectors else []
            return EmbeddingResponse(
                success=True,
                vector=vector,
                vectors=[vector],
                count=1 if vector else 0,
                dimensions=len(vector),
                provider=payload.provider,
                model=payload.model or embedder.model,
                text_length=len(payload.text),
            )

    except Exception as e:
        logger.error("Embedding failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
