"""RIP Query Intelligence routes — Intent classification, expansion, HyDE, decomposition.

Implements endpoints 11.25–11.28 from the implementation tracker.
Uses real LLM models via rip_connectors for LLM-backed operations.
"""

from fastapi import APIRouter, HTTPException

from common_lib.modules.rip.rip_query.schemas import (
    QueryIntentRequest,
    IntentClassification,
    QueryExpansionRequest,
    QueryExpansionResponse,
    HyDERequest,
    HyDEResponse,
    DecomposeRequest,
    DecomposeResponse,
)
from common_lib.modules.rip.rip_connectors import create_llm_fn

router = APIRouter(prefix="/rip/query", tags=["RIP — Query Intelligence"])


@router.post("/intent", response_model=IntentClassification)
async def classify_intent(payload: QueryIntentRequest):
    """Classify query intent — identifies query type, complexity, domain entities.

    Uses LLM model specified in payload for intent classification.
    """
    try:
        from common_lib.modules.rip.rip_query.service import classify_intent as _classify

        llm_fn = await create_llm_fn(
            model_name=payload.llm_model,
            temperature=0.3,
            max_tokens=256,
        )

        result = await _classify(
            payload.query,
            context=payload.context,
            llm_fn=llm_fn,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/expand", response_model=QueryExpansionResponse)
async def expand_query(payload: QueryExpansionRequest):
    """Expand query with LLM-generated or synonym-based alternatives.

    Methods: llm, synonym, step_back, none.
    """
    try:
        from common_lib.modules.rip.rip_query.service import expand_query as _expand

        llm_fn = None
        if payload.method in ("llm", "step_back"):
            llm_fn = await create_llm_fn(
                model_name=payload.llm_model,
                temperature=0.7,
                max_tokens=1024,
            )

        result = await _expand(
            payload.query,
            method=payload.method,
            num_expansions=payload.num_expansions,
            context=payload.context,
            llm_fn=llm_fn,
        )
        result.llm_model = payload.llm_model if llm_fn else None
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/hyde", response_model=HyDEResponse)
async def hyde_generation(payload: HyDERequest):
    """Generate hypothetical documents (HyDE) for retrieval augmentation."""
    try:
        from common_lib.modules.rip.rip_query.service import generate_hyde

        llm_fn = await create_llm_fn(
            model_name=payload.llm_model,
            temperature=0.7,
            max_tokens=512,
        )

        result = await generate_hyde(
            payload.query,
            num_hypothetical=payload.num_hypothetical,
            context=payload.context,
            llm_fn=llm_fn,
        )
        result.llm_model = payload.llm_model
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/decompose", response_model=DecomposeResponse)
async def decompose_query(payload: DecomposeRequest):
    """Decompose a complex query into sub-queries.

    Methods: cot (chain-of-thought), direct, step_back.
    """
    try:
        from common_lib.modules.rip.rip_query.service import decompose_query as _decompose

        llm_fn = await create_llm_fn(
            model_name=payload.llm_model,
            temperature=0.5,
            max_tokens=1024,
        )

        result = await _decompose(
            payload.query,
            method=payload.method,
            llm_fn=llm_fn,
        )
        result.llm_model = payload.llm_model
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
