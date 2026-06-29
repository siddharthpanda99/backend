"""RIP ColBERT routes — Late interaction retrieval via connector layer.

Uses create_colbert_fn() from rip_connectors to load a real RAGatouille
ColBERTv2 model, enabling actual MaxSim late-interaction search.
"""

from fastapi import APIRouter, HTTPException
from typing import Optional

from common_lib.modules.rip.rip_retrieval.schemas import ColBERTSearchRequest
from common_lib.modules.rip.rip_connectors import create_colbert_fn

router = APIRouter(prefix="/rip/colbert", tags=["RIP — ColBERT"])


@router.post("/search")
async def colbert_search(payload: ColBERTSearchRequest):
    """ColBERT late interaction search via RAGatouille connector.

    Uses create_colbert_fn() from the RIP connector layer to load a real
    ColBERTv2 model and perform MaxSim scoring against indexed documents.
    """
    try:
        from common_lib.modules.rip.rip_retrieval.colbert import (
            colbert_search as _colbert_search,
        )
        import time

        # Create real colbert_fn from connector layer
        colbert_fn = await create_colbert_fn(
            model_name=payload.model,
            device="cpu",
        )

        start = time.perf_counter()
        result = await _colbert_search(
            query=payload.query,
            colbert_fn=colbert_fn,
            top_k=payload.top_k,
            model=payload.model,
            use_plaid=payload.use_plaid,
            tenant_id=payload.tenant_id,
        )
        elapsed = (time.perf_counter() - start) * 1000

        return {
            "query": payload.query,
            "results": result.get("results", []),
            "model": payload.model,
            "method": "colbert",
            "latency_ms": elapsed,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
