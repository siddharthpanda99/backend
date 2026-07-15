"""MCP tools for Monitoring & Observability (UDS Module 17)."""

from typing import Dict, List, Optional

from common_lib.modules.db_studio.observability import (
    ObservabilityService,
    MetricIngestRequest,
    LogIngestRequest,
    TraceIngestRequest, SpanIngestRequest,
    AlertRuleCreate,
    IncidentCreate,
)

svc = ObservabilityService()


def register_observability_tools(mcp_server):
    """Register all observability tools with the MCP server."""

    @mcp_server.tool()
    async def ingest_metric(name: str, value: float, metric_type: str = "gauge",
                            source: str = "system", unit: str = None,
                            source_id: str = None, tags: Dict[str, str] = None) -> str:
        """Ingest a metric data point."""
        req = MetricIngestRequest(name=name, value=value, metric_type=metric_type,
                                   source=source, unit=unit, source_id=source_id, tags=tags)
        result = svc.ingest_metric(req)
        return f"Ingested metric: {result.name} = {result.current_value} ({result.metric_type})"

    @mcp_server.tool()
    async def list_metrics(source: str = None, metric_type: str = None, limit: int = 20) -> str:
        """List metrics and their current values."""
        results = svc.list_metrics(source, metric_type, limit)
        if not results:
            return "No metrics found."
        lines = [f"**Metrics** ({len(results)}):"]
        for m in results:
            lines.append(f"- {m.name} = {m.current_value} [{m.metric_type}] (source: {m.source})")
        return "\n".join(lines)

    @mcp_server.tool()
    async def ingest_log(message: str, source: str, level: str = "info",
                         trace_id: str = None, correlation_id: str = None,
                         error_type: str = None, host: str = None, service: str = None) -> str:
        """Ingest a structured log entry."""
        req = LogIngestRequest(level=level, message=message, source=source,
                                trace_id=trace_id, correlation_id=correlation_id,
                                error_type=error_type, host=host, service=service)
        result = svc.ingest_log(req)
        return f"Ingested log: [{result.level}] {result.message[:60]}..."

    @mcp_server.tool()
    async def list_logs(level: str = None, source: str = None, limit: int = 20) -> str:
        """List log entries with optional filters."""
        results = svc.list_logs(level, source, limit=limit)
        if not results:
            return "No log entries found."
        lines = [f"**Logs** ({len(results)}):"]
        for l in results:
            lines.append(f"[{l.level}] {l.message[:80]} ({l.source})")
        return "\n".join(lines)

    @mcp_server.tool()
    async def ingest_trace(trace_id: str, name: str, source: str,
                           duration_ms: int = None, status: str = "ok",
                           service_name: str = None) -> str:
        """Ingest a distributed trace."""
        req = TraceIngestRequest(trace_id=trace_id, name=name, source=source,
                                  duration_ms=duration_ms, status=status,
                                  service_name=service_name)
        result = svc.ingest_trace(req)
        return f"Ingested trace: {result.name} ({result.status}, {result.duration_ms}ms)"

    @mcp_server.tool()
    async def list_traces(source: str = None, status: str = None, limit: int = 10) -> str:
        """List distributed traces."""
        results = svc.list_traces(source, status, limit)
        if not results:
            return "No traces found."
        lines = [f"**Traces** ({len(results)}):"]
        for t in results:
            lines.append(f"- {t.name} ({t.status}, {t.duration_ms}ms, {t.span_count} spans)")
        return "\n".join(lines)

    @mcp_server.tool()
    async def create_alert_rule(name: str, metric_name: str, condition: str,
                                threshold: float, severity: str = "warning",
                                evaluation_window: str = "5m",
                                description: str = None) -> str:
        """Create a monitoring alert rule."""
        req = AlertRuleCreate(name=name, metric_name=metric_name, condition=condition,
                               threshold=threshold, severity=severity,
                               evaluation_window=evaluation_window, description=description)
        result = svc.create_alert_rule(req)
        return f"Created alert rule: {result.name} ({result.condition} {result.threshold})"

    @mcp_server.tool()
    async def list_alert_rules(source: str = None, is_active: bool = None, limit: int = 20) -> str:
        """List alert rules."""
        results = svc.list_alert_rules(source, is_active, limit)
        if not results:
            return "No alert rules found."
        lines = [f"**Alert Rules** ({len(results)}):"]
        for r in results:
            lines.append(f"- {r.name}: {r.metric_name} {r.condition} {r.threshold} [{r.severity}]")
        return "\n".join(lines)

    @mcp_server.tool()
    async def list_alerts(status: str = "firing", severity: str = None, limit: int = 10) -> str:
        """List alert history."""
        results = svc.list_alert_history(status, severity, limit)
        if not results:
            return "No alerts found."
        lines = [f"**Alerts** ({len(results)}):"]
        for a in results:
            lines.append(f"- [{a.severity}] {a.rule_name} ({a.status})")
        return "\n".join(lines)

    @mcp_server.tool()
    async def acknowledge_alert(alert_id: str, acknowledged_by: str) -> str:
        """Acknowledge a firing alert."""
        result = svc.acknowledge_alert(alert_id, acknowledged_by)
        if not result:
            return f"Alert {alert_id} not found."
        return f"Acknowledged alert: {result.rule_name}"

    @mcp_server.tool()
    async def create_incident(title: str, severity: str = "medium",
                              description: str = None, assigned_to: str = None) -> str:
        """Create an incident."""
        req = IncidentCreate(title=title, severity=severity,
                              description=description, assigned_to=assigned_to)
        result = svc.create_incident(req)
        return f"Created incident: {result.title} ({result.id}), severity={result.severity}"

    @mcp_server.tool()
    async def list_incidents(status: str = "open", severity: str = None, limit: int = 10) -> str:
        """List incidents."""
        results = svc.list_incidents(status, severity, limit)
        if not results:
            return "No incidents found."
        lines = [f"**Incidents** ({len(results)}):"]
        for i in results:
            lines.append(f"- [{i.severity}] {i.title} ({i.status})")
        return "\n".join(lines)

    @mcp_server.tool()
    async def check_health() -> str:
        """Check system health status."""
        results = svc.check_health()
        lines = ["**System Health**:", "---"]
        for h in results:
            icon = "✅" if h.status == "healthy" else "⚠️"
            lines.append(f"{icon} {h.component}: {h.status} ({h.message})")
        return "\n".join(lines)

    @mcp_server.tool()
    async def get_observability_dashboard() -> str:
        """Get observability dashboard summary."""
        dash = svc.get_dashboard()
        return (
            f"**Observability Dashboard**\n"
            f"- Metrics: {dash.total_metrics}\n"
            f"- Active Alert Rules: {dash.active_alert_rules}\n"
            f"- Firing Alerts: {dash.firing_alerts}\n"
            f"- Open Incidents: {dash.open_incidents}\n"
            f"- Recent Logs: {len(dash.recent_logs)}\n"
            f"- Recent Alerts: {len(dash.recent_alerts)}\n"
            f"- Health: {len(dash.health_summary)} components checked"
        )
