"""SOTA Memory Systems — REST endpoints.

Exposes all 10 SOTA memory agents (Mem0, MemGPT, Reflexion, Generative Agent,
LongMem, Zep, RAPTOR, GraphRAG, LightRAG, HippoRAG) via FastAPI at
``/api/v1/sota/``.

All agents are lazily initialised through ``SOTAService``.
Route design follows the ``app/modules/audio/routes/router.py`` pattern:
exception handling delegates to 500 with detail string.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from common_lib.modules.memory.memory_stores.sota.service import (
    SOTAService,
    get_sota_service,
)

router = APIRouter()


# ── Helpers ──────────────────────────────────────────────────────────────────

def _get_svc() -> SOTAService:
    return get_sota_service()


def _handle(exc: Exception) -> None:
    raise HTTPException(status_code=500, detail=str(exc))


# ── Request / Response models ────────────────────────────────────────────────

# Shared
class MessageItem(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class HealthResponse(BaseModel):
    status: str
    agents: Dict[str, bool]


# Mem0
class Mem0AddRequest(BaseModel):
    messages: List[MessageItem]
    user_id: str = "default"


class Mem0AddResponse(BaseModel):
    added: int
    updated: int
    deleted: int


class Mem0SearchRequest(BaseModel):
    query: str
    user_id: str = "default"
    top_k: int = 10


class Mem0DeleteRequest(BaseModel):
    memory_id: str
    user_id: str = "default"


class Mem0StateResponse(BaseModel):
    user_count: int
    total_memories: int


# MemGPT
class MemGPTStepRequest(BaseModel):
    message: str


class MemGPTStepResponse(BaseModel):
    reply: str


class MemGPTStateResponse(BaseModel):
    core_memory: Dict[str, str]
    archival_count: int
    conversation_turns: int


# Reflexion
class ReflexionRunRequest(BaseModel):
    task: str
    expected_outcome: str = ""
    context: str = ""
    max_trials: int = 3


class ReflexionRunResponse(BaseModel):
    success: bool
    attempt: str
    trials: int
    outcome: str
    reflections: List[str]


# Generative Agent
class GenAgentObserveRequest(BaseModel):
    observation: str


class GenAgentActRequest(BaseModel):
    observation: str


class GenAgentActResponse(BaseModel):
    action: str


class GenAgentRetrieveRequest(BaseModel):
    situation: str
    top_k: int = 10


class GenAgentStateResponse(BaseModel):
    name: str
    persona: str
    memory_stream_count: int
    reflections: int


# LongMem
class LongMemChatRequest(BaseModel):
    message: str
    system_prompt: str = ""


class LongMemChatResponse(BaseModel):
    reply: str


class LongMemStateResponse(BaseModel):
    active_turns: int
    compressed_chunks: int
    total_turns: int


# Zep
class ZepAddEpisodeRequest(BaseModel):
    messages: List[MessageItem]
    user_id: str = "default"


class ZepAddEpisodeResponse(BaseModel):
    episode_id: str


class ZepSearchRequest(BaseModel):
    query: str
    user_id: str = "default"
    limit: int = 10


class ZepFactsRequest(BaseModel):
    user_id: str = "default"
    entity: Optional[str] = None


class ZepStateResponse(BaseModel):
    entities: int
    edges: int
    episodes: int
    currently_valid_edges: int


# ── RAPTOR ────────────────────────────────────────────────────────────────────

class RAPTORBuildRequest(BaseModel):
    documents: List[str]
    chunk_size: int = 100
    chunk_overlap: int = 20
    max_levels: int = 5
    max_cluster_size: int = 10
    max_summary_tokens: int = 200


class RAPTORBuildResponse(BaseModel):
    total_nodes: int
    levels: int
    nodes_per_level: Dict[str, int]


class RAPTORRetrieveRequest(BaseModel):
    query: str
    top_k: int = 8


class RAPTORRetrieveByLevelRequest(BaseModel):
    query: str
    level: int = 0
    top_k: int = 4


class RAPTORStateResponse(BaseModel):
    total_nodes: int
    levels: int
    nodes_per_level: Dict[str, int]


# ── Health ───────────────────────────────────────────────────────────────────

@router.get("/health", response_model=HealthResponse)
async def sota_health():
    """Check which SOTA agents are available."""
    from common_lib.modules.memory.memory_stores.sota import (
        Mem0, MemGPTAgent, ReflexionAgent,
        GenerativeAgent, LongMemAgent, ZepMemoryClient,
        RaptorAgent, GraphRAGAgent, LightRAGAgent, HippoRAGAgent,
    )
    agents = {
        "mem0": True,
        "memgpt": True,
        "reflexion": True,
        "gen_agent": True,
        "longmem": True,
        "zep": True,
        "raptor": True,
        "graphrag": True,
        "lightrag": True,
        "hipporag": True,
    }
    return HealthResponse(status="ok", agents=agents)


# ── Mem0 ─────────────────────────────────────────────────────────────────────

@router.post("/mem0/add", response_model=Mem0AddResponse)
async def mem0_add(request: Mem0AddRequest):
    """Extract and store memories from a conversation turn."""
    try:
        svc = _get_svc()
        result = await svc.mem0_add(
            user_id=request.user_id,
            messages=[m.model_dump() for m in request.messages],
        )
        return Mem0AddResponse(**result)
    except Exception as e:
        _handle(e)


@router.post("/mem0/search")
async def mem0_search(request: Mem0SearchRequest):
    """Search stored memories by semantic similarity."""
    try:
        svc = _get_svc()
        results = await svc.mem0_search(
            query=request.query,
            user_id=request.user_id,
            top_k=request.top_k,
        )
        return {"results": results}
    except Exception as e:
        _handle(e)


@router.get("/mem0/{user_id}/memories")
async def mem0_get_all(user_id: str):
    """Get all memories for a user."""
    try:
        svc = _get_svc()
        return {"memories": await svc.mem0_get_all(user_id)}
    except Exception as e:
        _handle(e)


@router.delete("/mem0/{user_id}/memories/{memory_id}")
async def mem0_delete(user_id: str, memory_id: str):
    """Delete a specific memory."""
    try:
        svc = _get_svc()
        deleted = await svc.mem0_delete(memory_id, user_id)
        return {"deleted": deleted}
    except Exception as e:
        _handle(e)


@router.get("/mem0/state", response_model=Mem0StateResponse)
async def mem0_state():
    """Return Mem0 state summary."""
    try:
        svc = _get_svc()
        state = await svc.mem0_state()
        return Mem0StateResponse(**state)
    except Exception as e:
        _handle(e)


# ── MemGPT ───────────────────────────────────────────────────────────────────

@router.post("/memgpt/step", response_model=MemGPTStepResponse)
async def memgpt_step(request: MemGPTStepRequest):
    """Process a user message through the MemGPT hierarchical memory loop."""
    try:
        svc = _get_svc()
        reply = await svc.memgpt_step(request.message)
        return MemGPTStepResponse(reply=reply)
    except Exception as e:
        _handle(e)


@router.get("/memgpt/state", response_model=MemGPTStateResponse)
async def memgpt_state():
    """Return MemGPT state summary."""
    try:
        svc = _get_svc()
        state = await svc.memgpt_state()
        return MemGPTStateResponse(**state)
    except Exception as e:
        _handle(e)


@router.post("/memgpt/reset")
async def memgpt_reset():
    """Reset MemGPT conversation (keeps core + archival memory)."""
    try:
        svc = _get_svc()
        await svc.memgpt_reset()
        return {"status": "ok"}
    except Exception as e:
        _handle(e)


@router.post("/memgpt/reset-all")
async def memgpt_reset_all():
    """Reset ALL MemGPT memory (core, archival, conversation)."""
    try:
        svc = _get_svc()
        await svc.memgpt_reset_all()
        return {"status": "ok"}
    except Exception as e:
        _handle(e)


# ── Reflexion ─────────────────────────────────────────────────────────────────

@router.post("/reflexion/run", response_model=ReflexionRunResponse)
async def reflexion_run(request: ReflexionRunRequest):
    """Run a Reflexion verbal-RL loop (simulated environment by default)."""
    try:
        svc = _get_svc()
        result = await svc.reflexion_run(
            task=request.task,
            expected_outcome=request.expected_outcome,
            context=request.context,
            max_trials=request.max_trials,
        )
        return ReflexionRunResponse(**result)
    except Exception as e:
        _handle(e)


@router.post("/reflexion/clear")
async def reflexion_clear():
    """Clear Reflexion episodic memory."""
    try:
        svc = _get_svc()
        await svc.reflexion_clear()
        return {"status": "ok"}
    except Exception as e:
        _handle(e)


@router.get("/reflexion/state")
async def reflexion_state():
    """Return Reflexion state summary."""
    try:
        svc = _get_svc()
        return await svc.reflexion_state()
    except Exception as e:
        _handle(e)


# ── Generative Agent ─────────────────────────────────────────────────────────

@router.post("/gen-agent/observe")
async def gen_agent_observe(request: GenAgentObserveRequest):
    """Add an observation to the agent's memory stream."""
    try:
        svc = _get_svc()
        await svc.gen_agent_observe(request.observation)
        return {"status": "ok"}
    except Exception as e:
        _handle(e)


