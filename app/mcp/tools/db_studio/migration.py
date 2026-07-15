"""MCP tools for Migration & Schema Versioning (UDS Module 13)."""

import logging
from typing import Any, Dict, List, Optional

from common_lib.modules.db_studio.migration import (
    MigrationService,
    SchemaVersionCreate,
    MigrationCreate, MigrationValidateRequest, MigrationApplyRequest,
    DriftDetectRequest,
    DeploymentCreate, DeploymentApproveRequest,
    RollbackRequest,
)

logger = logging.getLogger(__name__)
service = MigrationService()


def register_migration_tools(mcp_server):
    """Register all migration and schema versioning MCP tools."""

    # ── Schema Version Tools ─────────────────────────────────────────

    @mcp_server.tool(description="Create a schema version snapshot marking a new schema version")
    async def create_schema_version(
        connection_id: str,
        version: str,
        engine: str = "postgresql",
        database_name: Optional[str] = None,
        previous_version: Optional[str] = None,
        description: Optional[str] = None,
        is_baseline: bool = False,
        branch: str = "main",
        tags: Optional[List[str]] = None,
    ) -> str:
        """Create a schema version."""
        req = SchemaVersionCreate(
            connection_id=connection_id, version=version, engine=engine,
            database_name=database_name, previous_version=previous_version,
            description=description, is_baseline=is_baseline,
            branch=branch, tags=tags,
        )
        result = service.create_version(req)
        import json
        return json.dumps(result.model_dump(), indent=2, default=str)

    @mcp_server.tool(description="List schema versions with optional filters")
    async def list_schema_versions(
        connection_id: Optional[str] = None,
        branch: Optional[str] = None,
        limit: int = 50,
    ) -> str:
        """List schema versions."""
        results = service.list_versions(connection_id, branch, limit)
        import json
        return json.dumps([r.model_dump() for r in results], indent=2, default=str)

    # ── Migration Tools ──────────────────────────────────────────────

    @mcp_server.tool(description="Create a new database migration script")
    async def create_migration(
        connection_id: str,
        name: str,
        version: str,
        up_sql: str,
        engine: str = "postgresql",
        description: Optional[str] = None,
        migration_type: str = "standard",
        down_sql: Optional[str] = None,
        is_destructive: bool = False,
        dependencies: Optional[List[str]] = None,
    ) -> str:
        """Create a migration."""
        req = MigrationCreate(
            connection_id=connection_id, name=name, version=version,
            up_sql=up_sql, engine=engine, description=description,
            migration_type=migration_type, down_sql=down_sql,
            is_destructive=is_destructive, dependencies=dependencies,
        )
        result = service.create_migration(req)
        import json
        return json.dumps(result.model_dump(), indent=2, default=str)

    @mcp_server.tool(description="List migrations with optional filters")
    async def list_migrations(
        connection_id: Optional[str] = None,
        status: Optional[str] = None,
        migration_type: Optional[str] = None,
        limit: int = 50,
    ) -> str:
        """List migrations."""
        results = service.list_migrations(connection_id, status, migration_type, limit)
        import json
        return json.dumps([r.model_dump() for r in results], indent=2, default=str)

    @mcp_server.tool(description="Get a specific migration by ID")
    async def get_migration(migration_id: str) -> Optional[str]:
        """Get a migration."""
        result = service.get_migration(migration_id)
        if not result:
            return None
        import json
        return json.dumps(result.model_dump(), indent=2, default=str)

    @mcp_server.tool(description="Validate a migration script for syntax, dependencies, and destructive changes")
    async def validate_migration(migration_id: str) -> str:
        """Validate a migration."""
        req = MigrationValidateRequest(migration_id=migration_id)
        result = service.validate_migration(req)
        import json
        return json.dumps(result.model_dump(), indent=2, default=str)

    @mcp_server.tool(description="Apply a migration (optionally as a dry run)")
    async def apply_migration(migration_id: str, dry_run: bool = False) -> str:
        """Apply a migration."""
        req = MigrationApplyRequest(migration_id=migration_id, dry_run=dry_run)
        result = service.apply_migration(req)
        import json
        return json.dumps(result.model_dump(), indent=2, default=str)

    @mcp_server.tool(description="List migration execution history")
    async def list_migration_history(
        connection_id: Optional[str] = None,
        migration_id: Optional[str] = None,
        limit: int = 50,
    ) -> str:
        """List migration history."""
        results = service.list_migration_history(connection_id, migration_id, limit)
        import json
        return json.dumps([r.model_dump() for r in results], indent=2, default=str)

    # ── Drift Detection Tools ────────────────────────────────────────

    @mcp_server.tool(description="Detect schema drift by comparing expected vs actual schema")
    async def detect_drift(
        connection_id: str,
        engine: str = "postgresql",
        environment: str = "production",
        baseline_version: Optional[str] = None,
    ) -> str:
        """Detect schema drift."""
        req = DriftDetectRequest(
            connection_id=connection_id, engine=engine,
            environment=environment, baseline_version=baseline_version,
        )
        result = service.detect_drift(req)
        import json
        return json.dumps(result.model_dump(), indent=2, default=str)

    @mcp_server.tool(description="List drift detection reports with optional filters")
    async def list_drift_reports(
        connection_id: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 50,
    ) -> str:
        """List drift reports."""
        results = service.list_drift_reports(connection_id, severity, limit)
        import json
        return json.dumps([r.model_dump() for r in results], indent=2, default=str)

    # ── Deployment Tools ─────────────────────────────────────────────

    @mcp_server.tool(description="Create a deployment plan with ordered migrations")
    async def create_deployment(
        name: str,
        migration_ids: List[str],
        engine: str = "postgresql",
        environment: str = "development",
        approval_required: bool = False,
    ) -> str:
        """Create a deployment."""
        req = DeploymentCreate(
            name=name, migration_ids=migration_ids, engine=engine,
            environment=environment, approval_required=approval_required,
        )
        result = service.create_deployment(req)
        import json
        return json.dumps(result.model_dump(), indent=2, default=str)

    @mcp_server.tool(description="Execute a pending deployment run")
    async def execute_deployment(deployment_id: str) -> str:
        """Execute a deployment."""
        result = service.execute_deployment(deployment_id)
        import json
        return json.dumps(result.model_dump(), indent=2, default=str)

    @mcp_server.tool(description="Approve a deployment for execution")
    async def approve_deployment(deployment_id: str, approved_by: str = "admin") -> Optional[str]:
        """Approve a deployment."""
        req = DeploymentApproveRequest(deployment_id=deployment_id, approved_by=approved_by)
        result = service.approve_deployment(req)
        if not result:
            return None
        import json
        return json.dumps(result.model_dump(), indent=2, default=str)

    @mcp_server.tool(description="List deployment runs")
    async def list_deployments(
        environment: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> str:
        """List deployments."""
        results = service.list_deployments(environment, status, limit)
        import json
        return json.dumps([r.model_dump() for r in results], indent=2, default=str)

    # ── Rollback Tools ───────────────────────────────────────────────

    @mcp_server.tool(description="Rollback a previously applied migration")
    async def rollback_migration(
        migration_id: str,
        reason: Optional[str] = None,
        rollback_type: str = "manual",
    ) -> str:
        """Rollback a migration."""
        req = RollbackRequest(migration_id=migration_id, reason=reason, rollback_type=rollback_type)
        result = service.rollback_migration(req)
        import json
        return json.dumps(result.model_dump(), indent=2, default=str)

    @mcp_server.tool(description="List rollback history")
    async def list_rollbacks(migration_id: Optional[str] = None, limit: int = 50) -> str:
        """List rollback history."""
        results = service.list_rollbacks(migration_id, limit)
        import json
        return json.dumps([r.model_dump() for r in results], indent=2, default=str)

    # ── Dashboard & Audit Tools ──────────────────────────────────────

    @mcp_server.tool(description="Get the migration dashboard summary")
    async def get_migration_dashboard() -> str:
        """Get migration dashboard."""
        result = service.get_dashboard()
        import json
        return json.dumps(result.model_dump(), indent=2, default=str)

    @mcp_server.tool(description="List migration audit log entries")
    async def list_migration_audit_logs(
        action: Optional[str] = None,
        target_type: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 50,
    ) -> str:
        """List migration audit logs."""
        results = service.list_audit_logs(action, target_type, severity, limit)
        import json
        return json.dumps([r.model_dump() for r in results], indent=2, default=str)
