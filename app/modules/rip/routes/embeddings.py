"""RIP Embeddings routes — Generate and manage vector embeddings.

Provides the embedding layer for the RIP retrieval pipeline.
"""

from fastapi import APIRouter, HTTPException

from common_lib.modules.rip.rip_embeddings.schemas import (
    EmbeddingRequest,
    EmbeddingResponse,
    EmbeddingBatchResponse,
)

router = APIRouter(prefix="/rip/embeddings", tags=["RIP — Embeddings"])


@router.post("", response_model=EmbeddingBatchResponse)
async def generate_embeddings(payload: EmbeddingRequest):
    """Generate embeddings for specified chunks using the configured model."""
    try:
        from common_lib.modules.rip.rip_embeddings.service import (
            generate_embeddings as _generate,
        )
        import time

        start = time.perf_counter()

        # Fetch chunk contents for embedding
        from common_lib.modules.rip.rip_documents.service import get_chunks_by_ids

        chunks = await get_chunks_by_ids(payload.chunk_ids)
        texts = [c.content for c in chunks]

        embeddings = await _generate(
            texts=texts,
            model_id=payload.model_name,
        )
        elapsed = (time.perf_counter() - start) * 1000

        response_embeddings = [
            EmbeddingResponse(
                chunk_id=payload.chunk_ids[i],
                model_name=payload.model_name,
                dimension=payload.dimension,
                embedding=embeddings[i] if i < len(embeddings) else [],
            )
            for i in range(len(payload.chunk_ids))
        ]

        return EmbeddingBatchResponse(
            embeddings=response_embeddings,
            total_time_ms=elapsed,
            model_name=payload.model_name,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
