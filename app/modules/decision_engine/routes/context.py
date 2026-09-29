"""Context Resolver routes — build DecisionContext from GoalSpec via ports.

POST /api/v1/decision-engine/context/build           — build DecisionContext from GoalSpec
POST /api/v1/decision-engine/context/memories        — fetch relevant memories
POST /api/v1/decision-engine/context/policies        — fetch applicable policies
POST /api/v1/decision-engine/context/tools           — fetch available tools
POST /api/v1/decision-engine/context/agents          — fetch candidate agents
POST /api/v1/decision-engine/context/evidence        — build evidence summary
POST /api/v1/decision-engine/context/risk            — compute risk dimensions
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.modules.decision_engine.routes._errors import http_error

from app.modules.decision_engine.routes._flags import (
    require_fabric as _require_fabric,
)

router = APIRouter()


# Request/Response models for this route group
class BuildDecisionStateRequest(BaseModel):
    """Request to build DecisionContext from GoalSpec."""

    goal_spec: dict[str, Any] = Field(
        ..., description="GoalSpec from IntentIngestionService.ingest_intent"
    )
    tenant_id: str = Field(default="default", description="Tenant identifier")


class FetchMemoriesRequest(BaseModel):
    """Request to fetch relevant memories."""

    goal_spec: dict[str, Any] = Field(
        ..., description="GoalSpec with intent, entities, constraints"
    )
    tenant_id: str = Field(default="default", description="Tenant identifier")


class FetchPoliciesRequest(BaseModel):
    """Request to fetch applicable policies."""

    goal_spec: dict[str, Any] = Field(
        ..., description="GoalSpec with intent, entities, constraints"
    )
    tenant_id: str = Field(default="default", description="Tenant identifier")


class FetchToolsRequest(BaseModel):
    """Request to fetch available tools."""

    goal_spec: dict[str, Any] = Field(
        ..., description="GoalSpec with intent, routing_hints"
    )
    tenant_id: str = Field(default="default", description="Tenant identifier")


class FetchAgentsRequest(BaseModel):
    """Request to fetch candidate agents."""

    goal_spec: dict[str, Any] = Field(
        ..., description="GoalSpec with intent, routing_hints"
    )
    tenant_id: str = Field(default="default", description="Tenant identifier")


class BuildEvidenceRequest(BaseModel):
    """Request to build evidence summary."""

    memories: list[dict[str, Any]] = Field(..., description="Relevant memory records")
    policies: list[dict[str, Any]] = Field(..., description="Applicable policy rules")
    goal_spec: dict[str, Any] = Field(..., description="Original GoalSpec for context")


class ComputeRiskRequest(BaseModel):
    """Request to compute risk dimensions."""

    goal_spec: dict[str, Any] = Field(
        ..., description="GoalSpec with intent, constraints"
    )
    policies: list[dict[str, Any]] = Field(..., description="Applicable policy rules")
    memories: list[dict[str, Any]] = Field(..., description="Relevant memory records")


@router.post("/build")
async def build_decision_state(payload: BuildDecisionStateRequest) -> dict[str, Any]:
    """POST /context/build — build DecisionContext from GoalSpec and tenant context."""
    _require_fabric()

    from common_lib.modules.decision_engine.services import ContextResolverService

    service = ContextResolverService()
    try:
        result = service.build_decision_state(payload.goal_spec, payload.tenant_id)
        return result
    except ValueError as exc:
        # 422 is what this route has always returned for a bad request; the
        # shared mapper's default is 400, so it is pinned here explicitly.
        raise http_error(exc, value_error_status=422)
    except NotImplementedError as exc:
        raise http_error(exc, prefix="Decision state building not yet implemented")


@router.post("/memories")
async def fetch_relevant_memories(
    payload: FetchMemoriesRequest,
) -> list[dict[str, Any]]:
    """POST /context/memories — fetch memories relevant to the goal."""
    _require_fabric()

    from common_lib.modules.decision_engine.services import ContextResolverService

    service = ContextResolverService()
    try:
        result = service.fetch_relevant_memories(payload.goal_spec, payload.tenant_id)
        return result
    except NotImplementedError as exc:
        raise http_error(exc, prefix="Memory fetching not yet implemented")


@router.post("/policies")
async def fetch_applicable_policies(
    payload: FetchPoliciesRequest,
) -> list[dict[str, Any]]:
    """POST /context/policies — fetch policies applicable to the goal."""
    _require_fabric()

    from common_lib.modules.decision_engine.services import ContextResolverService

    service = ContextResolverService()
    try:
        result = service.fetch_applicable_policies(payload.goal_spec, payload.tenant_id)
        return result
    except NotImplementedError as exc:
        raise http_error(exc, prefix="Policy fetching not yet implemented")


@router.post("/tools")
async def fetch_available_tools(payload: FetchToolsRequest) -> list[dict[str, Any]]:
    """POST /context/tools — fetch tools available for this goal/tenant."""
    _require_fabric()

    from common_lib.modules.decision_engine.services import ContextResolverService

    service = ContextResolverService()
    try:
        result = service.fetch_available_tools(payload.goal_spec, payload.tenant_id)
        return result
    except NotImplementedError as exc:
        raise http_error(exc, prefix="Tool fetching not yet implemented")


@router.post("/agents")
async def fetch_candidate_agents(payload: FetchAgentsRequest) -> list[dict[str, Any]]:
    """POST /context/agents — fetch agents available for delegation."""
    _require_fabric()

    from common_lib.modules.decision_engine.services import ContextResolverService

    service = ContextResolverService()
    try:
        result = service.fetch_candidate_agents(payload.goal_spec, payload.tenant_id)
        return result
    except NotImplementedError as exc:
        raise http_error(exc, prefix="Agent fetching not yet implemented")


@router.post("/evidence")
async def build_evidence_summary(payload: BuildEvidenceRequest) -> list[dict[str, Any]]:
    """POST /context/evidence — build evidence summary from memories and policies."""
    _require_fabric()

    from common_lib.modules.decision_engine.services import ContextResolverService

    service = ContextResolverService()
    try:
        result = service.build_evidence_summary(
            payload.memories, payload.policies, payload.goal_spec
        )
        return result
    except NotImplementedError as exc:
        raise http_error(exc, prefix="Evidence summary building not yet implemented")


@router.post("/risk")
async def compute_risk_dimensions(payload: ComputeRiskRequest) -> dict[str, Any]:
    """POST /context/risk — compute risk dimensions for the decision context."""
    _require_fabric()

    from common_lib.modules.decision_engine.services import ContextResolverService

    service = ContextResolverService()
    try:
        result = service.compute_risk_dimensions(
            payload.goal_spec, payload.policies, payload.memories
        )
        return result
    except NotImplementedError as exc:
        raise http_error(exc, prefix="Risk computation not yet implemented")
