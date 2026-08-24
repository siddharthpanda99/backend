"""MCP Tools — Sequential Agent Chains.

Provides chain creation, execution, listing, and workflow export
for sequential agent chains via the MCP server.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_runner = None


def _get_runner():
    global _runner
    if _runner is None:
        from common_lib.modules.orchestration.chains.chain import ChainRunner
        _runner = ChainRunner()
    return _runner


def register_chains_tools(mcp):
    """Register Chains MCP tools."""

    @mcp.tool()
    def create_chain(
        name: str,
        steps: List[Dict[str, Any]],
        description: str = "",
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Create and register a sequential agent chain.

        Chains wrap the workflow engine as YAML abstractions. Each step has a
        type (start, end, llm, tool, condition, transform) and optional config.

        Args:
            name: Chain name
            steps: List of step dicts with {name, type, config} keys.
                   Types: start, end, llm, tool, condition, transform
            description: What this chain does
            tags: Tags for organization

        Returns:
            Dict with 'chain_id', 'name', 'steps', 'created'
        """
        from common_lib.modules.orchestration.chains.builder import chain_from_steps
        chain = chain_from_steps(name, steps, description=description, tags=tags or [])
        runner = _get_runner()
        runner.register_chain(chain)
        return {
            "chain_id": chain.chain_id,
            "name": chain.name,
            "steps": [
                {"id": s.step_id, "name": s.name, "type": s.step_type}
                for s in chain.steps
            ],
            "created": True,
        }

    @mcp.tool()
    def run_chain(
        chain_id: str,
        inputs: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute a registered chain by ID.

        Runs each step sequentially, passing output from one step as input to the next.

        Args:
            chain_id: Chain ID to execute
            inputs: Optional input data for the first step

        Returns:
            Dict with 'run_id', 'status', 'output', 'duration_ms', 'steps_completed'
        """
        runner = _get_runner()
        run = runner.run_chain(chain_id, inputs=inputs)
        return {
            "run_id": run.run_id,
            "chain_id": run.chain_id,
            "status": run.status,
            "output": run.output,
            "error": run.error,
            "duration_ms": run.duration_ms,
            "steps_completed": run.steps_completed,
            "started_at": run.started_at,
            "completed_at": run.completed_at,
        }

    @mcp.tool()
    def list_chains() -> Dict[str, Any]:
        """List all registered chains with their step counts and tags.

        Returns:
            Dict with 'chains' list and 'total' count
        """
        runner = _get_runner()
        chains = runner.list_chains()
        return {
            "chains": [
                {
                    "chain_id": c.chain_id,
                    "name": c.name,
                    "description": c.description,
                    "step_count": len(c.steps),
                    "tags": c.tags,
                }
                for c in chains
            ],
            "total": len(chains),
        }

    @mcp.tool()
    def get_chain_run(run_id: str) -> Dict[str, Any]:
        """Get the results of a specific chain run.

        Args:
            run_id: Chain run ID

        Returns:
            Dict with full run details including per-step results
        """
        runner = _get_runner()
        run = runner.get_run(run_id)
        if not run:
            return {"error": f"Run not found: {run_id}"}
        return {
            "run_id": run.run_id,
            "chain_id": run.chain_id,
            "status": run.status,
            "output": run.output,
            "error": run.error,
            "duration_ms": run.duration_ms,
            "steps_completed": run.steps_completed,
            "started_at": run.started_at,
            "completed_at": run.completed_at,
        }

    @mcp.tool()
    def list_chain_runs(limit: int = 50) -> Dict[str, Any]:
        """List recent chain runs with status and timing.

        Args:
            limit: Maximum number of runs to return

        Returns:
            Dict with 'runs' list and 'total' count
        """
        runner = _get_runner()
        runs = runner.list_runs(limit=limit)
        return {
            "runs": [
                {
                    "run_id": r.run_id,
                    "chain_id": r.chain_id,
                    "status": r.status,
                    "duration_ms": r.duration_ms,
                    "steps_completed": r.steps_completed,
                    "started_at": r.started_at,
                }
                for r in runs
            ],
            "total": len(runs),
        }

    @mcp.tool()
    def chain_stats() -> Dict[str, Any]:
        """Get chain execution statistics.

        Returns total chains, total runs, success rate, and average duration.

        Returns:
            Dict with 'total_chains', 'total_runs', 'successful_runs',
            'failed_runs', 'avg_duration_ms'
        """
        runner = _get_runner()
        return runner.get_stats()

    @mcp.tool()
    def export_chain_as_workflow(chain_id: str) -> Dict[str, Any]:
        """Export a chain as a workflow YAML definition.

        Converts the chain to the platform's workflow format for use
        in the workflow engine or canvas editor.

        Args:
            chain_id: Chain ID to export

        Returns:
            Dict with 'workflow' (YAML-compatible dict) and 'format'
        """
        runner = _get_runner()
        chain = runner.get_chain(chain_id)
        if not chain:
            return {"error": f"Chain not found: {chain_id}"}
        workflow = runner.export_as_workflow(chain)
        return {"workflow": workflow, "format": "platform_workflow_yaml"}

    logger.info("Chains MCP tools registered (8 tools)")
