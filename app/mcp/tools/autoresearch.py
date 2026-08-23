"""MCP Tools — AutoResearch Module.

Provides autonomous research loop capabilities to external agents
via the MCP server.
"""

import logging
from typing import Any, Dict, Optional, List

logger = logging.getLogger(__name__)


def register_autoresearch_tools(mcp):
    """Register AutoResearch MCP tools."""

    @mcp.tool()
    def start_research_loop(
        target_file: str = "train.py",
        metric_name: str = "val_bpb",
        time_budget: int = 300,
        run_forever: bool = True,
    ) -> Dict[str, Any]:
        """Start an autonomous research loop.

        The loop runs experiments indefinitely: modify target file,
        run with time budget, evaluate metric, keep if improved, repeat.

        Args:
            target_file: Path to the file the agent can modify
            metric_name: Metric to optimize (lower is better)
            time_budget: Time budget per experiment in seconds
            run_forever: Whether to run indefinitely

        Returns:
            Status of the research loop
        """
        from common_lib.modules.knowledge_engine.autoresearch.nodes import (
            node_start_research_loop,
        )
        return node_start_research_loop(target_file, metric_name, time_budget, run_forever)

    @mcp.tool()
    def stop_research_loop() -> Dict[str, Any]:
        """Stop the currently running research loop.

        Returns:
            Status including experiment count and best metric
        """
        from common_lib.modules.knowledge_engine.autoresearch.nodes import (
            node_stop_research_loop,
        )
        return node_stop_research_loop()

    @mcp.tool()
    def get_research_status() -> Dict[str, Any]:
        """Get the current status of the research loop.

        Returns:
            Current status, experiment count, best metric, config
        """
        from common_lib.modules.knowledge_engine.autoresearch.nodes import (
            node_get_research_status,
        )
        return node_get_research_status()

    @mcp.tool()
    def configure_research(
        target_file: Optional[str] = None,
        metric_name: Optional[str] = None,
        time_budget: Optional[int] = None,
        max_retries: Optional[int] = None,
        auto_fix_crashes: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Configure the research loop parameters.

        Args:
            target_file: Path to the file the agent can modify
            metric_name: Metric to optimize (lower is better)
            time_budget: Time budget per experiment in seconds
            max_retries: Maximum retry attempts on crash
            auto_fix_crashes: Whether to auto-fix simple crashes

        Returns:
            Updated configuration
        """
        from common_lib.modules.knowledge_engine.autoresearch.nodes import (
            node_configure_research,
        )
        return node_configure_research(target_file, metric_name, time_budget, max_retries, auto_fix_crashes)

    @mcp.tool()
    def get_experiment_history(limit: int = 10) -> Dict[str, Any]:
        """Get the history of experiments.

        Args:
            limit: Maximum number of experiments to return

        Returns:
            List of experiment results with best experiment
        """
        from common_lib.modules.knowledge_engine.autoresearch.nodes import (
            node_get_experiment_history,
        )
        return node_get_experiment_history(limit)

    @mcp.tool()
    def evaluate_experiment(
        current_metric: float,
        baseline_metric: float,
        secondary_metrics: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        """Evaluate whether to keep or discard an experiment.

        Args:
            current_metric: Metric from the experiment
            baseline_metric: Best metric so far
            secondary_metrics: Optional secondary metrics

        Returns:
            Decision (keep/discard/maybe) with reasoning
        """
        from common_lib.modules.knowledge_engine.autoresearch.nodes import (
            node_evaluate_experiment,
        )
        return node_evaluate_experiment(current_metric, baseline_metric, secondary_metrics)

    @mcp.tool()
    def evaluate_complexity_cost(
        improvement_pct: float,
        lines_added: int,
        lines_removed: int = 0,
    ) -> Dict[str, Any]:
        """Evaluate if complexity cost is justified for an improvement.

        Based on AutoResearch simplicity criterion.

        Args:
            improvement_pct: Percentage improvement
            lines_added: Lines of code added
            lines_removed: Lines of code removed

        Returns:
            Whether to keep based on complexity cost
        """
        from common_lib.modules.knowledge_engine.autoresearch.nodes import (
            node_evaluate_complexity_cost,
        )
        return node_evaluate_complexity_cost(improvement_pct, lines_added, lines_removed)

    @mcp.tool()
    def analyze_crash(log_file: str) -> Dict[str, Any]:
        """Analyze a crash log to determine crash type and suggested fix.

        Args:
            log_file: Path to the crash log

        Returns:
            Crash analysis: type, error, suggested fix, line number
        """
        from common_lib.modules.knowledge_engine.autoresearch.nodes import (
            node_analyze_crash,
        )
        return node_analyze_crash(log_file)

    @mcp.tool()
    def attempt_crash_recovery(
        log_file: str,
        experiment_id: str = "default",
    ) -> Dict[str, Any]:
        """Attempt to recover from a crash.

        Analyzes the crash, attempts auto-fix if possible,
        and manages retry logic.

        Args:
            log_file: Path to the crash log
            experiment_id: Identifier for this experiment

        Returns:
            Recovery status: can_retry, attempts, fixed
        """
        from common_lib.modules.knowledge_engine.autoresearch.nodes import (
            node_attempt_recovery,
        )
        return node_attempt_recovery(log_file, experiment_id)

    @mcp.tool()
    def get_crash_summary() -> Dict[str, Any]:
        """Get summary of all crashes.

        Returns:
            Crash statistics by type, auto-fixable count
        """
        from common_lib.modules.knowledge_engine.autoresearch.nodes import (
            node_get_crash_summary,
        )
        return node_get_crash_summary()

    logger.info("AutoResearch MCP tools registered (10 tools)")
