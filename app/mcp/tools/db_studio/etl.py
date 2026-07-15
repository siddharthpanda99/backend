"""MCP tools for ETL/ELT/Reverse ETL Platform (UDS Module 15)."""

import json
import logging
from typing import Any, Dict, List, Optional

from common_lib.modules.db_studio.etl import (
    ETLService,
    PipelineCreate,
    PipelineValidateRequest,
    ExecutionRunRequest,
    ScheduleCreate,
    ConnectorConfigCreate,
)

logger = logging.getLogger(__name__)
service = ETLService()


def register_etl_tools(mcp_server):
    """Register all ETL/ELT/Reverse ETL MCP tools."""

    # ── Pipeline Tools ───────────────────────────────────────────────

    @mcp_server.tool(description="Create a new ETL/ELT/reverse-ETL/CDC pipeline")
    async def create_pipeline(
        name: str,
        description: Optional[str] = None,
        pipeline_type: str = "etl",
        source_type: Optional[str] = None,
        destination_type: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> str:
        """Create a pipeline definition."""
        req = PipelineCreate(
            name=name, description=description,
            pipeline_type=pipeline_type, source_type=source_type,
            destination_type=destination_type, tags=tags,
        )
        result = service.create_pipeline(req)
        return json.dumps(result.model_dump(), indent=2, default=str)

    @mcp_server.tool(description="List pipelines with optional type/status filters")
    async def list_pipelines(
        pipeline_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> str:
        """List pipelines."""
        results = service.list_pipelines(pipeline_type, status, limit)
        return json.dumps([r.model_dump() for r in results], indent=2, default=str)

    @mcp_server.tool(description="Get a specific pipeline by ID")
    async def get_pipeline(pipeline_id: str) -> str:
        """Get a pipeline."""
        result = service.get_pipeline(pipeline_id)
        if not result:
            return json.dumps({"error": "Pipeline not found"})
        return json.dumps(result.model_dump(), indent=2, default=str)

    @mcp_server.tool(description="Validate a pipeline definition for correctness")
    async def validate_pipeline(pipeline_id: str) -> str:
        """Validate a pipeline."""
        req = PipelineValidateRequest(pipeline_id=pipeline_id)
        result = service.validate_pipeline(req)
        return json.dumps(result.model_dump(), indent=2, default=str)

    # ── Execution Tools ──────────────────────────────────────────────

    @mcp_server.tool(description="Execute a pipeline and get results")
    async def run_execution(
        pipeline_id: str,
        execution_type: str = "manual",
        start_nodes: Optional[List[str]] = None,
    ) -> str:
        """Run a pipeline execution."""
        req = ExecutionRunRequest(
            pipeline_id=pipeline_id, execution_type=execution_type,
            start_nodes=start_nodes,
        )
        result = service.run_execution(req)
        return json.dumps(result.model_dump(), indent=2, default=str)

    @mcp_server.tool(description="List pipeline executions with optional filters")
    async def list_executions(
        pipeline_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> str:
        """List executions."""
        results = service.list_executions(pipeline_id, status, limit)
        return json.dumps([r.model_dump() for r in results], indent=2, default=str)

    @mcp_server.tool(description="Get a specific execution by ID")
    async def get_execution(execution_id: str) -> str:
        """Get an execution."""
        result = service.get_execution(execution_id)
        if not result:
            return json.dumps({"error": "Execution not found"})
        return json.dumps(result.model_dump(), indent=2, default=str)

    # ── Schedule Tools ───────────────────────────────────────────────

    @mcp_server.tool(description="Create a scheduled run for a pipeline")
    async def create_schedule(
        pipeline_id: str,
        name: str,
        cron_expression: str,
        timezone: str = "UTC",
        max_concurrent: int = 1,
        retry_on_failure: bool = True,
        max_retries: int = 3,
        notify_on_failure: bool = False,
        notify_email: Optional[str] = None,
    ) -> str:
        """Create a pipeline schedule."""
        req = ScheduleCreate(
            pipeline_id=pipeline_id, name=name, cron_expression=cron_expression,
            timezone=timezone, max_concurrent=max_concurrent,
            retry_on_failure=retry_on_failure, max_retries=max_retries,
            notify_on_failure=notify_on_failure, notify_email=notify_email,
        )
        result = service.create_schedule(req)
        return json.dumps(result.model_dump(), indent=2, default=str)

    @mcp_server.tool(description="List pipeline schedules with optional filters")
    async def list_schedules(
        pipeline_id: Optional[str] = None,
        is_active: Optional[bool] = None,
        limit: int = 50,
    ) -> str:
        """List schedules."""
        results = service.list_schedules(pipeline_id, is_active, limit)
        return json.dumps([r.model_dump() for r in results], indent=2, default=str)

    # ── CDC Offset Tools ─────────────────────────────────────────────

    @mcp_server.tool(description="List CDC offset tracking states for pipelines")
    async def list_cdc_offsets(
        pipeline_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> str:
        """List CDC offsets."""
        results = service.list_cdc_offsets(pipeline_id, status, limit)
        return json.dumps([r.model_dump() for r in results], indent=2, default=str)

    # ── Lineage Tools ────────────────────────────────────────────────

    @mcp_server.tool(description="List data lineage records for pipelines or executions")
    async def list_lineage(
        pipeline_id: Optional[str] = None,
        execution_id: Optional[str] = None,
        limit: int = 50,
    ) -> str:
        """List lineage records."""
        results = service.list_lineage(pipeline_id, execution_id, limit)
        return json.dumps([r.model_dump() for r in results], indent=2, default=str)

    @mcp_server.tool(description="Get the lineage graph (nodes + edges) for a pipeline")
    async def get_lineage_graph(pipeline_id: str) -> str:
        """Get lineage graph."""
        result = service.get_lineage_graph(pipeline_id)
        return json.dumps(result.model_dump(), indent=2, default=str)

    # ── Connector Config Tools ───────────────────────────────────────

    @mcp_server.tool(description="Create a connector configuration for pipeline sources/destinations")
    async def create_connector_config(
        name: str,
        connector_type: str,
        engine: str,
        config: Optional[Dict[str, Any]] = None,
        max_connections: int = 5,
        timeout_seconds: int = 30,
        retry_count: int = 3,
    ) -> str:
        """Create a connector config."""
        req = ConnectorConfigCreate(
            name=name, connector_type=connector_type, engine=engine,
            config=config, max_connections=max_connections,
            timeout_seconds=timeout_seconds, retry_count=retry_count,
        )
        result = service.create_connector_config(req)
        return json.dumps(result.model_dump(), indent=2, default=str)

    @mcp_server.tool(description="List connector configurations with optional filters")
    async def list_connector_configs(
        connector_type: Optional[str] = None,
        engine: Optional[str] = None,
        limit: int = 50,
    ) -> str:
        """List connector configs."""
        results = service.list_connector_configs(connector_type, engine, limit)
        return json.dumps([r.model_dump() for r in results], indent=2, default=str)

    @mcp_server.tool(description="Test a connector configuration's connectivity")
    async def test_connector(connector_id: str) -> str:
        """Test a connector."""
        result = service.test_connector(connector_id)
        if not result:
            return json.dumps({"error": "Connector not found"})
        return json.dumps(result.model_dump(), indent=2, default=str)

    # ── Execution Log Tools ──────────────────────────────────────────

    @mcp_server.tool(description="List execution log entries with optional filters")
    async def list_execution_logs(
        execution_id: Optional[str] = None,
        pipeline_id: Optional[str] = None,
        log_level: Optional[str] = None,
        limit: int = 100,
    ) -> str:
        """List execution logs."""
        results = service.list_execution_logs(execution_id, pipeline_id, log_level, limit)
        return json.dumps([r.model_dump() for r in results], indent=2, default=str)

    # ── Dashboard & Audit Tools ──────────────────────────────────────

    @mcp_server.tool(description="Get the ETL dashboard summary with metrics and recent executions")
    async def get_etl_dashboard() -> str:
        """Get ETL dashboard."""
        result = service.get_dashboard()
        return json.dumps(result.model_dump(), indent=2, default=str)

    @mcp_server.tool(description="List ETL audit log entries")
    async def list_etl_audit_logs(
        action: Optional[str] = None,
        target_type: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 50,
    ) -> str:
        """List ETL audit logs."""
        results = service.list_audit_logs(action, target_type, severity, limit)
        return json.dumps([r.model_dump() for r in results], indent=2, default=str)
