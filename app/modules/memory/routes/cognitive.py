"""Cognitive memory routes — MEM-026 (SSOT §40, Wave MEM-7).

Thin transport for the Nexus Cognitive Memory Engine (Cluster 2 waves
MEM-0..6). No business logic — lazy delegation into
``common_lib.modules.memory.*``:

* ``POST /memory/cognitive/remember``  — Mem0-style remember w/ dedup (MEM-012)
* ``POST /memory/cognitive/recall``    — Hindsight-style budgeted recall (MEM-013)
* ``GET  /memory/cognitive/blocks``    — Letta core blocks (MEM-016)
* ``POST /memory/cognitive/blocks/append`` — agent block append (guard-gated)
* ``POST /memory/cognitive/tools``     — execute memory tool (MEM-017)
* ``POST /memory/cognitive/reflect``   — reflection synthesis (MEM-021)
* ``POST /memory/cognitive/consolidate`` — episodic consolidation (MEM-020)
* ``POST /memory/cognitive/promote``   — governed promotion (MEM-023)
* ``POST /memory/cognitive/share``     — pool sharing (MEM-024)
* ``GET  /memory/cognitive/freshness`` — freshness vector (MEM-025)

All endpoints are gated by ``NEXUS_MEMORY_ENGINE_ENABLED`` (503 when off —
default). Never raises to the client; structured errors only.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from common_lib.modules.memory.flags import NEXUS_MEMORY_ENGINE_ENABLED

router = APIRouter(prefix="/memory/cognitive", tags=["Memory — Cognitive Engine"])


def _require_engine() -> None:
    """Fail-fast gate: engine flag off ⇒ 503 (flag is default-OFF)."""
    from common_lib.modules.memory.flags import is_memory_flag_enabled

    if not is_memory_flag_enabled(NEXUS_MEMORY_ENGINE_ENABLED):
        raise HTTPException(
            status_code=503,
            detail="Cognitive memory engine is disabled (NEXUS_MEMORY_ENGINE_ENABLED)",
        )


def _result(outcome: dict[str, Any]) -> dict[str, Any]:
    """Normalize a never-raises service dict into a response (error ⇒ 502)."""
    if isinstance(outcome, dict) and "error" in outcome:
        raise HTTPException(status_code=502, detail=outcome["error"])
    return outcome


class RememberRequest(BaseModel):
    content: str = Field(..., min_length=1)
    scope: str = "PRIVATE"
    metadata: dict[str, Any] = Field(default_factory=dict)
    agent_id: str | None = None


class RecallRequest(BaseModel):
    query: str = Field(..., min_length=1)
    scope: str = "ALL"
    token_budget: int = Field(default=4000, ge=1)
    memory_types: list[str] | None = None


class BlockAppendRequest(BaseModel):
    agent_id: str = "default"
    name: str = "persona"
    text: str


class ToolRequest(BaseModel):
    agent_id: str
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)


class ReflectRequest(BaseModel):
    topic: str = Field(..., min_length=1)
    agent_id: str | None = None
    max_points: int = Field(default=5, ge=1, le=20)
    use_llm: bool = False
    store: bool = True


class ConsolidateRequest(BaseModel):
    agent_id: str | None = None
    window_episodes: int = Field(default=200, ge=1)
    min_cluster_size: int = Field(default=2, ge=2)
    dry_run: bool = False


class PromoteRequest(BaseModel):
    memory_id: str
    kb_id: str
    subject_id: str | None = None
    object_id: str | None = None


class ShareRequest(BaseModel):
    memory_id: str
    pool_scope: str
    caller_agent_id: str


@router.post("/remember")
def remember_endpoint(req: RememberRequest) -> dict[str, Any]:
    _require_engine()
    from common_lib.modules.memory.api.remember import remember

    return _result(
        remember(
            req.content,
            scope=req.scope,
            metadata=req.metadata,
            agent_id=req.agent_id,
        )
    )


@router.post("/recall")
def recall_endpoint(req: RecallRequest) -> dict[str, Any]:
    _require_engine()
    from common_lib.modules.memory.api.recall import recall

    return _result(
        recall(
            req.query,
            scope=req.scope,
            token_budget=req.token_budget,
            memory_types=req.memory_types,
        )
    )


@router.get("/blocks")
def blocks_endpoint(agent_id: str = "default", name: str | None = None) -> dict[str, Any]:
    _require_engine()
    from common_lib.modules.memory.letta.blocks import read_core_blocks

    return _result(read_core_blocks(agent_id, name))


@router.post("/blocks/append")
def blocks_append_endpoint(req: BlockAppendRequest) -> dict[str, Any]:
    _require_engine()
    from common_lib.modules.memory.letta.blocks import append_core_block

    return _result(append_core_block(req.agent_id, req.name, req.text, actor="system"))


@router.post("/tools")
def tools_endpoint(req: ToolRequest) -> dict[str, Any]:
    _require_engine()
    from common_lib.modules.memory.letta.tools import execute_memory_tool

    return _result(execute_memory_tool(req.agent_id, req.tool, req.args))


@router.post("/reflect")
def reflect_endpoint(req: ReflectRequest) -> dict[str, Any]:
    _require_engine()
    from common_lib.modules.memory.cognitive.reflection import reflect

    return _result(
        reflect(
            req.topic,
            agent_id=req.agent_id,
            max_points=req.max_points,
            use_llm=req.use_llm,
            store=req.store,
        )
    )


@router.post("/consolidate")
def consolidate_endpoint(req: ConsolidateRequest) -> dict[str, Any]:
    _require_engine()
    from common_lib.modules.memory.cognitive.consolidation import consolidate_episodes

    return _result(
        consolidate_episodes(
            agent_id=req.agent_id,
            window_episodes=req.window_episodes,
            min_cluster_size=req.min_cluster_size,
            dry_run=req.dry_run,
        )
    )


@router.post("/promote")
def promote_endpoint(req: PromoteRequest) -> dict[str, Any]:
    _require_engine()
    from common_lib.modules.memory.promotion.gateway import promote_memory_to_world_model

    return _result(
        promote_memory_to_world_model(
            req.memory_id, req.kb_id, subject_id=req.subject_id, object_id=req.object_id
        )
    )


@router.post("/share")
def share_endpoint(req: ShareRequest) -> dict[str, Any]:
    _require_engine()
    from common_lib.modules.memory.federation.sharing import share_memory_to_pool

    return _result(
        share_memory_to_pool(req.memory_id, req.pool_scope, req.caller_agent_id)
    )


@router.get("/freshness")
def freshness_endpoint(memory_id: str) -> dict[str, Any]:
    _require_engine()
    from common_lib.modules.memory.lifecycle.freshness import evaluate_memory_freshness

    return _result(evaluate_memory_freshness(memory_id))
