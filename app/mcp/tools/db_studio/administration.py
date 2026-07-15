"""MCP agent-facing tools for Database Administration Center (UDS Module 10)."""

from typing import Any, Dict, List, Optional
from common_lib.modules.db_studio.administration.service import AdminCenterService
from common_lib.modules.db_studio.administration.schemas import (
    UserCreate, UserUpdate,
    RoleCreate, RoleGrant,
    SessionKillRequest,
    MaintenanceRequest,
    JobCreate,
)

svc = AdminCenterService()


def register_administration_tools(mcp_server: Any) -> None:
    """Register all Module 10 agent-facing tools."""

    # ── User Management ────────────────────────────────────────────────

    @mcp_server.tool(description="Create a new database user")
    def admin_create_user(username: str, role: Optional[str] = None) -> str:
        """Create a database user."""
        req = UserCreate(username=username, role=role)
        result = svc.create_user(req)
        return f"User '{result.username}' created (role={result.role})"

    @mcp_server.tool(description="List all database users")
    def admin_list_users() -> List[Dict[str, Any]]:
        """List database users."""
        return [u.model_dump() for u in svc.list_users()]

    @mcp_server.tool(description="Delete a database user")
    def admin_delete_user(username: str) -> str:
        """Delete a database user."""
        if svc.delete_user(username):
            return f"User '{username}' deleted"
        return f"User '{username}' not found"

    # ── Role Management ────────────────────────────────────────────────

    @mcp_server.tool(description="Create a new database role")
    def admin_create_role(name: str, description: Optional[str] = None) -> str:
        """Create a database role."""
        req = RoleCreate(name=name, description=description)
        result = svc.create_role(req)
        return f"Role '{result.name}' created"

    @mcp_server.tool(description="List all database roles")
    def admin_list_roles() -> List[Dict[str, Any]]:
        """List database roles."""
        return [r.model_dump() for r in svc.list_roles()]

    @mcp_server.tool(description="Grant a role to a user")
    def admin_grant_role(role_name: str, target: str) -> str:
        """Grant role to user."""
        req = RoleGrant(role_name=role_name, target=target)
        svc.grant_role(req)
        return f"Role '{role_name}' granted to '{target}'"

    @mcp_server.tool(description="Get effective permissions for a user")
    def admin_get_permissions(username: str) -> Dict[str, Any]:
        """Get effective permissions."""
        return svc.get_effective_permissions(username).model_dump()

    # ── Session Management ─────────────────────────────────────────────

    @mcp_server.tool(description="List active database sessions")
    def admin_list_sessions() -> List[Dict[str, Any]]:
        """List active database sessions."""
        return [s.model_dump() for s in svc.list_sessions()]

    @mcp_server.tool(description="Kill a database session")
    def admin_kill_session(session_id: str, force: bool = False) -> str:
        """Kill a database session."""
        req = SessionKillRequest(session_id=session_id, force=force)
        if svc.kill_session(req):
            return f"Session {session_id} terminated"
        return f"Session {session_id} not found"

    # ── Lock Management ────────────────────────────────────────────────

    @mcp_server.tool(description="List database locks")
    def admin_list_locks() -> List[Dict[str, Any]]:
        """List database locks."""
        return [l.model_dump() for l in svc.list_locks()]

    @mcp_server.tool(description="Detect database deadlocks")
    def admin_detect_deadlocks() -> Dict[str, Any]:
        """Detect deadlocks."""
        return svc.detect_deadlocks().model_dump()

    # ── Maintenance ────────────────────────────────────────────────────

    @mcp_server.tool(description="Run a maintenance operation (vacuum, analyze, reindex, etc.)")
    def admin_run_maintenance(operation: str, target: Optional[str] = None) -> str:
        """Run maintenance operation."""
        req = MaintenanceRequest(operation=operation, target=target)
        result = svc.run_maintenance(req)
        return f"Maintenance '{result.operation}' completed in {result.duration_ms}ms (target: {result.target or 'all'})"

    @mcp_server.tool(description="List maintenance history")
    def admin_list_maintenance_history(operation: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """List maintenance history."""
        return [m.model_dump() for m in svc.list_maintenance_history(operation=operation, limit=limit)]

    # ── Replication ────────────────────────────────────────────────────

    @mcp_server.tool(description="Get replication status and topology")
    def admin_get_replication_status() -> Dict[str, Any]:
        """Get replication status."""
        return svc.get_replication_status().model_dump()

    @mcp_server.tool(description="Get current replication lag")
    def admin_get_replication_lag() -> Dict[str, Any]:
        """Get replication lag."""
        return svc.get_replication_lag().model_dump()

    # ── Configuration ──────────────────────────────────────────────────

    @mcp_server.tool(description="Get server information and configuration")
    def admin_get_server_info() -> Dict[str, Any]:
        """Get server info."""
        return svc.get_server_info().model_dump()

    @mcp_server.tool(description="List configuration parameters")
    def admin_list_config_params(category: Optional[str] = None) -> List[Dict[str, Any]]:
        """List config params."""
        return [p.model_dump() for p in svc.list_config_params(category)]

    @mcp_server.tool(description="List installed database extensions")
    def admin_list_extensions() -> List[Dict[str, Any]]:
        """List extensions."""
        return [e.model_dump() for e in svc.list_extensions()]

    # ── Storage ────────────────────────────────────────────────────────

    @mcp_server.tool(description="Get storage usage per database")
    def admin_get_storage_usage() -> List[Dict[str, Any]]:
        """Get storage usage."""
        return [s.model_dump() for s in svc.get_storage_usage()]

    @mcp_server.tool(description="List tablespaces")
    def admin_list_tablespaces() -> List[Dict[str, Any]]:
        """List tablespaces."""
        return [t.model_dump() for t in svc.list_tablespaces()]

    # ── Jobs ───────────────────────────────────────────────────────────

    @mcp_server.tool(description="Create an administration job")
    def admin_create_job(job_type: str, engine: str) -> str:
        """Create an administration job."""
        req = JobCreate(job_type=job_type, engine=engine)
        result = svc.create_job(req)
        return f"Job '{result.id}' created (type={result.job_type}, status={result.status})"

    @mcp_server.tool(description="List administration jobs")
    def admin_list_jobs(status: Optional[str] = None, job_type: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """List administration jobs."""
        return [j.model_dump() for j in svc.list_jobs(status, job_type, limit)]

    @mcp_server.tool(description="Cancel an administration job")
    def admin_cancel_job(job_id: str) -> str:
        """Cancel a job."""
        if svc.cancel_job(job_id):
            return f"Job {job_id} cancelled"
        return f"Job {job_id} not found or already completed"

    # ── Audit ──────────────────────────────────────────────────────────

    @mcp_server.tool(description="List audit log entries")
    def admin_list_audit_logs(
        action: Optional[str] = None,
        target_type: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """List audit logs."""
        return [a.model_dump() for a in svc.list_audit_logs(action, target_type, severity, limit)]