@router.post("/gen-agent/act", response_model=GenAgentActResponse)
async def gen_agent_act(request: GenAgentActRequest):
    """Full observe → retrieve → act → store cycle."""
    try:
        svc = _get_svc()
        action = await svc.gen_agent_act(request.observation)
        return GenAgentActResponse(action=action)
    except Exception as e:
        _handle(e)


@router.post("/gen-agent/retrieve")
async def gen_agent_retrieve(request: GenAgentRetrieveRequest):
    """Retrieve relevant memories for a situation."""
    try:
        svc = _get_svc()
        results = await svc.gen_agent_retrieve(request.situation, top_k=request.top_k)
        return {"results": results}
    except Exception as e:
        _handle(e)


@router.get("/gen-agent/state", response_model=GenAgentStateResponse)
async def gen_agent_state():
    """Return Generative Agent state summary."""
    try:
        svc = _get_svc()
        state = await svc.gen_agent_state()
        return GenAgentStateResponse(**state)
    except Exception as e:
        _handle(e)


@router.post("/gen-agent/clear")
async def gen_agent_clear():
    """Clear the agent's memory stream."""
    try:
        svc = _get_svc()
        await svc.gen_agent_clear()
        return {"status": "ok"}
    except Exception as e:
        _handle(e)


# ── LongMem ──────────────────────────────────────────────────────────────────

