"""RIP Experiment routes — Smart Indexing comparison.

POST /api/v1/rip/experiment/smart-index — Run the smart indexing experiment
GET  /api/v1/rip/experiment/strategies — List available chunking strategies
"""

from fastapi import APIRouter, HTTPException
from typing import Optional

from common_lib.modules.rip.rip_experiment.schemas import (
    SmartIndexRequest,
    SmartIndexResponse,
)
from common_lib.modules.rip.rip_experiment.smart_indexing import SmartIndexingExperiment

router = APIRouter(prefix="/rip/experiment", tags=["RIP — Experiment"])

_experiment = SmartIndexingExperiment()


@router.post("/smart-index", response_model=SmartIndexResponse)
async def run_smart_index_experiment(payload: SmartIndexRequest):
    """Run the smart indexing experiment.

    Compares chunking strategies (hierarchical, recursive, semantic) across
    multiple chunk sizes with entity extraction, graph construction, hybrid
    retrieval, and RAGAS evaluation metrics.
    """
    try:
        if not payload.content or not payload.content.strip():
            raise HTTPException(
                status_code=400, detail="content is required and cannot be empty"
            )
        result = await _experiment.run(payload)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Experiment failed: {str(e)}")


@router.get("/strategies")
async def list_strategies():
    """List available chunking strategies with descriptions."""
    return {
        "strategies": [
            {
                "id": "hierarchical",
                "name": "Hierarchical",
                "description": "Multi-level splitting on markdown headings (#, ##, ###), then recursive sub-chunking. Produces parent-child chunk relationships.",
            },
            {
                "id": "recursive",
                "name": "Recursive Character",
                "description": "Natural boundary splitting: paragraphs → sentences → words. Preserves semantic flow within chunks.",
            },
            {
                "id": "semantic",
                "name": "Semantic",
                "description": "Sentence-level splitting with embedding-similarity boundary detection. Groups semantically similar sentences together.",
            },
            {
                "id": "fixed",
                "name": "Fixed-size",
                "description": "Fixed token-size chunks with overlap. Simple but may break mid-sentence.",
            },
            {
                "id": "llm",
                "name": "LLM-based",
                "description": "LLM-guided semantic boundary identification (LumberChunker-style). Highest quality, requires LLM.",
            },
            {
                "id": "late",
                "name": "Late Chunking",
                "description": "Embed full document first, then chunk the embedding space. Falls back to fixed-size.",
            },
        ]
    }
