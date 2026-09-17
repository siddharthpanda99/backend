"""RIP Nexus memory-integration routes — thin transport for §49-§54 (chunk C074).

Extends the existing RIP memory surface (store/search above) with the Wave-10
policy/scope/promotion/conflict endpoints. Thin-router discipline: no business
logic here; delegation to ``common_lib.modules.rip.rip_memory.*`` (lazy imports
inside handlers). Endpoints:

* ``POST /rip/memory/policy``     — §52 policy resolution + §49/§50 role map (C070)
* ``POST /rip/memory/scope``      — §51/§85 read-gate memory filtering (C071)
* ``POST /rip/memory/promote``    — §53 promotion with full lineage (C072)
* ``POST /rip/memory/conflict``   — §54 reconciliation with lineage preserved (C073)
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/rip/memory", tags=["RIP — Memory"])


class PolicyRequest(BaseModel):
    query: str = Field(..., min_length=1)
    explicit_policy: str | None = None
    tenant_override: str | None = None


class PolicyResponse(BaseModel):
    result: dict[str, Any]


class ScopeRequest(BaseModel):
    records: list[dict[str, Any]] = Field(default_factory=list)
    query_scope: str = Field(..., min_length=1)


class ScopeResponse(BaseModel):
    result: dict[str, Any]


class PromoteRequest(BaseModel):
    evidence: dict[str, Any]
    gate_confidence: float | None = None
    content_override: str | None = None
    target: str = Field("memory", pattern="^(memory|world_model)$")


class PromoteResponse(BaseModel):
    result: dict[str, Any]


class ConflictRequest(BaseModel):
    memory: dict[str, Any]
    evidence: dict[str, Any]


class ConflictResponse(BaseModel):
    result: dict[str, Any]


@router.post("/policy", response_model=PolicyResponse)
async def resolve_policy(payload: PolicyRequest):
    """Resolve the effective §52 memory policy for a query (deterministic)."""
    try:
        from common_lib.modules.rip.rip_memory.policy import (
            apply_memory_policy,
            resolve_memory_policy,
        )

        resolved = resolve_memory_policy(
            query=payload.query,
            explicit_policy=payload.explicit_policy,
            tenant_override=payload.tenant_override,
        )
        return {"result": resolved}
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scope", response_model=ScopeResponse)
async def filter_by_scope(payload: ScopeRequest):
    """§51/§85 read gate: filter memory records by query scope (fail-closed)."""
    try:
        from common_lib.modules.rip.rip_memory.scope import filter_memory_by_scope

        result = filter_memory_by_scope(
            query_scope=payload.query_scope, records=payload.records
        )
        return {"result": result}
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/promote", response_model=PromoteResponse)
async def promote(payload: PromoteRequest):
    """§53/§88: promote document evidence → memory (or world-model candidate)."""
    try:
        if payload.target == "world_model":
            from common_lib.modules.rip.rip_memory.promotion import (
                promote_to_world_model,
            )

            result = promote_to_world_model(evidence=payload.evidence)
        else:
            from common_lib.modules.rip.rip_memory.promotion import (
                promote_to_memory,
            )

            kwargs: dict[str, Any] = {"evidence": payload.evidence}
            if payload.gate_confidence is not None:
                kwargs["gate_confidence"] = payload.gate_confidence
            if payload.content_override is not None:
                kwargs["content_override"] = payload.content_override
            result = promote_to_memory(**kwargs)
        return {"result": result}
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/conflict", response_model=ConflictResponse)
async def reconcile_conflict(payload: ConflictRequest):
    """§54: reconcile new evidence vs stored memory (lineage preserved)."""
    try:
        from common_lib.modules.rip.rip_memory.conflict import (
            reconcile_memory_conflict,
        )

        result = reconcile_memory_conflict(memory=payload.memory, evidence=payload.evidence)
        return {"result": result}
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
