import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.modules.common.types.index import APIResponse
from common_lib.modules.observability.experiments.experiment_tracker import (
    ExperimentTracker,
    list_experiments,
    get_experiment,
    create_experiment,
    delete_experiment,
    list_runs,
    get_run_metrics,
    get_run_params,
    get_run_artifacts,
    ENABLE_NATIVE_EXPERIMENTS,
)
from common_lib.modules.observability.experiment_models import (
    Experiment,
    ExperimentRun,
    RunMetric,
    RunParam,
    RunArtifact,
)

logger = logging.getLogger(__name__)

router = APIRouter()


class ExperimentCreate(BaseModel):
    name: str
    description: Optional[str] = None
    tags: Optional[Dict[str, str]] = None


class RunCreate(BaseModel):
    experiment_id: int
    run_name: Optional[str] = None
    tags: Optional[Dict[str, str]] = None


class MetricsLog(BaseModel):
    metrics: Dict[str, float]
    step: Optional[int] = None


class ParamsLog(BaseModel):
    params: Dict[str, Any]


# ─── Experiments CRUD ──────────────────────────────────────────────────


@router.get("/", response_model=APIResponse)
async def get_experiments():
    if not ENABLE_NATIVE_EXPERIMENTS:
        return APIResponse(data=[], message="Native experiments disabled")
    exps = list_experiments()
    return APIResponse(
        data=[e.model_dump() for e in exps],
        message=f"Found {len(exps)} experiments",
    )


@router.get("/{experiment_id}", response_model=APIResponse)
async def get_experiment_by_id(experiment_id: int):
    exp = get_experiment(experiment_id)
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return APIResponse(data=exp.model_dump())


@router.post("/", response_model=APIResponse, status_code=201)
async def new_experiment(body: ExperimentCreate):
    exp = create_experiment(
        name=body.name,
        description=body.description,
        tags=body.tags,
    )
    return APIResponse(data=exp.model_dump(), message="Experiment created")


@router.delete("/{experiment_id}", response_model=APIResponse)
async def remove_experiment(experiment_id: int):
    ok = delete_experiment(experiment_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return APIResponse(message="Experiment deleted")


# ─── Runs ──────────────────────────────────────────────────────────────


@router.post("/{experiment_id}/runs", response_model=APIResponse, status_code=201)
async def start_run(experiment_id: int, body: RunCreate):
    exp = get_experiment(experiment_id)
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")
    tracker = ExperimentTracker(exp.name)
    return APIResponse(
        data={
            "experiment_id": experiment_id,
            "message": "Run started — use tracker.log_* methods in backend code",
        }
    )


@router.get("/{experiment_id}/runs", response_model=APIResponse)
async def get_runs(
    experiment_id: int,
    limit: int = Query(100, le=500),
    status: Optional[str] = None,
):
    exp = get_experiment(experiment_id)
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")
    runs = list_runs(experiment_id, max_results=limit)
    if status:
        runs = [r for r in runs if r.status == status]
    return APIResponse(data=[r.model_dump() for r in runs])


# ─── Run Details (metrics, params, artifacts) ──────────────────────────


@router.get("/runs/{run_id}/metrics", response_model=APIResponse)
async def get_metrics(run_id: int):
    metrics = get_run_metrics(run_id)
    return APIResponse(data=[m.model_dump() for m in metrics])


@router.get("/runs/{run_id}/params", response_model=APIResponse)
async def get_params(run_id: int):
    params = get_run_params(run_id)
    return APIResponse(data=[p.model_dump() for p in params])


@router.get("/runs/{run_id}/artifacts", response_model=APIResponse)
async def get_artifacts(run_id: int):
    artifacts = get_run_artifacts(run_id)
    return APIResponse(data=[a.model_dump() for a in artifacts])
