"""MCP tools for Performance Profiler & Query Optimizer (UDS Module 11)."""

import logging
from typing import Any, Dict, List, Optional

from common_lib.modules.db_studio.performance import (
    PerformanceProfilerService,
    ProfileRequest, ExplainRequest, ExplainCompareRequest,
    OptimizeRequest, RecommendationUpdate,
    IndexAdvisorRequest,
    SnapshotCreate, CapacityRequest,
)

logger = logging.getLogger(__name__)
service = PerformanceProfilerService()


def register_performance_tools(mcp_server):
    """Register all performance profiling and optimization MCP tools."""

    # ── Profiling Tools ───────────────────────────────────────────────

    @mcp_server.tool(description="Profile a SQL query execution with timing, CPU, memory, and wait events")
    async def profile_query(
        query: str,
        connection_id: str = "default",
        database_name: Optional[str] = None,
        collect_wait_events: bool = True,
        timeout_seconds: int = 30,
    ) -> str:
        """Profile a SQL query execution."""
        req = ProfileRequest(
            connection_id=connection_id,
            database_name=database_name,
            query=query,
            collect_wait_events=collect_wait_events,
            timeout_seconds=timeout_seconds,
        )
        result = service.profile_query(req)
        import json
        return json.dumps(result.model_dump(), indent=2, default=str)

    @mcp_server.tool(description="Get a query profile by ID")
    async def get_profile(profile_id: str) -> Optional[str]:
        """Get a specific query profile."""
        result = service.get_profile(profile_id)
        if not result:
            return None
        import json
        return json.dumps(result.model_dump(), indent=2, default=str)

    @mcp_server.tool(description="List query profiles with optional connection_id filter")
    async def list_profiles(connection_id: Optional[str] = None, limit: int = 50) -> str:
        """List query profiles."""
        result = service.list_profiles(connection_id, limit)
        import json
        return json.dumps(result.model_dump(), indent=2, default=str)

    # ── Explain Plan Tools ────────────────────────────────────────────

    @mcp_server.tool(description="Generate an execution plan for a SQL query (EXPLAIN)")
    async def explain_query(
        query: str,
        connection_id: str = "default",
        analyze: bool = False,
    ) -> str:
        """Generate an execution plan."""
        req = ExplainRequest(connection_id=connection_id, query=query, analyze=analyze)
        result = service.explain_query(req)
        import json
        return json.dumps(result.model_dump(), indent=2, default=str)

    @mcp_server.tool(description="Compare two execution plans by their IDs to find regressions and improvements")
    async def compare_plans(plan_a_id: str, plan_b_id: str) -> str:
        """Compare two execution plans."""
        result = service.compare_plans(plan_a_id, plan_b_id)
        import json
        return json.dumps(result.model_dump(), indent=2, default=str)

    # ── Optimization Tools ────────────────────────────────────────────

    @mcp_server.tool(description="Analyze a SQL query and generate optimization recommendations")
    async def optimize_query(
        query: str,
        connection_id: str = "default",
    ) -> str:
        """Generate optimization recommendations."""
        req = OptimizeRequest(connection_id=connection_id, query=query)
        results = service.optimize_query(req)
        import json
        return json.dumps([r.model_dump() for r in results], indent=2, default=str)

    @mcp_server.tool(description="List optimization recommendations with optional filters")
    async def list_recommendations(
        connection_id: Optional[str] = None,
        rec_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> str:
        """List optimization recommendations."""
        results = service.list_recommendations(connection_id, rec_type, status, limit)
        import json
        return json.dumps([r.model_dump() for r in results], indent=2, default=str)

    @mcp_server.tool(description="Update an optimization recommendation status (applied, dismissed, in_progress)")
    async def update_recommendation(
        rec_id: str,
        status: str,
        dismissed_reason: Optional[str] = None,
    ) -> Optional[str]:
        """Update recommendation status."""
        req = RecommendationUpdate(status=status, dismissed_reason=dismissed_reason)
        result = service.update_recommendation(rec_id, req)
        if not result:
            return None
        import json
        return json.dumps(result.model_dump(), indent=2, default=str)

    # ── Index Advisor Tools ───────────────────────────────────────────

    @mcp_server.tool(description="Analyze indexes and recommend missing, unused, or duplicate indexes")
    async def analyze_indexes(
        connection_id: str = "default",
        table_name: Optional[str] = None,
        analyze_workload: bool = True,
    ) -> str:
        """Analyze indexes for optimization."""
        req = IndexAdvisorRequest(
            connection_id=connection_id,
            table_name=table_name,
            analyze_workload=analyze_workload,
        )
        results = service.analyze_indexes(req)
        import json
        return json.dumps([r.model_dump() for r in results], indent=2, default=str)

    @mcp_server.tool(description="List index advisor reports with optional filters")
    async def list_index_reports(
        connection_id: Optional[str] = None,
        table_name: Optional[str] = None,
        rec_type: Optional[str] = None,
        limit: int = 50,
    ) -> str:
        """List index advisor reports."""
        results = service.list_index_reports(connection_id, table_name, rec_type, limit)
        import json
        return json.dumps([r.model_dump() for r in results], indent=2, default=str)

    # ── Snapshot Tools ────────────────────────────────────────────────

    @mcp_server.tool(description="Create a performance snapshot (system, query, workload, or baseline)")
    async def create_performance_snapshot(
        engine: str = "postgresql",
        snapshot_type: str = "system",
        label: Optional[str] = None,
        tags: Optional[List[str]] = None,
        is_baseline: bool = False,
        connection_id: Optional[str] = None,
    ) -> str:
        """Create a performance snapshot."""
        req = SnapshotCreate(
            engine=engine,
            snapshot_type=snapshot_type,
            label=label,
            tags=tags,
            is_baseline=is_baseline,
            connection_id=connection_id,
        )
        result = service.create_snapshot(req)
        import json
        return json.dumps(result.model_dump(), indent=2, default=str)

    @mcp_server.tool(description="List performance snapshots with optional filters")
    async def list_performance_snapshots(
        connection_id: Optional[str] = None,
        snapshot_type: Optional[str] = None,
        limit: int = 50,
    ) -> str:
        """List performance snapshots."""
        results = service.list_snapshots(connection_id, snapshot_type, limit)
        import json
        return json.dumps([r.model_dump() for r in results], indent=2, default=str)

    @mcp_server.tool(description="Compare two performance snapshots to find regressions and improvements")
    async def compare_snapshots(baseline_id: str, current_id: str) -> str:
        """Compare two snapshots."""
        result = service.compare_snapshots(baseline_id, current_id)
        import json
        return json.dumps(result.model_dump(), indent=2, default=str)

    # ── Capacity Tools ────────────────────────────────────────────────

    @mcp_server.tool(description="Get capacity planning metrics with growth forecasts and alerts")
    async def get_capacity_planning(
        connection_id: Optional[str] = None,
        engine: str = "postgresql",
        metric_type: Optional[str] = None,
    ) -> str:
        """Get capacity planning metrics."""
        req = CapacityRequest(connection_id=connection_id, engine=engine, metric_type=metric_type)
        result = service.get_capacity_metrics(req)
        import json
        return json.dumps(result.model_dump(), indent=2, default=str)

    @mcp_server.tool(description="List capacity metrics with optional filters")
    async def list_capacity_metrics(
        connection_id: Optional[str] = None,
        metric_type: Optional[str] = None,
        limit: int = 50,
    ) -> str:
        """List capacity metrics."""
        results = service.list_capacity_metrics(connection_id, metric_type, limit)
        import json
        return json.dumps([r.model_dump() for r in results], indent=2, default=str)

    # ── Dashboard & History Tools ─────────────────────────────────────

    @mcp_server.tool(description="Get the performance dashboard summary with metrics and alerts")
    async def get_performance_dashboard(connection_id: Optional[str] = None) -> str:
        """Get performance dashboard."""
        result = service.get_dashboard(connection_id)
        import json
        return json.dumps(result.model_dump(), indent=2, default=str)

    @mcp_server.tool(description="Get historical performance data with trends")
    async def get_performance_history(
        connection_id: Optional[str] = None,
        days: int = 7,
    ) -> str:
        """Get performance history."""
        result = service.get_history(connection_id, days)
        import json
        return json.dumps(result.model_dump(), indent=2, default=str)
