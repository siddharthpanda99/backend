"""Thin API routes for Database Administration Center (UDS Module 10)."""

from fastapi import APIRouter, HTTPException
from typing import List, Optional

from common_lib.modules.db_studio.administration.service import AdminCenterService
from common_lib.modules.db_studio.administration.provisioning import (
    ProvisioningError,
    ProvisioningUnsupported,
)
from common_lib.modules.db_studio.administration.schemas import (
    UserCreate,
    UserUpdate,
    UserOut,
    RoleCreate,
    RoleGrant,
    RoleOut,
    EffectivePermissionOut,
    SessionOut,
    SessionKillRequest,
    LockOut,
    DeadlockInfo,
    MaintenanceRequest,
    MaintenanceOut,
    ReplicationStatus,
    ReplicationTopology,
    ConfigParam,
    ExtensionInfo,
    ServerInfo,
    StorageUsage,
    TablespaceInfo,
    JobCreate,
    JobOut,
    AuditOut,
    DatabaseCreate,
    DatabaseOut,
    ProvisionResult,
)

svc = AdminCenterService()


def _handle(fn):
    """Run a provisioning call, translating driver errors to HTTP codes."""
    try:
        return fn()
    except ProvisioningUnsupported as e:
        raise HTTPException(422, str(e))
    except ProvisioningError as e:
        raise HTTPException(400, str(e))
    except HTTPException:
        raise
    except Exception as e:  # noqa
        raise HTTPException(500, f"Provisioning failed: {e}")


