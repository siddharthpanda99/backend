"""RIP Agentic RAG routes — Self-RAG, CRAG, and autonomous research.

Implements endpoints 11.20–11.22 from the implementation tracker.

These routes now use the rip_connectors module to instantiate real LLM
providers (OpenAI, OpenRouter, Groq, vLLM) based on the model name
specified in the request.
"""

from fastapi import APIRouter, HTTPException

from common_lib.modules.rip.rip_rag.schemas import SelfRAGRequest, CRAGRequest
from common_lib.modules.rip.rip_synthesis.schemas import ResearchRequest, ResearchResponse
from common_lib.modules.rip.rip_connectors import create_llm_fn

router = APIRouter(prefix="/rip/agent", tags=["RIP — Agentic RAG"])


@router.post("/self-rag")
async def self_rag(payload: SelfRAGRequest):
    """Self-RAG — Self-reflective retrieval with relevance + support evaluation.

    Uses a real LLM (via rip_connectors) to decide whether to retrieve,
    evaluate relevance of retrieved chunks, and critique its own outputs.
    """
    try:
        from common_lib.modules.rip.rip_rag.service import self_rag as _self_rag
        import time

        # Create a real LLM function backed by the requested model
        llm_fn = await create_llm_fn(
            model_name=payload.llm_model,
            system_prompt="You are a retrieval quality evaluator. Be concise.",
            temperature=0.3,
            max_tokens=256,
        )

        start = time.perf_counter()
        result = await _self_rag(
            query=payload.query,
            context=payload.context,
            top_k=payload.retrieval_top_k,
            require_support=payload.require_support,
            reranker=payload.reranker,
            max_attempts=payload.max_retrieval_attempts,
            llm_fn=llm_fn,
            tenant_id=payload.tenant_id,
        )
        elapsed = (time.perf_counter() - start) * 1000

        return {
            "query": payload.query,
            "answer": result.get("answer", ""),
            "retrieved_chunks": result.get("retrieved_chunks", []),
            "is_relevant": result.get("is_relevant", True),
            "is_supported": result.get("is_supported", True),
            "hallucination_detected": result.get("hallucination_detected", False),
            "retrieval_attempts": result.get("retrieval_attempts", 1),
            "llm_model": payload.llm_model,
            "latency_ms": elapsed,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/crag")
async def crag_retrieval(payload: CRAGRequest):
    """Corrective RAG (CRAG) — Retrieval with relevance check and fallback.

    Uses a real LLM to evaluate confidence. Falls back to web search or
    alternative retrievers below the threshold.
    """
    try:
        from common_lib.modules.rip.rip_rag.service import crag as _crag
        import time

        llm_fn = await create_llm_fn(
            model_name=payload.llm_model,
            system_prompt="You are a confidence evaluator. Return only a decimal number between 0 and 1.",
            temperature=0.2,
            max_tokens=32,
        )

        start = time.perf_counter()
        result = await _crag(
            query=payload.query,
            top_k=payload.top_k,
            confidence_threshold=payload.confidence_threshold,
            web_fallback=payload.web_fallback,
            max_corrections=payload.max_corrections,
            llm_fn=llm_fn,
            tenant_id=payload.tenant_id,
        )
        elapsed = (time.perf_counter() - start) * 1000

        return {
            "query": payload.query,
            "answer": result.get("answer", ""),
            "retrieved_chunks": result.get("retrieved_chunks", []),
            "confidence": result.get("confidence", 0.0),
            "used_web_fallback": result.get("used_web_fallback", False),
            "corrections_made": result.get("corrections_made", 0),
            "llm_model": payload.llm_model,
            "latency_ms": elapsed,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/research", response_model=ResearchResponse)
async def research_agent(payload: ResearchRequest):
    """Autonomous research agent — multi-step retrieval and synthesis.

    Uses a real LLM (via rip_connectors) for decomposition, analysis,
    and final synthesis. Depth levels: quick, standard, deep.
    """
    try:
        from common_lib.modules.rip.rip_synthesis.service import research_query as _research
        import time

        llm_fn = await create_llm_fn(
            model_name=payload.llm_model or "gpt-4o-mini",
            system_prompt="You are a thorough research analyst. Provide detailed, cited findings.",
            temperature=0.5,
            max_tokens=4096,
        )

        start = time.perf_counter()
        result = await _research(
            question=payload.question,
            depth=payload.depth,
            max_steps=payload.max_steps,
            include_synthesis=payload.include_synthesis,
            include_sources=payload.include_sources,
            llm_fn=llm_fn,
            tenant_id=payload.tenant_id,
        )
        elapsed = (time.perf_counter() - start) * 1000

        return ResearchResponse(
            question=payload.question,
            synthesis=result.get("synthesis"),
            findings=result.get("findings", []),
            sources=result.get("sources", []),
            reasoning_steps=result.get("reasoning_steps", 0),
            total_time_ms=elapsed,
            confidence=result.get("confidence", 0.0),
            llm_model=payload.llm_model,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