@router.post("/longmem/chat", response_model=LongMemChatResponse)
async def longmem_chat(request: LongMemChatRequest):
    """Process a message through LongMem's rolling compression."""
    try:
        svc = _get_svc()
        reply = await svc.longmem_chat(request.message, system_prompt=request.system_prompt)
        return LongMemChatResponse(reply=reply)
    except Exception as e:
        _handle(e)


@router.get("/longmem/state", response_model=LongMemStateResponse)
async def longmem_state():
    """Return LongMem state summary."""
    try:
        svc = _get_svc()
        state = await svc.longmem_state()
        return LongMemStateResponse(**state)
    except Exception as e:
        _handle(e)


@router.post("/longmem/clear")
async def longmem_clear():
    """Clear LongMem conversation memory."""
    try:
        svc = _get_svc()
        await svc.longmem_clear()
        return {"status": "ok"}
    except Exception as e:
        _handle(e)


# ── Zep ──────────────────────────────────────────────────────────────────────

@router.post("/zep/episode", response_model=ZepAddEpisodeResponse)
async def zep_add_episode(request: ZepAddEpisodeRequest):
    """Add a conversation episode to the temporal knowledge graph."""
    try:
        svc = _get_svc()
        episode_id = await svc.zep_add_episode(
            messages=[m.model_dump() for m in request.messages],
            user_id=request.user_id,
        )
        return ZepAddEpisodeResponse(episode_id=episode_id)
    except Exception as e:
        _handle(e)


@router.post("/zep/search")
async def zep_search(request: ZepSearchRequest):
    """Search the temporal knowledge graph."""
    try:
        svc = _get_svc()
        results = await svc.zep_search(
            query=request.query,
            user_id=request.user_id,
            limit=request.limit,
        )
        return {"results": results}
    except Exception as e:
        _handle(e)


@router.post("/zep/facts")
async def zep_facts(request: ZepFactsRequest):
    """Get facts from the temporal knowledge graph."""
    try:
        svc = _get_svc()
        facts = await svc.zep_facts(user_id=request.user_id, entity=request.entity)
        return {"facts": facts}
    except Exception as e:
        _handle(e)


@router.get("/zep/state", response_model=ZepStateResponse)
async def zep_state():
    """Return Zep state summary."""
    try:
        svc = _get_svc()
        state = await svc.zep_state()
        return ZepStateResponse(**state)
    except Exception as e:
        _handle(e)


@router.post("/zep/clear")
async def zep_clear():
    """Clear the entire temporal knowledge graph."""
    try:
        svc = _get_svc()
        await svc.zep_clear()
        return {"status": "ok"}
    except Exception as e:
        _handle(e)


# ── RAPTOR ────────────────────────────────────────────────────────────────────

