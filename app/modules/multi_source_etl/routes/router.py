"""Thin FastAPI router for Multi-Source ETL — pipelines, query, infra, seed, init, migrations."""

import logging
from typing import Optional, List
from pydantic import BaseModel

from fastapi import APIRouter, HTTPException, Query

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
    MonitorMetric,
    MetricsResponse,
)

from common_lib.modules.multi_source_etl.query_executor import (
    execute_query,
    get_schema,
    list_tables as ql_list_tables,
    describe_table as ql_describe_table,
    test_connection,
    get_connection_info,
    execute_batch,
    list_connections,
)

from common_lib.modules.multi_source_etl.etl_infra import (
    container_up,
    container_down,
    container_status,
    container_logs,
    container_build,
    container_restart,
)

from common_lib.modules.multi_source_etl.etl_init import init_all as etl_init_all
from common_lib.modules.multi_source_etl.etl_migrations import (
    list_migrations,
    run_migrations,
    rollback_migration,
    create_migration,
    migration_status,
)
from common_lib.modules.multi_source_etl.etl_seed import (
    seed_all,
    seed_use_case,
    list_use_cases as seed_list_use_cases,
    load_seed,
)

logger = logging.getLogger(__name__)

router = APIRouter()
svc = MultiSourceETLService()


# ── Request / Response models ──────────────────────────────────────────────


class QueryRequest(BaseModel):
    command: str
    params: Optional[dict] = None
    timeout: Optional[int] = 30


class BatchQueryRequest(BaseModel):
    commands: List[str]
    timeout: Optional[int] = 60


class ContainerUpRequest(BaseModel):
    service: Optional[str] = None
    build: bool = False


class ContainerBuildRequest(BaseModel):
    service: Optional[str] = None
    no_cache: bool = False


class ContainerLogsRequest(BaseModel):
    service: Optional[str] = None
    tail: int = 100


class MigrateApplyRequest(BaseModel):
    dry_run: bool = False


class MigrateRollbackRequest(BaseModel):
    version: str


class MigrateCreateRequest(BaseModel):
    name: str
    schema_path: Optional[str] = None


class SeedRequest(BaseModel):
    use_cases: Optional[List[str]] = None
    dry_run: bool = False


class InitRequest(BaseModel):
    pass


class SeedUseCaseRequest(BaseModel):
    use_case_id: Optional[str] = None
    dry_run: bool = False


# ═══════════════════════════════════════════════════════════════════════════
# Existing pipeline / trigger endpoints
# ═══════════════════════════════════════════════════════════════════════════


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


# ═══════════════════════════════════════════════════════════════════════════
# Connection management
# ═══════════════════════════════════════════════════════════════════════════


@router.get("/connections")
def api_list_connections():
    return list_connections()


@router.get("/connections/{conn_id}")
def api_connection_info(conn_id: str):
    result = get_connection_info(conn_id)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error", "Not found"))
    return result


@router.post("/connections/{conn_id}/test")
def api_test_connection(conn_id: str):
    return test_connection(conn_id)


# ═══════════════════════════════════════════════════════════════════════════
# Query execution
# ═══════════════════════════════════════════════════════════════════════════


@router.post("/connections/{conn_id}/query")
def api_execute_query(conn_id: str, req: QueryRequest):
    result = execute_query(conn_id, req.command, req.params, req.timeout or 30)
    return result


@router.post("/connections/{conn_id}/query/batch")
def api_execute_batch(conn_id: str, req: BatchQueryRequest):
    return execute_batch(conn_id, req.commands, req.timeout or 60)


# ═══════════════════════════════════════════════════════════════════════════
# Schema browsing
# ═══════════════════════════════════════════════════════════════════════════


@router.get("/connections/{conn_id}/schema")
def api_get_schema(conn_id: str):
    return get_schema(conn_id)


@router.get("/connections/{conn_id}/tables")
def api_list_tables(conn_id: str):
    return ql_list_tables(conn_id)


@router.get("/connections/{conn_id}/tables/{table}")
def api_describe_table(conn_id: str, table: str):
    return ql_describe_table(conn_id, table)


# ═══════════════════════════════════════════════════════════════════════════
# Infrastructure
# ═══════════════════════════════════════════════════════════════════════════


@router.post("/infra/up")
def api_container_up(req: ContainerUpRequest = ContainerUpRequest()):
    return container_up(service=req.service, build=req.build)


@router.post("/infra/down")
def api_container_down():
    return container_down()


@router.get("/infra/status")
def api_container_status():
    return container_status()


@router.post("/infra/logs")
def api_container_logs(req: ContainerLogsRequest = ContainerLogsRequest()):
    return {"logs": container_logs(service=req.service, tail=req.tail)}


@router.post("/infra/build")
def api_container_build(req: ContainerBuildRequest = ContainerBuildRequest()):
    return container_build(service=req.service, no_cache=req.no_cache)


@router.post("/infra/restart")
def api_container_restart():
    return container_restart()


# ═══════════════════════════════════════════════════════════════════════════
# Init
# ═══════════════════════════════════════════════════════════════════════════


@router.post("/init")
def api_etl_init(req: InitRequest = InitRequest()):
    ok = etl_init_all()
    return {"success": ok}


# ═══════════════════════════════════════════════════════════════════════════
# Seed
# ═══════════════════════════════════════════════════════════════════════════


@router.get("/seed/use-cases")
def api_seed_use_cases():
    return {"use_cases": seed_list_use_cases()}


@router.get("/seed/use-cases/{use_case_id}")
def api_seed_use_case_info(use_case_id: str):
    data = load_seed(use_case_id)
    if not data:
        raise HTTPException(
            status_code=404, detail=f"Use case '{use_case_id}' not found"
        )
    return data


@router.post("/seed")
def api_seed(req: SeedRequest = SeedRequest()):
    ok = seed_all(use_cases=req.use_cases, dry_run=req.dry_run)
    return {"success": ok, "dry_run": req.dry_run}


@router.post("/seed/{use_case_id}")
def api_seed_single(use_case_id: str, req: SeedUseCaseRequest = SeedUseCaseRequest()):
    ok = seed_use_case(use_case_id, dry_run=req.dry_run)
    if not ok:
        raise HTTPException(status_code=400, detail=f"Seeding '{use_case_id}' failed")
    return {"success": ok, "use_case_id": use_case_id, "dry_run": req.dry_run}


# ═══════════════════════════════════════════════════════════════════════════
# Migrations
# ═══════════════════════════════════════════════════════════════════════════


@router.get("/connections/{conn_id}/migrations")
def api_list_migrations(conn_id: str):
    return list_migrations(conn_id)


@router.post("/connections/{conn_id}/migrations/apply")
def api_apply_migrations(
    conn_id: str, req: MigrateApplyRequest = MigrateApplyRequest()
):
    return run_migrations(conn_id, dry_run=req.dry_run)


@router.post("/connections/{conn_id}/migrations/rollback")
def api_rollback_migration(conn_id: str, req: MigrateRollbackRequest):
    return rollback_migration(conn_id, req.version)


@router.post("/connections/{conn_id}/migrations/create")
def api_create_migration(conn_id: str, req: MigrateCreateRequest):
    return create_migration(conn_id, req.name, req.schema_path)


@router.get("/connections/{conn_id}/migrations/status")
def api_migration_status(conn_id: str):
    return migration_status(conn_id)


__all__ = ["router"]
