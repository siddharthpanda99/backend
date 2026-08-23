"""MCP Tools — AutoResearch Observability Dashboard.

Provides dashboard status and metrics for external agents.
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def register_autoresearch_observability_tools(mcp):
    """Register AutoResearch Observability MCP tools."""

    @mcp.tool()
    def get_autoresearch_dashboard() -> Dict[str, Any]:
        """Get full autoresearch status for the observability dashboard.

        Returns:
            Loop status, experiment counts, crash breakdown,
            best metric, and recent events.
        """
        from common_lib.modules.observability.autoresearch_nodes import (
            node_get_autoresearch_dashboard,
        )
        return node_get_autoresearch_dashboard()

    @mcp.tool()
    def get_autoresearch_metrics() -> Dict[str, float]:
        """Get autoresearch metrics for Prometheus export.

        Returns:
            Dict with metric_name -> value pairs.
        """
        from common_lib.modules.observability.autoresearch_nodes import (
            node_get_autoresearch_metrics,
        )
        return node_get_autoresearch_metrics()

    @mcp.tool()
    def record_autoresearch_experiment(
        experiment_id: str,
        status: str,
        metric_value: float,
        metric_name: str = "",
        duration_seconds: float = 0.0,
        crash_type: Optional[str] = None,
        description: str = "",
        loop_id: str = "default",
    ) -> Dict[str, Any]:
        """Record an experiment event for observability.

        Args:
            experiment_id: Experiment identifier
            status: kept, discard, crash, timeout
            metric_value: Metric value achieved
            metric_name: Name of the metric
            duration_seconds: How long the experiment took
            crash_type: Type of crash if applicable
            description: What this experiment tried
            loop_id: Research loop identifier

        Returns:
            Recording status
        """
        from common_lib.modules.observability.autoresearch_nodes import (
            node_record_experiment_event,
        )
        return node_record_experiment_event(
            experiment_id, status, metric_value, metric_name,
            duration_seconds, crash_type, description, loop_id,
        )

    @mcp.tool()
    def record_autoresearch_loop_event(
        event_type: str,
        target_file: str = "",
        metric_name: str = "",
        loop_id: str = "default",
    ) -> Dict[str, Any]:
        """Record a research loop lifecycle event.

        Args:
            event_type: start or stop
            target_file: File being optimized
            metric_name: Metric being tracked
            loop_id: Research loop identifier

        Returns:
            Recording status
        """
        from common_lib.modules.observability.autoresearch_nodes import (
            node_record_loop_event,
        )
        return node_record_loop_event(event_type, target_file, metric_name, loop_id)

    logger.info("AutoResearch Observability MCP tools registered (4 tools)")
