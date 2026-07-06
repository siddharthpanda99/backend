"""Thin FastAPI router for Multi-Source ETL pipelines.

All business logic lives in common_lib.modules.multi_source_etl.
"""

import logging
from fastapi import APIRouter, HTTPException

from common_lib.modules.multi_source_etl import (
    MultiSourceETLService,
    PipelineRunRequest,
    PipelineRunResponse,
    PipelineStatusResponse,
    PipelineRunListResponse,
    PipelineRunSummary,
    ReportOutput,
    UseCaseListResponse,
    UseCaseInfo,
    TriggerConfig,
    TriggerCreate,
    TriggerUpdate,
    TriggerListResponse,
    TriggerType,
    TriggerStatus,
    MonitorMetric,
    MetricsResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()
svc = MultiSourceETLService()


@router.get("/use-cases", response_model=UseCaseListResponse)
def list_use_cases():
    items = svc.list_use_cases()
    return UseCaseListResponse(items=items, total=len(items))


@router.get("/use-cases/{use_case_id}", response_model=UseCaseInfo)
def get_use_case(use_case_id: str):
    info = svc.get_use_case(use_case_id)
    if not info:
        raise HTTPException(
            status_code=404, detail=f"Use case '{use_case_id}' not found"
        )
    return info


@router.post("/run", response_model=PipelineRunResponse)
def start_pipeline(req: PipelineRunRequest):
    try:
        return svc.start_pipeline(req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/run/{pipeline_id}/execute", response_model=PipelineStatusResponse)
def execute_pipeline(pipeline_id: str):
    try:
        return svc.run_pipeline(pipeline_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/status/{pipeline_id}", response_model=PipelineStatusResponse)
def pipeline_status(pipeline_id: str):
    status = svc.get_pipeline_status(pipeline_id)
    if not status:
        raise HTTPException(
            status_code=404, detail=f"Pipeline '{pipeline_id}' not found"
        )
    return status


@router.get("/results/{pipeline_id}", response_model=ReportOutput)
def pipeline_results(pipeline_id: str):
    result = svc.get_pipeline_result(pipeline_id)
    if not result:
        raise HTTPException(
            status_code=404, detail=f"No results for pipeline '{pipeline_id}'"
        )
    return result


@router.get("/runs", response_model=PipelineRunListResponse)
def list_runs():
    runs = svc.list_runs()
    return PipelineRunListResponse(runs=runs, total=len(runs))


@router.get("/triggers", response_model=TriggerListResponse)
def list_triggers():
    triggers = svc.list_triggers()
    return TriggerListResponse(triggers=triggers, total=len(triggers))


@router.post("/triggers", response_model=TriggerConfig, status_code=201)
def create_trigger(req: TriggerCreate):
    return svc.create_trigger(req)


@router.put("/triggers/{trigger_id}", response_model=TriggerConfig)
def update_trigger(trigger_id: str, req: TriggerUpdate):
    updated = svc.update_trigger(trigger_id, req)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Trigger '{trigger_id}' not found")
    return updated


@router.delete("/triggers/{trigger_id}")
def delete_trigger(trigger_id: str):
    if not svc.delete_trigger(trigger_id):
        raise HTTPException(status_code=404, detail=f"Trigger '{trigger_id}' not found")
    return {"ok": True}


@router.get("/metrics", response_model=MetricsResponse)
def get_metrics():
    metrics = svc.get_metrics()
    return MetricsResponse(metrics=metrics, total=len(metrics))


__all__ = ["router"]
