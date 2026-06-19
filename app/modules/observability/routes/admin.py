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

    return {"slos": SLOManager.list_slos(), "evaluations": SLOManager.evaluate()}


@router.get("/observability/traces")
async def get_traces():
    from common_lib.modules.observability import get_observability

    obs = get_observability()
    return {"traces": obs.get_recent_traces(20)}


@router.get("/observability/metrics")
async def get_metrics():
    from common_lib.modules.observability import get_observability

    obs = get_observability()
    return obs.get_all_metrics()


@router.get("/observability/alerts")
async def get_alerts():
    from common_lib.modules.observability import get_observability

    obs = get_observability()
    return {"alerts": obs.get_active_alerts()}


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