@router.post("/raptor/build", response_model=RAPTORBuildResponse)
async def raptor_build(request: RAPTORBuildRequest):
    """Build a RAPTOR tree from documents using recursive clustering and summarization.

    Accepts raw document text, optional build parameters (chunk_size, overlap,
    max_levels, cluster_size, summary tokens), and returns tree statistics.
    """
    try:
        svc = _get_svc()
        state = await svc.raptor_build(
            request.documents,
            chunk_size=request.chunk_size,
            chunk_overlap=request.chunk_overlap,
            max_levels=request.max_levels,
            max_cluster_size=request.max_cluster_size,
            max_summary_tokens=request.max_summary_tokens,
        )
        return RAPTORBuildResponse(
            total_nodes=state.get("total_nodes", 0),
            levels=state.get("levels", 0),
            nodes_per_level={str(k): v for k, v in state.get("nodes_per_level", {}).items()},
        )
    except Exception as e:
        _handle(e)


@router.post("/raptor/retrieve")
async def raptor_retrieve(request: RAPTORRetrieveRequest):
    """Retrieve top-K relevant nodes across all tree levels.

    Embeds the query and returns the most similar nodes from all levels
    (leaf chunks + summary nodes). Results include node_id, text, level,
    similarity score, and children references.
    """
    try:
        svc = _get_svc()
        results = await svc.raptor_retrieve(request.query, top_k=request.top_k)
        return {"results": results, "count": len(results)}
    except Exception as e:
        _handle(e)


@router.post("/raptor/retrieve-by-level")
async def raptor_retrieve_by_level(request: RAPTORRetrieveByLevelRequest):
    """Retrieve from a specific tree level only.

    Use level=0 for fine-grained fact retrieval (leaf chunks), and higher
    levels for thematic / abstract retrieval.
    """
    try:
        svc = _get_svc()
        results = await svc.raptor_retrieve_by_level(
            request.query,
            level=request.level,
            top_k=request.top_k,
        )
        return {"results": results, "count": len(results), "level": request.level}
    except Exception as e:
        _handle(e)


@router.get("/raptor/state", response_model=RAPTORStateResponse)
async def raptor_state():
    """Return the current RAPTOR tree state with statistics."""
    try:
        svc = _get_svc()
        state = await svc.raptor_state()
        return RAPTORStateResponse(
            total_nodes=state.get("total_nodes", 0),
            levels=state.get("levels", 0),
            nodes_per_level={str(k): v for k, v in state.get("nodes_per_level", {}).items()},
        )
    except Exception as e:
        _handle(e)


@router.post("/raptor/clear")
async def raptor_clear():
    """Clear the RAPTOR tree (start fresh)."""
    try:
        svc = _get_svc()
        await svc.raptor_clear()
        return {"status": "ok"}
    except Exception as e:
        _handle(e)


# ── GraphRAG ──────────────────────────────────────────────────────────────────

class GraphRAGIndexRequest(BaseModel):
    documents: List[str]


class GraphRAGIndexResponse(BaseModel):
    entities: int
    communities: int
    relationships: int


class GraphRAGSearchRequest(BaseModel):
    query: str


class GraphRAGSearchResponse(BaseModel):
    answer: str


class GraphRAGStateResponse(BaseModel):
    entities: int
    communities: int
    relationships: int


@router.post("/graphrag/index", response_model=GraphRAGIndexResponse)
async def graphrag_index(request: GraphRAGIndexRequest):
    """Index documents: extract entities, detect communities, generate summaries."""
    try:
        svc = _get_svc()
        state = await svc.graphrag_index(request.documents)
        return GraphRAGIndexResponse(
            entities=state.get("entities", state.get("total_entities", 0)),
            communities=state.get("communities", state.get("total_communities", 0)),
            relationships=state.get("relationships", state.get("total_relationships", 0)),
        )
    except Exception as e:
        _handle(e)


@router.post("/graphrag/local-search", response_model=GraphRAGSearchResponse)
async def graphrag_local_search(request: GraphRAGSearchRequest):
    """Local search: entity-centric retrieval with 1-hop neighbour expansion."""
    try:
        svc = _get_svc()
        answer = await svc.graphrag_local_search(request.query)
        return GraphRAGSearchResponse(answer=answer)
    except Exception as e:
        _handle(e)


@router.post("/graphrag/global-search", response_model=GraphRAGSearchResponse)
async def graphrag_global_search(request: GraphRAGSearchRequest):
    """Global search: community-centric retrieval over clustered summaries."""
    try:
        svc = _get_svc()
        answer = await svc.graphrag_global_search(request.query)
        return GraphRAGSearchResponse(answer=answer)
    except Exception as e:
        _handle(e)


