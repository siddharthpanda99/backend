"""Observability Admin Routes.

MOVED from common_lib/modules/observability/admin_routes.py
per P0.3 boundary rules: ALL route definitions belong in app/modules,
common_lib provides only services and models.
"""

from fastapi import APIRouter

router = APIRouter(tags=["Observability Admin"])


@router.get("/observability/slos")
async def get_slos():
    from common_lib.modules.observability.slos import SLOManager
    from common_lib.modules.observability import get_observability

    # Make sure defaults are registered and some metrics exist
    get_observability()
    SLOManager.register_defaults()

    evaluations = SLOManager.evaluate()
    mapped_slos = []
    for ev in evaluations:
        if "error" in ev:
            continue
        mapped_slos.append({
            "name": ev["name"],
            "target": ev["target"] * 100,  # e.g., 99.0 instead of 0.99
            "current": ev["current_value"] * 100,  # e.g., 99.5 instead of 0.995
            "budget": ev["error_budget_remaining_pct"],
            "eval_window": "7d" if ev["window_seconds"] == 86400 * 7 else "24h"
        })
    return mapped_slos


@router.get("/observability/traces")
async def get_traces():
    from common_lib.modules.observability import get_observability
    from datetime import datetime, timezone

    obs = get_observability()
    flat_traces = []
    for span in obs._spans:
        flat_traces.append({
            "id": span.context.trace_id,
            "operation": span.name,
            "module": span.attributes.get("module", "agentic_os"),
            "duration_ms": round(span.duration_ms, 2),
            "status": span.status,
            "timestamp": datetime.fromtimestamp(span.start_time, timezone.utc).isoformat(),
            "tags": [str(v) for v in span.attributes.get("tags", [])],
            "cost": span.attributes.get("cost"),
            "tokens": span.attributes.get("tokens"),
            "metadata": span.attributes,
        })
    flat_traces.reverse()
    return flat_traces


@router.get("/observability/metrics")
async def get_metrics():
    from common_lib.modules.observability import get_observability
    from datetime import datetime, timezone

    obs = get_observability()
    metrics_data = obs.get_all_metrics()
    flat_metrics = []
    
    # Map counters
    for name, val in metrics_data.get("counters", {}).items():
        flat_metrics.append({
            "name": name,
            "value": val,
            "unit": "count",
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    # Map gauges
    for name, val in metrics_data.get("gauges", {}).items():
        flat_metrics.append({
            "name": name,
            "value": val,
            "unit": "gauge",
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    return flat_metrics


@router.get("/observability/alerts")
async def get_alerts():
    from common_lib.modules.observability import get_observability

    obs = get_observability()
    alerts = obs.get_active_alerts()
    flat_alerts = []
    for alert in alerts:
        flat_alerts.append({
            "id": alert.rule_name,
            "name": alert.rule_name.replace("_", " ").title(),
            "severity": alert.severity,
            "status": "firing",
            "message": alert.message,
            "timestamp": alert.triggered_at,
        })
    return flat_alerts


@router.post("/observability/alerts/evaluate")
async def evaluate_alerts():
    from common_lib.modules.observability import get_observability

    obs = get_observability()
    alerts = obs.evaluate_alerts()
    return {"alerts": alerts}


@router.get("/observability/slos/{slo_name}/budget")
async def get_slo_budget(slo_name: str):
    from common_lib.modules.observability.slos import SLOManager

    budget = SLOManager.get_budget(slo_name)
    if not budget:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail=f"SLO '{slo_name}' not found")
    return {"budget": budget}


@router.get("/observability/lineage")
async def get_lineage(
    trace_id: str = "",
    limit: int = 50,
):
    from common_lib.modules.observability import get_observability

    obs = get_observability()
    if trace_id:
        return {"trace": obs.get_trace(trace_id)}
    return {"traces": obs.get_recent_traces(limit)}
