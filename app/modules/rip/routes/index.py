"""RIP Index routes — ANN index management (HNSW, IVF, DiskANN, Flat).

Uses the Index connector for real ANN backends via hnswlib / faiss / numpy.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from common_lib.modules.rip.rip_index.schemas import IndexRequest, IndexStatusResponse

router = APIRouter(prefix="/rip/indices", tags=["RIP — Index Management"])


@router.post("", response_model=IndexStatusResponse)
async def create_index(payload: IndexRequest):
    """Create or rebuild an ANN index for vector search.

    Algorithms: hnsw (via hnswlib), ivf (via faiss), flat (via numpy/faiss).
    Uses the Index connector for real ANN implementations.
    """
    try:
        from common_lib.modules.rip.rip_connectors import create_index_builder_fn
        import time

        start = time.perf_counter()

        builder_fn = await create_index_builder_fn(
            algorithm=payload.algorithm,
            dimension=payload.dimension,
        )
        result = await builder_fn(
            name=payload.name,
            algorithm=payload.algorithm,
            dimension=payload.dimension,
            vector_type=payload.vector_type,
            config=payload.config,
            document_ids=payload.document_ids,
        )
        elapsed = (time.perf_counter() - start) * 1000

        return IndexStatusResponse(
            id=result.get("id", ""),
            name=payload.name,
            algorithm=payload.algorithm,
            dimension=payload.dimension,
            total_vectors=result.get("total_vectors", 0),
            status=result.get("status", "building"),
            config=result.get("config", payload.config),
            created_at=result.get("created_at"),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=dict)
async def list_indices():
    """List all ANN indices with their status and vector counts."""
    try:
        from common_lib.modules.rip.rip_index.service import list_indices

        indices = await list_indices()
        count = len(indices) if indices else 0
        return {"indices": list(indices), "total": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
