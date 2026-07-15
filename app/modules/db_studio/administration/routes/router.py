"""Thin API routes for Database Administration Center (UDS Module 10)."""

from fastapi import APIRouter, HTTPException
from typing import List, Optional

from common_lib.modules.db_studio.administration.service import AdminCenterService
from common_lib.modules.db_studio.administration.schemas import (
    UserCreate, UserUpdate, UserOut,
    RoleCreate, RoleGrant, RoleOut, EffectivePermissionOut,
    SessionOut, SessionKillRequest,
    LockOut, DeadlockInfo,
    MaintenanceRequest, MaintenanceOut,
    ReplicationStatus, ReplicationTopology,
    ConfigParam, ExtensionInfo, ServerInfo,
    StorageUsage, TablespaceInfo,
    JobCreate, JobOut,
    AuditOut,
)

svc = AdminCenterService()


def get_router() -> APIRouter:
    router = APIRouter(prefix="/api/v1/admin", tags=["Database Administration"])

    # ── Users ──────────────────────────────────────────────────────────

    @router.post("/users", response_model=UserOut, status_code=201)
    def create_user(req: UserCreate):
        return svc.create_user(req)

    @router.get("/users", response_model=List[UserOut])
    def list_users():
        return svc.list_users()

    @router.get("/users/{username}", response_model=UserOut)
    def get_user(username: str):
        r = svc.get_user(username)
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
    def delete_user(username: str):
        if not svc.delete_user(username):
            raise HTTPException(404, "User not found")

    # ── Roles ──────────────────────────────────────────────────────────

    @router.post("/roles", response_model=RoleOut, status_code=201)
    def create_role(req: RoleCreate):
        return svc.create_role(req)

    @router.get("/roles", response_model=List[RoleOut])
    def list_roles():
        return svc.list_roles()

    @router.post("/roles/grant", response_model=dict)
    def grant_role(req: RoleGrant):
        svc.grant_role(req)
        return {"success": True, "message": f"Role '{req.role_name}' granted to '{req.target}'"}

    @router.post("/roles/revoke", response_model=dict)
    def revoke_role(role_name: str, target: str):
        svc.revoke_role(role_name, target)
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
        ok = svc.kill_session(SessionKillRequest(session_id=session_id, force=force, reason=reason))
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
    def list_jobs(status: Optional[str] = None, job_type: Optional[str] = None, limit: int = 20):
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
