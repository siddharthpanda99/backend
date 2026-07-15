"""Thin FastAPI router for Monitoring & Observability (UDS Module 17)."""

from fastapi import APIRouter, HTTPException
from common_lib.modules.db_studio.observability import (
    ObservabilityService,
    MetricIngestRequest, MetricOut, MetricSeriesOut,
    LogIngestRequest, LogEntryOut,
    TraceIngestRequest, TraceOut,
    SpanIngestRequest, SpanOut,
    AlertRuleCreate, AlertRuleOut,
    AlertHistoryOut,
    IncidentCreate, IncidentUpdate, IncidentOut,
    HealthCheckOut,
    ObservabilityDashboardOut,
)

router = APIRouter(prefix="/api/v1/observability", tags=["Observability"])
svc = ObservabilityService()


# ── Metrics ──────────────────────────────────────────────────────────

@router.post("/metrics/ingest", response_model=MetricOut)
def ingest_metric(req: MetricIngestRequest):
    return svc.ingest_metric(req)


@router.get("/metrics", response_model=list[MetricOut])
def list_metrics(source: str = None, metric_type: str = None, limit: int = 50):
    return svc.list_metrics(source, metric_type, limit)


@router.get("/metrics/{metric_id}/series", response_model=list[MetricSeriesOut])
def get_metric_series(metric_id: str, limit: int = 100):
    return svc.get_metric_series(metric_id, limit)


# ── Logs ─────────────────────────────────────────────────────────────

@router.post("/logs/ingest", response_model=LogEntryOut)
def ingest_log(req: LogIngestRequest):
    return svc.ingest_log(req)


@router.get("/logs", response_model=list[LogEntryOut])
def list_logs(level: str = None, source: str = None, trace_id: str = None,
              correlation_id: str = None, limit: int = 100):
    return svc.list_logs(level, source, trace_id, correlation_id, limit)


# ── Traces ───────────────────────────────────────────────────────────

@router.post("/traces/ingest", response_model=TraceOut)
def ingest_trace(req: TraceIngestRequest):
    return svc.ingest_trace(req)


@router.post("/traces/spans/ingest", response_model=SpanOut)
def ingest_span(req: SpanIngestRequest):
    return svc.ingest_span(req)


@router.get("/traces", response_model=list[TraceOut])
def list_traces(source: str = None, status: str = None, limit: int = 50):
    return svc.list_traces(source, status, limit)


@router.get("/traces/{trace_id}", response_model=TraceOut)
def get_trace(trace_id: str):
    result = svc.get_trace(trace_id)
    if not result:
        raise HTTPException(status_code=404, detail="Trace not found")
    return result


@router.get("/traces/{trace_id}/spans", response_model=list[SpanOut])
def list_spans(trace_id: str, limit: int = 100):
    return svc.list_spans(trace_id, limit)


# ── Alert Rules ──────────────────────────────────────────────────────

@router.post("/alert-rules", response_model=AlertRuleOut)
def create_alert_rule(req: AlertRuleCreate):
    return svc.create_alert_rule(req)


@router.get("/alert-rules", response_model=list[AlertRuleOut])
def list_alert_rules(source: str = None, is_active: bool = None, limit: int = 50):
    return svc.list_alert_rules(source, is_active, limit)


# ── Alert History ────────────────────────────────────────────────────

@router.get("/alerts", response_model=list[AlertHistoryOut])
def list_alert_history(status: str = None, severity: str = None, limit: int = 50):
    return svc.list_alert_history(status, severity, limit)


@router.patch("/alerts/{alert_id}/acknowledge", response_model=AlertHistoryOut)
def acknowledge_alert(alert_id: str, acknowledged_by: str):
    result = svc.acknowledge_alert(alert_id, acknowledged_by)
    if not result:
        raise HTTPException(status_code=404, detail="Alert not found")
    return result


@router.patch("/alerts/{alert_id}/resolve", response_model=AlertHistoryOut)
def resolve_alert(alert_id: str, resolved_by: str):
    result = svc.resolve_alert(alert_id, resolved_by)
    if not result:
        raise HTTPException(status_code=404, detail="Alert not found")
    return result


# ── Incidents ────────────────────────────────────────────────────────

@router.post("/incidents", response_model=IncidentOut)
def create_incident(req: IncidentCreate):
    return svc.create_incident(req)


@router.get("/incidents", response_model=list[IncidentOut])
def list_incidents(status: str = None, severity: str = None, limit: int = 50):
    return svc.list_incidents(status, severity, limit)


@router.patch("/incidents/{incident_id}", response_model=IncidentOut)
def update_incident(incident_id: str, req: IncidentUpdate):
    result = svc.update_incident(incident_id, req)
    if not result:
        raise HTTPException(status_code=404, detail="Incident not found")
    return result


# ── Health & Dashboard ───────────────────────────────────────────────

@router.get("/health", response_model=list[HealthCheckOut])
def check_health():
    return svc.check_health()


@router.get("/dashboard", response_model=ObservabilityDashboardOut)
def get_dashboard():
    return svc.get_dashboard()
