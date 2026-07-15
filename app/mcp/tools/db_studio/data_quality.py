"""MCP tools for Data Quality & Profiling (UDS Module 16)."""

import json
from typing import Any, Dict, List, Optional

from common_lib.modules.db_studio.data_quality import (
    DataQualityService,
    ProfileRequest, ProfileOut,
    QualityRuleCreate, QualityRuleOut,
    RuleExecuteRequest, RuleResultOut,
    ValidateRequest, ValidationOut,
    AlertCreate, AlertOut,
)

svc = DataQualityService()


def register_data_quality_tools(mcp_server):
    """Register all data quality tools with the MCP server."""

    @mcp_server.tool()
    async def profile_table(
        connection_id: str, engine: str, table_name: str,
        run_type: str = "full", sample_percent: float = None,
        columns: List[str] = None,
    ) -> str:
        """Run data profiling on a table to generate column-level statistics."""
        req = ProfileRequest(
            connection_id=connection_id, engine=engine, table_name=table_name,
            run_type=run_type, sample_percent=sample_percent, columns=columns,
        )
        result = svc.profile(req)
        return _format_profile(result)

    @mcp_server.tool()
    async def list_profiling_runs(connection_id: str = None, table_name: str = None, limit: int = 10) -> str:
        """List recent profiling runs."""
        results = svc.list_profiles(connection_id, table_name, limit)
        if not results:
            return "No profiling runs found."
        lines = [f"**Profiling Runs** ({len(results)}):"]
        for r in results:
            lines.append(f"- {r.id}: {r.table_name} ({r.status}, {r.total_columns} columns)")
        return "\n".join(lines)

    @mcp_server.tool()
    async def get_profile_statistics(run_id: str) -> str:
        """Get column-level statistics from a profiling run."""
        stats = svc.get_profile_statistics(run_id)
        if not stats:
            return "No statistics found for this run."
        lines = [f"**Profiling Statistics** ({len(stats)} columns):"]
        for s in stats:
            lines.append(
                f"- {s.column_name} ({s.data_type}): "
                f"rows={s.row_count}, null={s.null_percent:.1f}%, "
                f"distinct={s.distinct_percent:.1f}%"
            )
        return "\n".join(lines)

    @mcp_server.tool()
    async def create_quality_rule(
        name: str, rule_type: str, dimension: str = "validity",
        description: str = None, severity: str = "error",
        target_columns: List[str] = None, condition_expression: str = None,
        tags: List[str] = None,
    ) -> str:
        """Create a reusable data quality rule."""
        req = QualityRuleCreate(
            name=name, rule_type=rule_type, dimension=dimension,
            description=description, severity=severity,
            target_columns=target_columns, condition_expression=condition_expression,
            tags=tags,
        )
        result = svc.create_rule(req)
        return f"Created rule: {result.name} ({result.id}), type={result.rule_type}, dimension={result.dimension}"

    @mcp_server.tool()
    async def list_quality_rules(rule_type: str = None, dimension: str = None, limit: int = 20) -> str:
        """List data quality rules."""
        results = svc.list_rules(rule_type, dimension, limit=limit)
        if not results:
            return "No quality rules found."
        lines = [f"**Quality Rules** ({len(results)}):"]
        for r in results:
            lines.append(f"- {r.name} ({r.rule_type}, {r.dimension}, active={r.is_active})")
        return "\n".join(lines)

    @mcp_server.tool()
    async def execute_quality_rule(rule_id: str, connection_id: str, table_name: str) -> str:
        """Execute a quality rule against a table."""
        req = RuleExecuteRequest(rule_id=rule_id, connection_id=connection_id, table_name=table_name)
        result = svc.execute_rule(req)
        return (
            f"Rule execution: {result.status} "
            f"(checked={result.total_checked}, errors={result.error_count}, "
            f"pass_rate={result.pass_rate:.1f}%, duration={result.duration_ms}ms)"
        )

    @mcp_server.tool()
    async def run_validation(connection_id: str, engine: str, table_name: str, rule_ids: List[str] = None) -> str:
        """Run full validation against all active rules."""
        req = ValidateRequest(connection_id=connection_id, engine=engine, table_name=table_name, rule_ids=rule_ids)
        result = svc.execute_validation(req)
        return (
            f"Validation: {result.passed}/{result.total_rules} passed, "
            f"{result.failed} failed, {result.warnings} warnings "
            f"(pass rate: {result.overall_pass_rate:.1f}%)"
        )

    @mcp_server.tool()
    async def list_anomalies(connection_id: str = None, status: str = "open", limit: int = 10) -> str:
        """List detected data anomalies."""
        results = svc.list_anomalies(connection_id, status, limit=limit)
        if not results:
            return "No anomalies found."
        lines = [f"**Anomalies** ({len(results)}):"]
        for a in results:
            lines.append(f"- [{a.severity}] {a.anomaly_type} on {a.table_name}.{a.column_name} ({a.status})")
        return "\n".join(lines)

    @mcp_server.tool()
    async def list_drift_history(connection_id: str = None, table_name: str = None, limit: int = 10) -> str:
        """List schema/distribution drift history."""
        results = svc.list_drift(connection_id, table_name, limit=limit)
        if not results:
            return "No drift records found."
        lines = [f"**Drift History** ({len(results)}):"]
        for d in results:
            lines.append(f"- {d.drift_type} on {d.table_name} (score={d.drift_score}, breaking={d.is_breaking})")
        return "\n".join(lines)

    @mcp_server.tool()
    async def create_quality_alert(
        title: str, alert_type: str, severity: str = "info",
        source_type: str = "profiling", description: str = None,
        connection_id: str = None, table_name: str = None,
    ) -> str:
        """Create a quality alert."""
        req = AlertCreate(
            title=title, alert_type=alert_type, severity=severity,
            source_type=source_type, description=description,
            connection_id=connection_id, table_name=table_name,
        )
        result = svc.create_alert(req)
        return f"Created alert: {result.title} ({result.id}), severity={result.severity}"

    @mcp_server.tool()
    async def list_alerts(status: str = "open", severity: str = None, limit: int = 10) -> str:
        """List quality alerts."""
        results = svc.list_alerts(status, severity, limit=limit)
        if not results:
            return "No alerts found."
        lines = [f"**Alerts** ({len(results)}):"]
        for a in results:
            lines.append(f"- [{a.severity}] {a.title} ({a.status})")
        return "\n".join(lines)

    @mcp_server.tool()
    async def get_quality_dashboard() -> str:
        """Get data quality dashboard summary."""
        dash = svc.get_dashboard()
        return (
            f"**Quality Dashboard**\n"
            f"- Profiles: {dash.total_profiles}\n"
            f"- Active Rules: {dash.active_rules}\n"
            f"- Open Anomalies: {dash.open_anomalies}\n"
            f"- Open Alerts: {dash.open_alerts}\n"
            f"- Latest Score: {dash.latest_overall_score or 'N/A'}\n"
            f"- Recent Alerts: {len(dash.recent_alerts)}\n"
            f"- Recent Anomalies: {len(dash.recent_anomalies)}"
        )


def _format_profile(p: ProfileOut) -> str:
    return (
        f"**Profiling Complete**\n"
        f"- Table: {p.table_name}\n"
        f"- Type: {p.run_type}\n"
        f"- Status: {p.status}\n"
        f"- Columns: {p.profiled_columns}/{p.total_columns}\n"
        f"- Rows: {p.total_rows} (sampled: {p.sampled_rows})\n"
        f"- Duration: {p.duration_seconds}s\n"
        f"- ID: {p.id}"
    )
