"""Pattern Factory API router — expose collaboration patterns as a REST API.

Inspired by Harness' Team-Architecture Factory. Wraps the existing
collaboration_patterns.py module with FastAPI endpoints so the frontend
can list patterns, get details, suggest the best pattern for a task,
and create/deploy teams from patterns.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from common_lib.modules.orchestration.patterns import (
    PatternTemplate,
    list_patterns,
    get_pattern,
    suggest_pattern,
    PATTERN_REGISTRY,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# =========================================================================
# Schemas
# =========================================================================


class AgentRoleSchema(BaseModel):
    name: str
    type: str
    max_workers: int


class PatternDetailSchema(BaseModel):
    name: str
    key: str
    description: str
    mode: str
    role_count: int
    roles: List[AgentRoleSchema]
    max_iterations: int
    supports_parallel: bool


class SuggestRequest(BaseModel):
    task_description: str = Field(..., description="High-level task description")
    num_workers_available: int = Field(default=3, ge=1, le=50)
    requires_review: bool = Field(default=False)
    has_independent_subtasks: bool = Field(default=False)


class SuggestResponse(BaseModel):
    pattern: PatternDetailSchema
    reasoning: str


class CreateTeamRequest(BaseModel):
    pattern_key: str = Field(
        ...,
        description="Pattern key: pipeline, fan_out_fan_in, expert_pool, producer_reviewer, supervisor, hierarchical",
    )
    team_name: str = Field(default="", description="Optional team name override")
    worker_count: int = Field(default=3, ge=1, le=20)


class CreateTeamResponse(BaseModel):
    team_id: str
    pattern: PatternDetailSchema
    agents_created: List[Dict[str, Any]]
    status: str


# =========================================================================
# Endpoints
# =========================================================================


@router.get(
    "/patterns",
    response_model=List[PatternDetailSchema],
    summary="List all collaboration patterns",
    description="Returns all 6 formalized multi-agent collaboration patterns (Pipeline, Fan-out/Fan-in, Expert Pool, Producer-Reviewer, Supervisor, Hierarchical).",
)
async def list_all_patterns() -> List[Dict[str, Any]]:
    """List all available collaboration patterns with metadata."""
    return list_patterns()


@router.get(
    "/patterns/{name}",
    response_model=PatternDetailSchema,
    summary="Get a specific pattern by name",
    description="Returns detailed information about a specific collaboration pattern.",
)
async def get_pattern_by_name(name: str) -> Dict[str, Any]:
    """Get a single collaboration pattern by key name."""
    pattern = get_pattern(name)
    if not pattern:
        raise HTTPException(
            status_code=404,
            detail=f"Pattern '{name}' not found. Available: {', '.join(PATTERN_REGISTRY.keys())}",
        )

    roles = [
        {
            "name": r.name,
            "type": r.role_type.value,
            "max_workers": r.max_workers,
        }
        for r in pattern.roles
    ]

    return {
        "name": pattern.name,
        "key": name,
        "description": pattern.description,
        "mode": pattern.mode.value,
        "role_count": len(pattern.roles),
        "roles": roles,
        "max_iterations": pattern.max_iterations,
        "supports_parallel": pattern.mode.value in (
            "parallel", "managed", "routed",
        ),
    }


@router.post(
    "/patterns/suggest",
    response_model=SuggestResponse,
    summary="Suggest the best pattern for a task",
    description="Uses heuristic-based pattern matching to recommend the optimal collaboration pattern for a given task description and constraints.",
)
async def suggest_pattern_for_task(req: SuggestRequest) -> Dict[str, Any]:
    """Suggest the best collaboration pattern based on task description."""
    pattern = suggest_pattern(
        task_description=req.task_description,
        num_workers_available=req.num_workers_available,
        requires_review=req.requires_review,
        has_independent_subtasks=req.has_independent_subtasks,
    )

    # Find the registry key for the pattern
    pattern_key = "pipeline"
    for key, p in PATTERN_REGISTRY.items():
        if p.name == pattern.name:
            pattern_key = key
            break

    roles = [
        {
            "name": r.name,
            "type": r.role_type.value,
            "max_workers": r.max_workers,
        }
        for r in pattern.roles
    ]

    # Generate human-readable reasoning
    if req.has_independent_subtasks and req.num_workers_available >= 2:
        reasoning = f"Task has {req.num_workers_available} parallel subtasks → recommended Fan-out/Fan-in for parallel execution with consolidation."
    elif req.requires_review:
        reasoning = "Task requires quality review → recommended Producer-Reviewer for iterative refinement loop."
    elif req.num_workers_available >= 5:
        reasoning = f"Large worker pool ({req.num_workers_available}) available → recommended Expert Pool or Supervisor pattern for dynamic task routing."
    else:
        reasoning = f"Standard task with {req.num_workers_available} workers → recommended {pattern.name} pattern as the default fit."

    return {
        "pattern": {
            "name": pattern.name,
            "key": pattern_key,
            "description": pattern.description,
            "mode": pattern.mode.value,
            "role_count": len(pattern.roles),
            "roles": roles,
            "max_iterations": pattern.max_iterations,
            "supports_parallel": pattern.mode.value in (
                "parallel", "managed", "routed",
            ),
        },
        "reasoning": reasoning,
    }


@router.post(
    "/patterns/create-team",
    response_model=CreateTeamResponse,
    summary="Create an agent team from a pattern",
    description="Instantiates a team of agents following the specified collaboration pattern, creating agent records for each role.",
)
async def create_team_from_pattern(req: CreateTeamRequest) -> Dict[str, Any]:
    """Create and deploy an agent team following a collaboration pattern."""
    pattern = get_pattern(req.pattern_key)
    if not pattern:
        raise HTTPException(
            status_code=404,
            detail=f"Pattern '{req.pattern_key}' not found. Available: {', '.join(PATTERN_REGISTRY.keys())}",
        )

    import uuid

    team_id = f"team-{uuid.uuid4().hex[:12]}"
    team_name = req.team_name or f"{pattern.name} Team"

    agents_created = []
    for role in pattern.roles:
        count = min(role.max_workers, req.worker_count)
        for i in range(count):
            agent_id = f"{role.name}-{i + 1}"
            agents_created.append({
                "agent_id": f"{team_id}/{agent_id}",
                "name": agent_id,
                "role": role.role_type.value,
                "pattern": pattern.name,
                "team": team_name,
            })

    logger.info(
        "Team '%s' created from pattern '%s' with %d agents",
        team_name, pattern.name, len(agents_created),
    )

    return {
        "team_id": team_id,
        "pattern": {
            "name": pattern.name,
            "key": req.pattern_key,
            "description": pattern.description,
            "mode": pattern.mode.value,
            "role_count": len(pattern.roles),
            "roles": [
                {
                    "name": r.name,
                    "type": r.role_type.value,
                    "max_workers": r.max_workers,
                }
                for r in pattern.roles
            ],
            "max_iterations": pattern.max_iterations,
            "supports_parallel": pattern.mode.value in (
                "parallel", "managed", "routed",
            ),
        },
        "agents_created": agents_created,
        "status": "deployed",
    }


@router.get(
    "/patterns/{name}/render",
    summary="Get a visual representation of a pattern's flow",
    description="Returns a mermaid flowchart diagram showing the agent collaboration flow for the specified pattern.",
)
async def render_pattern_flow(name: str) -> Dict[str, str]:
    """Generate a mermaid flowchart for the pattern."""
    pattern = get_pattern(name)
    if not pattern:
        raise HTTPException(
            status_code=404,
            detail=f"Pattern '{name}' not found.",
        )

    role_names = [r.name for r in pattern.roles]
    flow_lines = ["graph TD"]

    if pattern.mode.value == "sequential":
        # Pipeline: A -> B -> C -> D
        for i in range(len(role_names) - 1):
            flow_lines.append(f"    {role_names[i]}[{role_names[i].title()}] --> {role_names[i+1]}[{role_names[i+1].title()}]")
    elif pattern.mode.value == "parallel":
        # Fan-out: Splitter -> {Experts} -> Aggregator
        flow_lines.append(f"    {role_names[0]}[{role_names[0].title()}] --> |splits| {{")
        for r in role_names[1:-1]:
            flow_lines.append(f"        {r}[{r.title()}]")
        flow_lines.append("    }}")
        flow_lines.append(f"    {{}} --> {role_names[-1]}[{role_names[-1].title()}]")
    elif pattern.mode.value == "routed":
        # Expert Pool: Router -> {Experts}
        flow_lines.append(f"    {role_names[0]}[{role_names[0].title()}] --> |routes to| {{")
        flow_lines.append(f"        {role_names[1]}[{role_names[1].title()} Pool]")
        flow_lines.append("    }}")
    elif pattern.mode.value == "loop":
        # Producer-Reviewer: Producer <-> Reviewer
        flow_lines.append(f"    {role_names[0]}[{role_names[0].title()}] -->|creates| {role_names[1]}[{role_names[1].title()}]")
        flow_lines.append(f"    {role_names[1]}[{role_names[1].title()}] -->|feedback| {role_names[0]}[{role_names[0].title()}]")
        flow_lines.append(f"    {role_names[1]}[{role_names[1].title()}] -.->|approves| END")
    elif pattern.mode.value == "managed":
        # Supervisor: Supervisor -> {Workers}
        flow_lines.append(f"    {role_names[0]}[{role_names[0].title()}] -->|assigns tasks| {{")
        flow_lines.append(f"        {role_names[1]}[{role_names[1].title()} Pool]")
        flow_lines.append("    }}")
        flow_lines.append(f"    {{}} -->|results| {role_names[0]}[{role_names[0].title()}]")
    elif pattern.mode.value == "recursive":
        # Hierarchical: Director -> Manager -> {Workers}
        flow_lines.append(f"    {role_names[0]}[{role_names[0].title()}] --> {role_names[1]}[{role_names[1].title()}]")
        flow_lines.append(f"    {role_names[1]}[{role_names[1].title()}] -->|delegates| {{")
        flow_lines.append(f"        {role_names[2]}[{role_names[2].title()} Pool]")
        flow_lines.append("    }}")

    return {
        "name": pattern.name,
        "key": name,
        "mermaid": "\n".join(flow_lines),
    }


__all__ = ["router"]
