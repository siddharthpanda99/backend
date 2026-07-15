"""MCP tools for Backup, Restore & Snapshot Manager (UDS Module 12)."""

import logging
from typing import Any, Dict, List, Optional

from common_lib.modules.db_studio.backup import (
    BackupRestoreService,
    BackupRunRequest, BackupValidateRequest,
    RestoreRunRequest,
    SnapshotCreateRequest,
    RetentionPolicyCreate,
    RecoveryTestRequest,
)

logger = logging.getLogger(__name__)
service = BackupRestoreService()


def register_backup_tools(mcp_server):
    """Register all backup, restore, and snapshot MCP tools."""

    # ── Backup Tools ──────────────────────────────────────────────────

    @mcp_server.tool(description="Run a database backup operation (full, incremental, differential, logical, or physical)")
    async def run_backup(
        connection_id: str,
        engine: str = "postgresql",
        database_name: Optional[str] = None,
        backup_type: str = "full",
        backup_mode: str = "online",
        compression_type: Optional[str] = "gzip",
        encryption_type: Optional[str] = None,
        storage_tier: str = "local",
        retention_days: Optional[int] = None,
    ) -> str:
        """Run a backup operation."""
        req = BackupRunRequest(
            connection_id=connection_id, engine=engine, database_name=database_name,
            backup_type=backup_type, backup_mode=backup_mode,
            compression_type=compression_type, encryption_type=encryption_type,
            storage_tier=storage_tier, retention_days=retention_days,
        )
        result = service.run_backup(req)
        import json
        return json.dumps(result.model_dump(), indent=2, default=str)

    @mcp_server.tool(description="List backup jobs with optional filters")
    async def list_backups(
        connection_id: Optional[str] = None,
        status: Optional[str] = None,
        backup_type: Optional[str] = None,
        limit: int = 50,
    ) -> str:
        """List backup jobs."""
        results = service.list_backups(connection_id, status, backup_type, limit)
        import json
        return json.dumps([r.model_dump() for r in results], indent=2, default=str)

    @mcp_server.tool(description="Get a specific backup job by ID")
    async def get_backup(backup_id: str) -> Optional[str]:
        """Get a backup job."""
        result = service.get_backup(backup_id)
        if not result:
            return None
        import json
        return json.dumps(result.model_dump(), indent=2, default=str)

    @mcp_server.tool(description="Validate a backup for integrity and restore readiness")
    async def validate_backup(backup_id: str, deep_check: bool = False) -> str:
        """Validate a backup."""
        req = BackupValidateRequest(backup_id=backup_id, deep_check=deep_check)
        result = service.validate_backup(req)
        import json
        return json.dumps(result.model_dump(), indent=2, default=str)

    # ── Restore Tools ─────────────────────────────────────────────────

    @mcp_server.tool(description="Run a restore operation (full, point_in_time, object_level, or selective)")
    async def run_restore(
        connection_id: str,
        engine: str = "postgresql",
        target_database: Optional[str] = None,
        source_backup_id: Optional[str] = None,
        source_snapshot_id: Optional[str] = None,
        restore_type: str = "full",
        restore_mode: str = "online",
        pitr_timestamp: Optional[str] = None,
        dry_run: bool = False,
        validate_before: bool = True,
        overwrite_existing: bool = False,
    ) -> str:
        """Run a restore operation."""
        req = RestoreRunRequest(
            connection_id=connection_id, engine=engine, target_database=target_database,
            source_backup_id=source_backup_id, source_snapshot_id=source_snapshot_id,
            restore_type=restore_type, restore_mode=restore_mode,
            pitr_timestamp=pitr_timestamp, dry_run=dry_run,
            validate_before=validate_before, overwrite_existing=overwrite_existing,
        )
        result = service.run_restore(req)
        import json
        return json.dumps(result.model_dump(), indent=2, default=str)

    @mcp_server.tool(description="List restore jobs")
    async def list_restores(
        connection_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> str:
        """List restore jobs."""
        results = service.list_restores(connection_id, status, limit)
        import json
        return json.dumps([r.model_dump() for r in results], indent=2, default=str)

    # ── Snapshot Tools ────────────────────────────────────────────────

    @mcp_server.tool(description="Create a database snapshot (manual, scheduled, or automated)")
    async def create_snapshot(
        connection_id: str,
        snapshot_name: str,
        engine: str = "postgresql",
        database_name: Optional[str] = None,
        snapshot_type: str = "manual",
        is_immutable: bool = False,
        is_incremental: bool = False,
        parent_snapshot_id: Optional[str] = None,
        retention_until: Optional[str] = None,
        tags: Optional[List[str]] = None,
        description: Optional[str] = None,
    ) -> str:
        """Create a snapshot."""
        req = SnapshotCreateRequest(
            connection_id=connection_id, snapshot_name=snapshot_name, engine=engine,
            database_name=database_name, snapshot_type=snapshot_type,
            is_immutable=is_immutable, is_incremental=is_incremental,
            parent_snapshot_id=parent_snapshot_id, retention_until=retention_until,
            tags=tags, description=description,
        )
        result = service.create_snapshot(req)
        import json
        return json.dumps(result.model_dump(), indent=2, default=str)

    @mcp_server.tool(description="List snapshots with optional filters")
    async def list_snapshots(
        connection_id: Optional[str] = None,
        engine: Optional[str] = None,
        limit: int = 50,
    ) -> str:
        """List snapshots."""
        results = service.list_snapshots(connection_id, engine, limit)
        import json
        return json.dumps([r.model_dump() for r in results], indent=2, default=str)

    @mcp_server.tool(description="Get a specific snapshot by ID")
    async def get_snapshot(snapshot_id: str) -> Optional[str]:
        """Get a snapshot."""
        result = service.get_snapshot(snapshot_id)
        if not result:
            return None
        import json
        return json.dumps(result.model_dump(), indent=2, default=str)

    @mcp_server.tool(description="Delete (soft) a snapshot")
    async def delete_snapshot(snapshot_id: str) -> str:
        """Delete a snapshot."""
        result = service.delete_snapshot(snapshot_id)
        return f"Snapshot {'deleted' if result else 'not found'}"

    @mcp_server.tool(description="Compare two snapshots and show differences")
    async def compare_snapshots(snapshot_a_id: str, snapshot_b_id: str) -> str:
        """Compare two snapshots."""
        result = service.compare_snapshots(snapshot_a_id, snapshot_b_id)
        import json
        return json.dumps(result.model_dump(), indent=2, default=str)

    # ── Retention Policy Tools ────────────────────────────────────────

    @mcp_server.tool(description="Create a retention policy for backups and snapshots")
    async def create_retention_policy(
        name: str,
        retention_days: int = 30,
        engine: Optional[str] = None,
        connection_id: Optional[str] = None,
        description: Optional[str] = None,
        max_backups: Optional[int] = None,
        min_backups: int = 1,
        encryption_required: bool = True,
        compression_required: bool = True,
        verification_required: bool = True,
        schedule_cron: Optional[str] = None,
        priority: int = 100,
    ) -> str:
        """Create a retention policy."""
        req = RetentionPolicyCreate(
            name=name, retention_days=retention_days, engine=engine,
            connection_id=connection_id, description=description,
            max_backups=max_backups, min_backups=min_backups,
            encryption_required=encryption_required,
            compression_required=compression_required,
            verification_required=verification_required,
            schedule_cron=schedule_cron, priority=priority,
        )
        result = service.create_retention_policy(req)
        import json
        return json.dumps(result.model_dump(), indent=2, default=str)

    @mcp_server.tool(description="List retention policies")
    async def list_retention_policies(is_active: Optional[bool] = None, limit: int = 50) -> str:
        """List retention policies."""
        results = service.list_retention_policies(is_active, limit)
        import json
        return json.dumps([r.model_dump() for r in results], indent=2, default=str)

    # ── Disaster Recovery Tools ───────────────────────────────────────

    @mcp_server.tool(description="Run a disaster recovery test (backup_validation, restore_drill, failover_test, cross_region)")
    async def run_recovery_test(
        connection_id: str,
        test_name: str,
        engine: str = "postgresql",
        test_type: str = "restore_drill",
        backup_id: Optional[str] = None,
        dr_plan_name: Optional[str] = None,
        region_source: Optional[str] = None,
        region_target: Optional[str] = None,
        is_scheduled: bool = False,
    ) -> str:
        """Run a recovery test."""
        req = RecoveryTestRequest(
            connection_id=connection_id, test_name=test_name, engine=engine,
            test_type=test_type, backup_id=backup_id, dr_plan_name=dr_plan_name,
            region_source=region_source, region_target=region_target,
            is_scheduled=is_scheduled,
        )
        result = service.run_recovery_test(req)
        import json
        return json.dumps(result.model_dump(), indent=2, default=str)

    @mcp_server.tool(description="List disaster recovery test results")
    async def list_recovery_tests(
        connection_id: Optional[str] = None,
        limit: int = 50,
    ) -> str:
        """List recovery tests."""
        results = service.list_recovery_tests(connection_id, limit)
        import json
        return json.dumps([r.model_dump() for r in results], indent=2, default=str)

    # ── Dashboard Tools ───────────────────────────────────────────────

    @mcp_server.tool(description="Get the backup dashboard summary")
    async def get_backup_dashboard() -> str:
        """Get backup dashboard."""
        result = service.get_dashboard()
        import json
        return json.dumps(result.model_dump(), indent=2, default=str)

    # ── Audit Tools ───────────────────────────────────────────────────

    @mcp_server.tool(description="List backup audit log entries")
    async def list_backup_audit_logs(
        action: Optional[str] = None,
        target_type: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 50,
    ) -> str:
        """List backup audit logs."""
        results = service.list_audit_logs(action, target_type, severity, limit)
        import json
        return json.dumps([r.model_dump() for r in results], indent=2, default=str)