def get_router() -> APIRouter:
    router = APIRouter(prefix="/api/v1/admin", tags=["Database Administration"])

    # ── Databases (real provisioning) ───────────────────────────────────

    @router.post("/databases", response_model=ProvisionResult, status_code=201)
    def create_database(req: DatabaseCreate):
        return _handle(lambda: svc.create_database(req))

    @router.get("/databases", response_model=List[DatabaseOut])
    def list_databases(connection_id: str):
        return _handle(lambda: svc.list_databases(connection_id))

    @router.delete("/databases/{name}", response_model=ProvisionResult)
    def drop_database(name: str, connection_id: str, confirm: bool = False):
        return _handle(lambda: svc.drop_database(connection_id, name, confirm))

    # ── Users ──────────────────────────────────────────────────────────

    @router.post("/users", response_model=UserOut, status_code=201)
    def create_user(req: UserCreate):
        return _handle(lambda: svc.create_user(req))

    @router.get("/users", response_model=List[UserOut])
    def list_users(connection_id: str):
        return _handle(lambda: svc.list_users(connection_id))

    @router.get("/users/{username}", response_model=UserOut)
    def get_user(username: str, connection_id: str):
        r = _handle(lambda: svc.get_user(username, connection_id))
        if not r:
            raise HTTPException(404, "User not found")
        return r

    @router.put("/users/{username}", response_model=UserOut)
    def update_user(username: str, req: UserUpdate):
        r = svc.update_user(username, req)
        if not r:
            raise HTTPException(404, "User not found")
        return r

    @router.delete("/users/{username}", status_code=204)
    def delete_user(username: str, connection_id: str, confirm: bool = False):
        _handle(lambda: svc.delete_user(username, connection_id, confirm))

    # ── Roles ──────────────────────────────────────────────────────────

    @router.post("/roles", response_model=RoleOut, status_code=201)
    def create_role(req: RoleCreate):
        return _handle(lambda: svc.create_role(req))

    @router.get("/roles", response_model=List[RoleOut])
    def list_roles():
        return svc.list_roles()

    @router.post("/roles/grant", response_model=dict)
    def grant_role(req: RoleGrant):
        _handle(lambda: svc.grant_role(req))
        return {
            "success": True,
            "message": f"Role '{req.role_name}' granted to '{req.target}'",
        }

    @router.post("/roles/revoke", response_model=dict)
    def revoke_role(
        role_name: str, target: str, connection_id: str, database: Optional[str] = None
    ):
        _handle(lambda: svc.revoke_role(role_name, target, connection_id, database))
        return {"success": True}

    @router.get("/roles/permissions/{username}", response_model=EffectivePermissionOut)
    def get_effective_permissions(username: str):
        return svc.get_effective_permissions(username)

    # ── Sessions ───────────────────────────────────────────────────────

    @router.get("/sessions", response_model=List[SessionOut])
    def list_sessions():
        return svc.list_sessions()

    @router.get("/sessions/{session_id}", response_model=SessionOut)
    def get_session(session_id: str):
        r = svc.get_session(session_id)
        if not r:
            raise HTTPException(404, "Session not found")
        return r

    @router.post("/sessions/{session_id}/kill", response_model=dict)
    def kill_session(session_id: str, force: bool = False, reason: str = None):
        ok = svc.kill_session(
            SessionKillRequest(session_id=session_id, force=force, reason=reason)
        )
        return {"success": ok, "message": f"Session {session_id} terminated"}

    # ── Locks ──────────────────────────────────────────────────────────

    @router.get("/locks", response_model=List[LockOut])
    def list_locks():
        return svc.list_locks()

    @router.get("/locks/deadlocks", response_model=DeadlockInfo)
    def detect_deadlocks():
        return svc.detect_deadlocks()

    @router.post("/locks/unlock/{pid}", response_model=dict)
    def force_unlock(pid: int):
        ok = svc.force_unlock(pid)
        return {"success": ok}

    # ── Maintenance ────────────────────────────────────────────────────

    @router.post("/maintenance/run", response_model=MaintenanceOut)
    def run_maintenance(req: MaintenanceRequest):
        return svc.run_maintenance(req)

    @router.get("/maintenance/history", response_model=List[MaintenanceOut])
    def list_maintenance_history(
        connection_id: Optional[str] = None,
        operation: Optional[str] = None,
        limit: int = 20,
    ):
        return svc.list_maintenance_history(connection_id, operation, limit)

    # ── Replication ────────────────────────────────────────────────────

    @router.get("/replication", response_model=ReplicationTopology)
    def get_replication_status():
        return svc.get_replication_status()

    @router.get("/replication/lag", response_model=ReplicationStatus)
    def get_replication_lag():
        return svc.get_replication_lag()

    # ── Configuration ──────────────────────────────────────────────────

    @router.get("/config", response_model=ServerInfo)
    def get_server_info():
        return svc.get_server_info()

    @router.get("/config/params", response_model=List[ConfigParam])
    def list_config_params(category: Optional[str] = None):
        return svc.list_config_params(category)

    @router.get("/config/extensions", response_model=List[ExtensionInfo])
    def list_extensions():
        return svc.list_extensions()

    @router.get("/config/real", response_model=List[ConfigParam])
    def get_real_config(connection_id: Optional[str] = None):
        """Query real pg_settings from a target connection or platform DB."""
        return svc.get_real_config(connection_id)

    @router.get("/config/extensions/real", response_model=List[ExtensionInfo])
    def get_real_extensions(connection_id: Optional[str] = None):
        """Query real pg_extension from a target connection or platform DB."""
        return svc.get_real_extensions(connection_id)

    @router.get("/roles/real", response_model=List[RoleOut])
    def get_real_roles(connection_id: Optional[str] = None):
        """Query real pg_roles from a target connection or platform DB."""
        return svc.get_real_roles(connection_id)

    # ── Dashboard Metrics (Phase 3) ─────────────────────────────────

    @router.get("/dashboard/metrics")
    def get_dashboard_metrics(connection_id: Optional[str] = None):
        """Query real dashboard metrics: DB size, connections, cache hit, tuples, TPS."""
        from typing import Any, Dict
        return svc.get_dashboard_metrics(connection_id)

    # ── Storage ────────────────────────────────────────────────────────

    @router.get("/storage", response_model=List[StorageUsage])
    def get_storage_usage():
        return svc.get_storage_usage()

    @router.get("/storage/tablespaces", response_model=List[TablespaceInfo])
    def list_tablespaces():
        return svc.list_tablespaces()

    # ── Jobs ───────────────────────────────────────────────────────────

    @router.post("/jobs", response_model=JobOut, status_code=201)
    def create_job(req: JobCreate):
        return svc.create_job(req)

    @router.get("/jobs", response_model=List[JobOut])
    def list_jobs(
        status: Optional[str] = None, job_type: Optional[str] = None, limit: int = 20
    ):
        return svc.list_jobs(status, job_type, limit)

    @router.get("/jobs/{job_id}", response_model=JobOut)
    def get_job(job_id: str):
        r = svc.get_job(job_id)
        if not r:
            raise HTTPException(404, "Job not found")
        return r

    @router.post("/jobs/{job_id}/cancel", response_model=dict)
    def cancel_job(job_id: str):
        ok = svc.cancel_job(job_id)
        if not ok:
            raise HTTPException(400, "Job cannot be cancelled or not found")
        return {"success": True, "message": f"Job {job_id} cancelled"}

    # ── Audit ──────────────────────────────────────────────────────────

    @router.get("/audit", response_model=List[AuditOut])
    def list_audit_logs(
        action: Optional[str] = None,
        target_type: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ):
        return svc.list_audit_logs(action, target_type, severity, limit, offset)

    return router
