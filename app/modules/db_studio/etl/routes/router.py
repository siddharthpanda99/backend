"""Thin backend route wrappers for ETL/ELT/Reverse ETL Platform (UDS Module 15)."""

from fastapi import APIRouter, HTTPException

from common_lib.modules.db_studio.etl import (
    ETLService,
    PipelineCreate, PipelineOut, PipelineValidateRequest, PipelineValidationOut,
    ExecutionRunRequest, ExecutionOut,
    ScheduleCreate, ScheduleOut,
    CDCOffsetOut,
    LineageOut, LineageGraphOut,
    ConnectorConfigCreate, ConnectorConfigOut,
    ExecutionLogOut,
    ETLDashboardOut, ETLAuditOut,
)

service = ETLService()


def get_router() -> APIRouter:
    router = APIRouter(prefix="/api/v1/etl", tags=["ETL/ELT/Reverse ETL Platform"])

    # ── Dashboard ────────────────────────────────────────────────────

    @router.get("/dashboard", response_model=ETLDashboardOut)
    async def get_dashboard():
        return service.get_dashboard()

    # ── Pipelines ────────────────────────────────────────────────────

    @router.post("/pipelines", response_model=PipelineOut)
    async def create_pipeline(req: PipelineCreate):
        return service.create_pipeline(req)

    @router.get("/pipelines", response_model=list[PipelineOut])
    async def list_pipelines(
        pipeline_type: str = None, status: str = None, limit: int = 50,
    ):
        return service.list_pipelines(pipeline_type, status, limit)

    @router.get("/pipelines/{pipeline_id}", response_model=PipelineOut)
    async def get_pipeline(pipeline_id: str):
        result = service.get_pipeline(pipeline_id)
        if not result:
            raise HTTPException(status_code=404, detail="Pipeline not found")
        return result

    @router.post("/pipelines/validate", response_model=PipelineValidationOut)
    async def validate_pipeline(req: PipelineValidateRequest):
        return service.validate_pipeline(req)

    # ── Executions ───────────────────────────────────────────────────

    @router.post("/executions", response_model=ExecutionOut)
    async def run_execution(req: ExecutionRunRequest):
        return service.run_execution(req)

    @router.get("/executions", response_model=list[ExecutionOut])
    async def list_executions(
        pipeline_id: str = None, status: str = None, limit: int = 50,
    ):
        return service.list_executions(pipeline_id, status, limit)

    @router.get("/executions/{execution_id}", response_model=ExecutionOut)
    async def get_execution(execution_id: str):
        result = service.get_execution(execution_id)
        if not result:
            raise HTTPException(status_code=404, detail="Execution not found")
        return result

    # ── Schedules ────────────────────────────────────────────────────

    @router.post("/schedules", response_model=ScheduleOut)
    async def create_schedule(req: ScheduleCreate):
        return service.create_schedule(req)

    @router.get("/schedules", response_model=list[ScheduleOut])
    async def list_schedules(
        pipeline_id: str = None, is_active: bool = None, limit: int = 50,
    ):
        return service.list_schedules(pipeline_id, is_active, limit)

    # ── CDC Offsets ──────────────────────────────────────────────────

    @router.get("/cdc-offsets", response_model=list[CDCOffsetOut])
    async def list_cdc_offsets(
        pipeline_id: str = None, status: str = None, limit: int = 50,
    ):
        return service.list_cdc_offsets(pipeline_id, status, limit)

    # ── Lineage ──────────────────────────────────────────────────────

    @router.get("/lineage", response_model=list[LineageOut])
    async def list_lineage(
        pipeline_id: str = None, execution_id: str = None, limit: int = 50,
    ):
        return service.list_lineage(pipeline_id, execution_id, limit)

    @router.get("/lineage/graph/{pipeline_id}", response_model=LineageGraphOut)
    async def get_lineage_graph(pipeline_id: str):
        return service.get_lineage_graph(pipeline_id)

    # ── Connector Configs ────────────────────────────────────────────

    @router.post("/connectors", response_model=ConnectorConfigOut)
    async def create_connector(req: ConnectorConfigCreate):
        return service.create_connector_config(req)

    @router.get("/connectors", response_model=list[ConnectorConfigOut])
    async def list_connectors(
        connector_type: str = None, engine: str = None, limit: int = 50,
    ):
        return service.list_connector_configs(connector_type, engine, limit)

    @router.post("/connectors/{connector_id}/test", response_model=ConnectorConfigOut)
    async def test_connector(connector_id: str):
        result = service.test_connector(connector_id)
        if not result:
            raise HTTPException(status_code=404, detail="Connector not found")
        return result

    # ── Execution Logs ───────────────────────────────────────────────

    @router.get("/execution-logs", response_model=list[ExecutionLogOut])
    async def list_execution_logs(
        execution_id: str = None, pipeline_id: str = None,
        log_level: str = None, limit: int = 100,
    ):
        return service.list_execution_logs(execution_id, pipeline_id, log_level, limit)

    # ── Audit ────────────────────────────────────────────────────────

    @router.get("/audit", response_model=list[ETLAuditOut])
    async def list_audit_logs(
        action: str = None, target_type: str = None,
        severity: str = None, limit: int = 50,
    ):
        return service.list_audit_logs(action, target_type, severity, limit)

    return router
