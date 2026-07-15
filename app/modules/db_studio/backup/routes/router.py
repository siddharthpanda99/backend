"""Thin backend route wrappers for Backup, Restore & Snapshot Manager (UDS Module 12)."""

from fastapi import APIRouter, HTTPException

from common_lib.modules.db_studio.backup import (
    BackupRestoreService,
    BackupRunRequest, BackupOut, BackupArtifactOut,
    BackupValidateRequest, BackupValidationOut,
    RestoreRunRequest, RestoreOut,
    SnapshotCreateRequest, SnapshotOut, SnapshotCompareOut,
    RetentionPolicyCreate, RetentionPolicyOut,
    RecoveryTestRequest, RecoveryTestOut,
    BackupDashboardOut, BackupAuditOut,
)

service = BackupRestoreService()


def get_router() -> APIRouter:
    router = APIRouter(prefix="/api/v1/backup", tags=["Backup, Restore & Snapshot"])

    # ── Dashboard ────────────────────────────────────────────────────

    @router.get("/dashboard", response_model=BackupDashboardOut)
    async def get_dashboard():
        return service.get_dashboard()

    # ── Backup ────────────────────────────────────────────────────

    @router.post("/run", response_model=BackupOut)
    async def run_backup(req: BackupRunRequest):
        return service.run_backup(req)

    @router.get("/jobs", response_model=list[BackupOut])
    async def list_backups(
        connection_id: str = None, status: str = None,
        backup_type: str = None, limit: int = 50,
    ):
        return service.list_backups(connection_id, status, backup_type, limit)

    @router.get("/jobs/{backup_id}", response_model=BackupOut)
    async def get_backup(backup_id: str):
        result = service.get_backup(backup_id)
        if not result:
            raise HTTPException(status_code=404, detail="Backup not found")
        return result

    @router.post("/validate", response_model=BackupValidationOut)
    async def validate_backup(req: BackupValidateRequest):
        return service.validate_backup(req)

    # ── Restore ──────────────────────────────────────────────────

    @router.post("/restore/run", response_model=RestoreOut)
    async def run_restore(req: RestoreRunRequest):
        return service.run_restore(req)

    @router.get("/restore/jobs", response_model=list[RestoreOut])
    async def list_restores(connection_id: str = None, status: str = None, limit: int = 50):
        return service.list_restores(connection_id, status, limit)

    @router.get("/restore/jobs/{restore_id}", response_model=RestoreOut)
    async def get_restore(restore_id: str):
        result = service.get_restore(restore_id)
        if not result:
            raise HTTPException(status_code=404, detail="Restore job not found")
        return result

    # ── Snapshots ────────────────────────────────────────────────

    @router.post("/snapshots", response_model=SnapshotOut)
    async def create_snapshot(req: SnapshotCreateRequest):
        return service.create_snapshot(req)

    @router.get("/snapshots", response_model=list[SnapshotOut])
    async def list_snapshots(connection_id: str = None, engine: str = None, limit: int = 50):
        return service.list_snapshots(connection_id, engine, limit)

    @router.get("/snapshots/{snapshot_id}", response_model=SnapshotOut)
    async def get_snapshot(snapshot_id: str):
        result = service.get_snapshot(snapshot_id)
        if not result:
            raise HTTPException(status_code=404, detail="Snapshot not found")
        return result

    @router.delete("/snapshots/{snapshot_id}")
    async def delete_snapshot(snapshot_id: str):
        result = service.delete_snapshot(snapshot_id)
        if not result:
            raise HTTPException(status_code=404, detail="Snapshot not found")
        return {"ok": True}

    @router.get("/snapshots/compare", response_model=SnapshotCompareOut)
    async def compare_snapshots(snapshot_a_id: str, snapshot_b_id: str):
        return service.compare_snapshots(snapshot_a_id, snapshot_b_id)

    # ── Retention Policies ──────────────────────────────────────

    @router.post("/policies", response_model=RetentionPolicyOut)
    async def create_policy(req: RetentionPolicyCreate):
        return service.create_retention_policy(req)

    @router.get("/policies", response_model=list[RetentionPolicyOut])
    async def list_policies(is_active: bool = None, limit: int = 50):
        return service.list_retention_policies(is_active, limit)

    @router.put("/policies/{policy_id}", response_model=RetentionPolicyOut)
    async def update_policy(policy_id: str, req: RetentionPolicyCreate):
        result = service.update_retention_policy(policy_id, req)
        if not result:
            raise HTTPException(status_code=404, detail="Policy not found")
        return result

    @router.delete("/policies/{policy_id}")
    async def delete_policy(policy_id: str):
        result = service.delete_retention_policy(policy_id)
        if not result:
            raise HTTPException(status_code=404, detail="Policy not found")
        return {"ok": True}

    # ── Disaster Recovery ───────────────────────────────────────

    @router.post("/recovery/test", response_model=RecoveryTestOut)
    async def run_recovery_test(req: RecoveryTestRequest):
        return service.run_recovery_test(req)

    @router.get("/recovery/tests", response_model=list[RecoveryTestOut])
    async def list_recovery_tests(connection_id: str = None, limit: int = 50):
        return service.list_recovery_tests(connection_id, limit)

    # ── Audit ───────────────────────────────────────────────────

    @router.get("/audit", response_model=list[BackupAuditOut])
    async def list_audit_logs(
        action: str = None, target_type: str = None,
        severity: str = None, limit: int = 50,
    ):
        return service.list_audit_logs(action, target_type, severity, limit)

    return router
