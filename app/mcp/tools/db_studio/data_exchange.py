"""MCP tools for Import, Export & Data Exchange (UDS Module 14)."""

import logging
from typing import Any, Dict, List, Optional

from common_lib.modules.db_studio.data_exchange import (
    DataExchangeService,
    ImportRequest, ExportRequest,
    MappingTemplateCreate,
    ValidationRequest,
    TransformationRuleCreate,
)

logger = logging.getLogger(__name__)
service = DataExchangeService()


def register_data_exchange_tools(mcp_server):
    """Register all import, export, and data exchange MCP tools."""

    # ── Import Tools ──────────────────────────────────────────────────

    @mcp_server.tool(description="Import data from a file into a database table")
    async def run_import(
        connection_id: str,
        target_table: str,
        file_path: str,
        engine: str = "postgresql",
        file_format: str = "csv",
        import_mode: str = "insert",
        has_header: bool = True,
        delimiter: Optional[str] = None,
        encoding: str = "utf-8",
        compression: Optional[str] = None,
        mapping_template_id: Optional[str] = None,
        validate_before: bool = True,
    ) -> str:
        """Run a data import."""
        req = ImportRequest(
            connection_id=connection_id, target_table=target_table,
            file_path=file_path, engine=engine, file_format=file_format,
            import_mode=import_mode, has_header=has_header, delimiter=delimiter,
            encoding=encoding, compression=compression,
            mapping_template_id=mapping_template_id, validate_before=validate_before,
        )
        result = service.run_import(req)
        import json
        return json.dumps(result.model_dump(), indent=2, default=str)

    @mcp_server.tool(description="List import jobs with optional filters")
    async def list_imports(
        connection_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> str:
        """List import jobs."""
        results = service.list_imports(connection_id, status, limit)
        import json
        return json.dumps([r.model_dump() for r in results], indent=2, default=str)

    # ── Export Tools ──────────────────────────────────────────────────

    @mcp_server.tool(description="Export data from a database to a file")
    async def run_export(
        connection_id: str,
        source_query: str,
        engine: str = "postgresql",
        file_format: str = "csv",
        file_path: Optional[str] = None,
        destination: str = "local",
        destination_path: Optional[str] = None,
        compression: Optional[str] = None,
        include_header: bool = True,
        delimiter: Optional[str] = None,
        encoding: str = "utf-8",
        max_rows: Optional[int] = None,
    ) -> str:
        """Run a data export."""
        req = ExportRequest(
            connection_id=connection_id, source_query=source_query, engine=engine,
            file_format=file_format, file_path=file_path, destination=destination,
            destination_path=destination_path, compression=compression,
            include_header=include_header, delimiter=delimiter,
            encoding=encoding, max_rows=max_rows,
        )
        result = service.run_export(req)
        import json
        return json.dumps(result.model_dump(), indent=2, default=str)

    @mcp_server.tool(description="List export jobs with optional filters")
    async def list_exports(
        connection_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> str:
        """List export jobs."""
        results = service.list_exports(connection_id, status, limit)
        import json
        return json.dumps([r.model_dump() for r in results], indent=2, default=str)

    # ── Mapping Tools ─────────────────────────────────────────────────

    @mcp_server.tool(description="Create a schema mapping template between source and target formats")
    async def create_mapping_template(
        name: str,
        source_format: str,
        target_format: str,
        description: Optional[str] = None,
        mappings: Optional[List[Dict[str, Any]]] = None,
        tags: Optional[List[str]] = None,
    ) -> str:
        """Create a mapping template."""
        req = MappingTemplateCreate(
            name=name, source_format=source_format, target_format=target_format,
            description=description, mappings=mappings, tags=tags,
        )
        result = service.create_mapping(req)
        import json
        return json.dumps(result.model_dump(), indent=2, default=str)

    @mcp_server.tool(description="List mapping templates with optional format filters")
    async def list_mapping_templates(
        source_format: Optional[str] = None,
        target_format: Optional[str] = None,
        limit: int = 50,
    ) -> str:
        """List mapping templates."""
        results = service.list_mappings(source_format, target_format, limit)
        import json
        return json.dumps([r.model_dump() for r in results], indent=2, default=str)

    # ── Validation Tools ──────────────────────────────────────────────

    @mcp_server.tool(description="Validate data for import or export")
    async def validate_data(
        job_type: str = "import",
        job_id: str = "default",
    ) -> str:
        """Validate data."""
        req = ValidationRequest(job_type=job_type, job_id=job_id)
        result = service.validate(req)
        import json
        return json.dumps(result.model_dump(), indent=2, default=str)

    # ── Transformation Rule Tools ─────────────────────────────────────

    @mcp_server.tool(description="Create a data transformation rule")
    async def create_transform_rule(
        name: str,
        rule_type: str,
        source_column: Optional[str] = None,
        target_column: Optional[str] = None,
        expression: Optional[str] = None,
        description: Optional[str] = None,
        error_handling: str = "skip",
        priority: int = 100,
    ) -> str:
        """Create a transform rule."""
        req = TransformationRuleCreate(
            name=name, rule_type=rule_type, source_column=source_column,
            target_column=target_column, expression=expression,
            description=description, error_handling=error_handling,
            priority=priority,
        )
        result = service.create_transform_rule(req)
        import json
        return json.dumps(result.model_dump(), indent=2, default=str)

    @mcp_server.tool(description="List transformation rules")
    async def list_transform_rules(
        rule_type: Optional[str] = None,
        is_active: Optional[bool] = None,
        limit: int = 50,
    ) -> str:
        """List transform rules."""
        results = service.list_transform_rules(rule_type, is_active, limit)
        import json
        return json.dumps([r.model_dump() for r in results], indent=2, default=str)

    # ── History & Dashboard Tools ─────────────────────────────────────

    @mcp_server.tool(description="List transfer history records")
    async def list_transfer_history(
        direction: Optional[str] = None,
        connection_id: Optional[str] = None,
        limit: int = 50,
    ) -> str:
        """List transfer history."""
        results = service.list_transfer_history(direction, connection_id, limit)
        import json
        return json.dumps([r.model_dump() for r in results], indent=2, default=str)

    @mcp_server.tool(description="Get the data exchange dashboard summary")
    async def get_data_exchange_dashboard() -> str:
        """Get data exchange dashboard."""
        result = service.get_dashboard()
        import json
        return json.dumps(result.model_dump(), indent=2, default=str)

    @mcp_server.tool(description="List data exchange audit log entries")
    async def list_exchange_audit_logs(
        action: Optional[str] = None,
        target_type: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 50,
    ) -> str:
        """List exchange audit logs."""
        results = service.list_audit_logs(action, target_type, severity, limit)
        import json
        return json.dumps([r.model_dump() for r in results], indent=2, default=str)