@router.get("/graphrag/state", response_model=GraphRAGStateResponse)
async def graphrag_state():
    """Return GraphRAG state summary."""
    try:
        svc = _get_svc()
        state = await svc.graphrag_state()
        return GraphRAGStateResponse(
            entities=state.get("entities", state.get("total_entities", 0)),
            communities=state.get("communities", state.get("total_communities", 0)),
            relationships=state.get("relationships", state.get("total_relationships", 0)),
        )
    except Exception as e:
        _handle(e)


@router.post("/graphrag/clear")
async def graphrag_clear():
    """Clear GraphRAG indexed data."""
    try:
        svc = _get_svc()
        await svc.graphrag_clear()
        return {"status": "ok"}
    except Exception as e:
        _handle(e)


# ── LightRAG ─────────────────────────────────────────────────────────────────

class LightRAGInsertRequest(BaseModel):
    text: str
    doc_id: str = "default"


class LightRAGQueryRequest(BaseModel):
    question: str
    mode: str = "hybrid"


class LightRAGQueryResponse(BaseModel):
    answer: str


class LightRAGStateResponse(BaseModel):
    entities: int
    relations: int
    chunks: int


@router.post("/lightrag/insert")
async def lightrag_insert(request: LightRAGInsertRequest):
    """Insert a document: chunk → extract entities/relations → embed."""
    try:
        svc = _get_svc()
        await svc.lightrag_insert(request.text, doc_id=request.doc_id)
        return {"status": "ok"}
    except Exception as e:
        _handle(e)


@router.post("/lightrag/query", response_model=LightRAGQueryResponse)
async def lightrag_query(request: LightRAGQueryRequest):
    """Query LightRAG with naive/local/global/hybrid retrieval mode."""
    try:
        svc = _get_svc()
        answer = await svc.lightrag_query(request.question, mode=request.mode)
        return LightRAGQueryResponse(answer=answer)
    except Exception as e:
        _handle(e)


@router.get("/lightrag/state", response_model=LightRAGStateResponse)
async def lightrag_state():
    """Return LightRAG state summary."""
    try:
        svc = _get_svc()
        state = await svc.lightrag_state()
        return LightRAGStateResponse(
            entities=state.get("entities", 0),
            relations=state.get("relations", 0),
            chunks=state.get("chunks", 0),
        )
    except Exception as e:
        _handle(e)


@router.post("/lightrag/clear")
async def lightrag_clear():
    """Clear all LightRAG indexed data."""
    try:
        svc = _get_svc()
        await svc.lightrag_clear()
        return {"status": "ok"}
    except Exception as e:
        _handle(e)


# ── HippoRAG ─────────────────────────────────────────────────────────────────

class HippoRAGIndexRequest(BaseModel):
    passages: List[str]


class HippoRAGIndexResponse(BaseModel):
    total_passages: int
    total_entities: int
    total_edges: int


class HippoRAGRetrieveRequest(BaseModel):
    query: str


class HippoRAGStateResponse(BaseModel):
    total_passages: int
    total_entities: int
    total_edges: int


@router.post("/hipporag/index", response_model=HippoRAGIndexResponse)
async def hipporag_index(request: HippoRAGIndexRequest):
    """Index passages: NER → entity-passage graph → Personalized PageRank."""
    try:
        svc = _get_svc()
        state = await svc.hipporag_index(request.passages)
        return HippoRAGIndexResponse(**state)
    except Exception as e:
        _handle(e)


@router.post("/hipporag/retrieve")
async def hipporag_retrieve(request: HippoRAGRetrieveRequest):
    """Retrieve passages using Personalized PageRank over entity-passage graph."""
    try:
        svc = _get_svc()
        results = await svc.hipporag_retrieve(request.query)
        return {"results": results, "count": len(results)}
    except Exception as e:
        _handle(e)


@router.get("/hipporag/state", response_model=HippoRAGStateResponse)
async def hipporag_state():
    """Return HippoRAG state summary."""
    try:
        svc = _get_svc()
        state = await svc.hipporag_state()
        return HippoRAGStateResponse(**state)
    except Exception as e:
        _handle(e)


@router.post("/hipporag/clear")
async def hipporag_clear():
    """Clear all HippoRAG indexed data."""
    try:
        svc = _get_svc()
        await svc.hipporag_clear()
        return {"status": "ok"}
    except Exception as e:
        _handle(e)


__all__ = ["router"]
