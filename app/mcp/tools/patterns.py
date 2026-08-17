"""Pattern Factory — MCP Tool Registration.

Registers the 6 collaboration patterns (Pipeline, Fan-out/Fan-in, Expert Pool,
Producer-Reviewer, Supervisor, Hierarchical) as MCP tools for agent consumption.

Inspired by Harness' Team-Architecture Factory.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.mcp.fastmcp_compat import FastMCP

from common_lib.modules.orchestration.patterns import (
    list_patterns,
    get_pattern,
    suggest_pattern,
    PATTERN_REGISTRY,
)

logger = logging.getLogger(__name__)


def register_pattern_tools(mcp: FastMCP) -> None:
    """Register all Pattern Factory tools with the MCP server."""

    @mcp.tool()
    async def pattern_list() -> List[Dict[str, Any]]:
        """List all 6 collaboration patterns available for team creation.

        Returns Pipeline, Fan-out/Fan-in, Expert Pool, Producer-Reviewer,
        Supervisor, and Hierarchical patterns with metadata about roles,
        mode, and constraints.

        Use this first to see what patterns are available, then call
        pattern_suggest or pattern_create_team with the chosen pattern key.
        """
        return list_patterns()

    @mcp.tool()
    async def pattern_get(name: str) -> Dict[str, Any]:
        """Get detailed information about a specific collaboration pattern.

        Args:
            name: Pattern key — one of: pipeline, fan_out_fan_in, expert_pool,
                  producer_reviewer, supervisor, hierarchical

        Returns:
            Full pattern definition including all roles, mode, iterations, etc.
        """
        pattern = get_pattern(name)
        if not pattern:
            return {
                "error": f"Pattern '{name}' not found",
                "available": list(PATTERN_REGISTRY.keys()),
            }

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
            "requires_consolidation": pattern.requires_consolidation,
            "supports_real_time_discovery": pattern.supports_real_time_discovery,
        }

    @mcp.tool()
    async def pattern_suggest(
        task_description: str,
        num_workers_available: int = 3,
        requires_review: bool = False,
        has_independent_subtasks: bool = False,
    ) -> Dict[str, Any]:
        """Suggest the best collaboration pattern for a given task description.

        Analyzes the task and constraints (workers available, review needs,
        parallel subtasks) to recommend the optimal team architecture pattern.

        Args:
            task_description: What the team needs to accomplish (e.g., "Build a
                              full-stack web app with frontend and backend")
            num_workers_available: How many agents can work in parallel (1-50)
            requires_review: Whether the output needs human-level quality review
            has_independent_subtasks: Whether the task has parallelizable subtasks

        Returns:
            The recommended pattern with reasoning explanation.
        """
        pattern = suggest_pattern(
            task_description=task_description,
            num_workers_available=num_workers_available,
            requires_review=requires_review,
            has_independent_subtasks=has_independent_subtasks,
        )

        # Find registry key
        pattern_key = "pipeline"
        for key, p in PATTERN_REGISTRY.items():
            if p.name == pattern.name:
                pattern_key = key
                break

        return {
            "suggested_pattern": pattern.name,
            "pattern_key": pattern_key,
            "description": pattern.description,
            "mode": pattern.mode.value,
            "reasoning": f"Heuristic match based on {num_workers_available} workers, "
                         f"review={'yes' if requires_review else 'no'}, "
                         f"parallel={'yes' if has_independent_subtasks else 'no'}",
            "roles": [
                {"name": r.name, "type": r.role_type.value}
                for r in pattern.roles
            ],
        }

    @mcp.tool()
    async def pattern_create_team(
        pattern_key: str,
        team_name: str = "",
        worker_count: int = 3,
    ) -> Dict[str, Any]:
        """Create an agent team from a collaboration pattern.

        Instantiates a team of agents following the specified pattern's
        role definitions.

        Args:
            pattern_key: Pattern to use — pipeline, fan_out_fan_in, expert_pool,
                        producer_reviewer, supervisor, hierarchical
            team_name: Optional name for the team (defaults to pattern name)
            worker_count: Number of workers to create per role (1-20)

        Returns:
            Team details with all created agent definitions.
        """
        import uuid

        pattern = get_pattern(pattern_key)
        if not pattern:
            return {
                "error": f"Pattern '{pattern_key}' not found",
                "available": list(PATTERN_REGISTRY.keys()),
            }

        team_id = f"team-{uuid.uuid4().hex[:12]}"
        team_name = team_name or f"{pattern.name} Team"

        agents_created = []
        for role in pattern.roles:
            count = min(role.max_workers, worker_count)
            for i in range(count):
                agent_id = f"{role.name}-{i + 1}"
                agents_created.append({
                    "agent_id": f"{team_id}/{agent_id}",
                    "name": agent_id,
                    "role": role.role_type.value,
                    "pattern": pattern.name,
                    "team": team_name,
                })

        return {
            "team_id": team_id,
            "team_name": team_name,
            "pattern": pattern.name,
            "pattern_key": pattern_key,
            "agents_created": agents_created,
            "agent_count": len(agents_created),
            "status": "deployed",
        }

    logger.info("Pattern Factory: MCP tools registered (list, get, suggest, create-team)")
