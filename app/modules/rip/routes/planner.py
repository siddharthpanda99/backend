"""RIP Nexus planner routes — thin transport for the §15 QueryPlan (chunk C015).

Thin-router discipline: no business logic here; delegation to
``common_lib.modules.rip.rip_router.plan.build_query_plan`` (lazy import).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/rip/query", tags=["RIP — Nexus Planner"])


class QueryPlanRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Raw user query")
    granted_scopes: list[str] | None = Field(
        default=None, description="Optional granted scope values (ACL narrowing)"
    )
    query_types: list[str] | None = Field(
        default=None, description="Optional pre-computed §11 types (skip classification)"
    )


class QueryPlanResponse(BaseModel):
    plan: dict[str, Any]


@router.post("/plan", response_model=QueryPlanResponse)
async def build_plan(payload: QueryPlanRequest) -> QueryPlanResponse:
    """Build the SSOT §15 QueryPlan (classification → requirements → completeness → scope)."""
    try:
        from common_lib.modules.rip.rip_router.plan import build_query_plan

        result = build_query_plan(
            payload.query,
            granted_scopes=payload.granted_scopes,
            query_types=payload.query_types,
        )
        return QueryPlanResponse(plan=result["plan"])
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 — transport error mapping only
        raise HTTPException(status_code=500, detail=str(exc)) from exc
