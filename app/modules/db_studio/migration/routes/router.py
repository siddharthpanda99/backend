"""Thin backend route wrappers for Migration & Schema Versioning (UDS Module 13)."""

from fastapi import APIRouter, HTTPException

from common_lib.modules.db_studio.migration import (
    MigrationService,
    SchemaVersionCreate, SchemaVersionOut,
    MigrationCreate, MigrationOut, MigrationValidateRequest, MigrationValidationOut,
    MigrationApplyRequest, MigrationExecOut,
    DriftDetectRequest, DriftReportOut,
    DeploymentCreate, DeploymentOut, DeploymentApproveRequest,
    RollbackRequest, RollbackOut,
    MigrationDashboardOut, MigrationAuditOut,
)

service = MigrationService()


def get_router() -> APIRouter:
    router = APIRouter(prefix="/api/v1/migrations", tags=["Migration & Schema Versioning"])

    # ── Dashboard ────────────────────────────────────────────────────

    @router.get("/dashboard", response_model=MigrationDashboardOut)
    async def get_dashboard():
        return service.get_dashboard()

    # ── Schema Versions ──────────────────────────────────────────────

    @router.post("/versions", response_model=SchemaVersionOut)
    async def create_version(req: SchemaVersionCreate):
        return service.create_version(req)

    @router.get("/versions", response_model=list[SchemaVersionOut])
    async def list_versions(connection_id: str = None, branch: str = None, limit: int = 50):
        return service.list_versions(connection_id, branch, limit)

    @router.get("/versions/{version_id}", response_model=SchemaVersionOut)
    async def get_version(version_id: str):
        result = service.get_version(version_id)
        if not result:
            raise HTTPException(status_code=404, detail="Version not found")
        return result

    # ── Migrations ───────────────────────────────────────────────────

    @router.post("", response_model=MigrationOut)
    async def create_migration(req: MigrationCreate):
        return service.create_migration(req)

    @router.get("", response_model=list[MigrationOut])
    async def list_migrations(
        connection_id: str = None, status: str = None,
        migration_type: str = None, limit: int = 50,
    ):
        return service.list_migrations(connection_id, status, migration_type, limit)

    @router.get("/{migration_id}", response_model=MigrationOut)
    async def get_migration(migration_id: str):
        result = service.get_migration(migration_id)
        if not result:
            raise HTTPException(status_code=404, detail="Migration not found")
        return result

    @router.post("/validate", response_model=MigrationValidationOut)
    async def validate_migration(req: MigrationValidateRequest):
        return service.validate_migration(req)

    @router.post("/apply", response_model=MigrationExecOut)
    async def apply_migration(req: MigrationApplyRequest):
        return service.apply_migration(req)

    @router.get("/history", response_model=list[MigrationExecOut])
    async def list_migration_history(
        connection_id: str = None, migration_id: str = None, limit: int = 50,
    ):
        return service.list_migration_history(connection_id, migration_id, limit)

    # ── Drift Detection ──────────────────────────────────────────────

    @router.post("/drift", response_model=DriftReportOut)
    async def detect_drift(req: DriftDetectRequest):
        return service.detect_drift(req)

    @router.get("/drift", response_model=list[DriftReportOut])
    async def list_drift_reports(
        connection_id: str = None, severity: str = None, limit: int = 50,
    ):
        return service.list_drift_reports(connection_id, severity, limit)

    # ── Deployments ──────────────────────────────────────────────────

    @router.post("/deployments", response_model=DeploymentOut)
    async def create_deployment(req: DeploymentCreate):
        return service.create_deployment(req)

    @router.get("/deployments", response_model=list[DeploymentOut])
    async def list_deployments(environment: str = None, status: str = None, limit: int = 50):
        return service.list_deployments(environment, status, limit)

    @router.post("/deployments/{deployment_id}/execute", response_model=DeploymentOut)
    async def execute_deployment(deployment_id: str):
        return service.execute_deployment(deployment_id)

    @router.post("/deployments/approve", response_model=DeploymentOut)
    async def approve_deployment(req: DeploymentApproveRequest):
        result = service.approve_deployment(req)
        if not result:
            raise HTTPException(status_code=404, detail="Deployment not found")
        return result

    # ── Rollback ─────────────────────────────────────────────────────

    @router.post("/rollback", response_model=RollbackOut)
    async def rollback_migration(req: RollbackRequest):
        return service.rollback_migration(req)

    @router.get("/rollbacks", response_model=list[RollbackOut])
    async def list_rollbacks(migration_id: str = None, limit: int = 50):
        return service.list_rollbacks(migration_id, limit)

    # ── Audit ────────────────────────────────────────────────────────

    @router.get("/audit", response_model=list[MigrationAuditOut])
    async def list_audit_logs(
        action: str = None, target_type: str = None,
        severity: str = None, limit: int = 50,
    ):
        return service.list_audit_logs(action, target_type, severity, limit)

    return router
