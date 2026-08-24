"""MCP Tools — Multi-Agent Supervisor.

Provides multi-agent task dispatch, worker management, and run tracking
via the MCP server. Routes tasks to specialized workers based on
capabilities and routing strategy.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_supervisor = None


def _get_supervisor():
    global _supervisor
    if _supervisor is None:
        from common_lib.modules.orchestration.multiagent.supervisor import SupervisorAgent
        from common_lib.modules.orchestration.multiagent.models import RoutingStrategy, AggregateStrategy
        _supervisor = SupervisorAgent(
            routing_strategy=RoutingStrategy.ROUND_ROBIN,
            aggregate_strategy=AggregateStrategy.FIRST,
        )
    return _supervisor


def register_multiagent_tools(mcp):
    """Register Multi-Agent Supervisor MCP tools."""

    @mcp.tool()
    def dispatch_multiagent_task(
        description: str,
        name: Optional[str] = None,
        capabilities_needed: Optional[List[str]] = None,
        routing_strategy: Optional[str] = None,
        aggregate_strategy: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute a task through the multi-agent supervisor.

        The supervisor routes to the best worker(s) based on capabilities
        and routing strategy, executes, and aggregates results.

        Routing strategies: round_robin, capability, load_balanced, priority, random, llm_decided
        Aggregate strategies: first, best, merge, vote, concatenate

        Args:
            description: Task description or prompt
            name: Optional task display name
            capabilities_needed: Required worker capabilities (e.g. ['code', 'python'])
            routing_strategy: Override routing strategy
            aggregate_strategy: Override aggregation strategy

        Returns:
            Dict with 'run_id', 'status', 'final_output', 'workers_used', 'duration_ms'
        """
        from common_lib.modules.orchestration.multiagent.models import (
            AggregateStrategy,
            RoutingStrategy,
            TaskDefinition,
        )
        from common_lib.modules.orchestration.multiagent.router import TaskRouter

        supervisor = _get_supervisor()

        if routing_strategy:
            supervisor.routing_strategy = RoutingStrategy(routing_strategy)
            supervisor._router = TaskRouter(strategy=supervisor.routing_strategy)

        if aggregate_strategy:
            supervisor.aggregate_strategy = AggregateStrategy(aggregate_strategy)

        task = TaskDefinition(
            name=name or f"Task: {description[:50]}",
            description=description,
            required_capabilities=capabilities_needed or [],
        )

        run = supervisor.execute(task)

        return {
            "run_id": run.id,
            "status": run.status.value,
            "final_output": run.final_output,
            "workers_used": len(run.results),
            "duration_ms": run.duration_ms,
            "total_tokens": run.total_tokens,
            "total_cost_usd": run.total_cost_usd,
        }

    @mcp.tool()
    def register_worker(
        name: str,
        capabilities: List[str],
        max_concurrent: int = 5,
    ) -> Dict[str, Any]:
        """Register a specialized worker agent with the supervisor.

        Workers are identified by capability tags and the supervisor routes
        tasks to the best-matching worker.

        Args:
            name: Worker display name
            capabilities: Capability tags (e.g. ['code', 'python', 'data_analysis'])
            max_concurrent: Max concurrent tasks (default: 5)

        Returns:
            Dict with 'worker_id', 'name', 'capabilities'
        """
        from common_lib.modules.orchestration.multiagent.models import WorkerDefinition, WorkerCapability
        from common_lib.modules.orchestration.multiagent.worker import WorkerAgent

        caps = [WorkerCapability(name=c, weight=1.0) for c in capabilities]
        definition = WorkerDefinition(
            name=name,
            capabilities=caps,
            max_concurrent_tasks=max_concurrent,
        )

        def default_fn(task_input: str) -> str:
            return f"Worker '{name}' processed: {task_input}"

        worker = WorkerAgent(definition=definition, fn=default_fn)
        supervisor = _get_supervisor()
        supervisor.add_worker(worker)

        return {
            "worker_id": worker.id,
            "name": name,
            "capabilities": capabilities,
        }

    @mcp.tool()
    def remove_worker(worker_id: str) -> Dict[str, Any]:
        """Remove a worker from the multi-agent supervisor.

        Args:
            worker_id: Worker ID to remove

        Returns:
            Dict with 'removed' (bool)
        """
        supervisor = _get_supervisor()
        removed = supervisor.remove_worker(worker_id)
        return {"removed": removed}

    @mcp.tool()
    def list_multiagent_workers() -> Dict[str, Any]:
        """List all registered worker agents with capabilities and stats.

        Returns:
            Dict with 'workers' list and 'total' count
        """
        supervisor = _get_supervisor()
        workers = supervisor.list_workers()
        return {"workers": workers, "total": len(workers)}

    @mcp.tool()
    def get_multiagent_run(run_id: str) -> Dict[str, Any]:
        """Get the results of a specific multi-agent run.

        Args:
            run_id: Multi-agent run ID

        Returns:
            Dict with run details, worker results, routing decisions
        """
        supervisor = _get_supervisor()
        run = supervisor.get_run(run_id)
        if not run:
            return {"error": f"Run not found: {run_id}"}
        return {
            "run_id": run.id,
            "name": run.name,
            "status": run.status.value,
            "final_output": run.final_output,
            "routing_strategy": run.routing_strategy.value,
            "aggregate_strategy": run.aggregate_strategy.value,
            "results_count": len(run.results),
            "duration_ms": run.duration_ms,
            "started_at": run.started_at,
            "completed_at": run.completed_at,
        }

    @mcp.tool()
    def list_multiagent_runs(limit: int = 50) -> Dict[str, Any]:
        """List recent multi-agent runs with status and timing.

        Args:
            limit: Maximum number of runs to return

        Returns:
            Dict with 'runs' list and 'total' count
        """
        supervisor = _get_supervisor()
        runs = supervisor.list_runs(limit=limit)
        return {
            "runs": [
                {
                    "run_id": r.id,
                    "name": r.name,
                    "status": r.status.value,
                    "routing_strategy": r.routing_strategy.value,
                    "aggregate_strategy": r.aggregate_strategy.value,
                    "results_count": len(r.results),
                    "duration_ms": r.duration_ms,
                    "started_at": r.started_at,
                }
                for r in runs
            ],
            "total": len(runs),
        }

    @mcp.tool()
    def multiagent_stats() -> Dict[str, Any]:
        """Get multi-agent supervisor statistics.

        Returns total workers, available workers, run counts, success/failure rates.

        Returns:
            Dict with 'total_workers', 'available_workers', 'total_runs',
            'completed_runs', 'failed_runs', 'workers' (per-worker stats)
        """
        supervisor = _get_supervisor()
        return supervisor.get_stats()

    logger.info("Multi-Agent Supervisor MCP tools registered (7 tools)")
