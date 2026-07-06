"""
Activity Logging Middleware — automatically logs every API request.

Intercepts all FastAPI requests and records:
- Activity log entry (every request)
- Audit log entry (for critical actions: auth, RBAC, data mutations, deletions)

This ensures "every action that happens is logged" without requiring
manual logging calls in every route handler.
"""
import time
import logging
import json
from typing import Callable
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("control_center_middleware")

# Lazy-imported at module level to avoid per-request import overhead
_activity_logger_cls = None
_audit_logger_cls = None


def _get_loggers():
    global _activity_logger_cls, _audit_logger_cls
    if _activity_logger_cls is None:
        from common_lib.modules.control_center.service import ActivityLogger, AuditLogger
        _activity_logger_cls = ActivityLogger
        _audit_logger_cls = AuditLogger
    return _activity_logger_cls, _audit_logger_cls

# Endpoints that trigger audit logging (critical actions)
AUDIT_CATEGORIES = {
    "/api/v1/auth": "auth",
    "/api/v1/roles": "rbac",
    "/api/v1/permissions": "rbac",
    "/api/v1/users": "user_management",
    "/api/v1/control-center": "control_center",
    "/api/v1/governance": "governance",
    "/api/v1/agents": "agent_management",
    "/api/v1/workflows": "workflow_management",
    "/api/v1/marketplace": "marketplace",
    "/api/v1/models": "model_management",
}

# HTTP methods that represent mutations (worth auditing in detail)
AUDIT_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

# Health check / static endpoints to skip
SKIP_PATHS = {"/docs", "/redoc", "/openapi.json", "/favicon.ico"}


# Auth action mapping for entity_audit_log (module-level constant)
_AUTH_ACTION_MAP = {
    "POST /api/v1/auth/login": "login",
    "POST /api/v1/auth/logout": "logout",
    "POST /api/v1/auth/register": "created",
}


class ActivityLoggingMiddleware(BaseHTTPMiddleware):
    """Logs every API request to the control_center_activity_log table."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip non-API and health endpoints
        path = request.url.path
        if not path.startswith("/api/v1") or path in SKIP_PATHS:
            return await call_next(request)

        start_time = time.time()

        # Extract user info from request state (set by auth middleware)
        user_id = getattr(request.state, "user_id", None)
        user_email = getattr(request.state, "user_email", None)
        user_role = getattr(request.state, "user_role", None)
        ip_address = request.client.host if request.client else None

        response = await call_next(request)

        elapsed_ms = round((time.time() - start_time) * 1000, 1)

        # Determine severity based on status code and method
        status = response.status_code
        method = request.method
        severity = "info"
        if status >= 500:
            severity = "error"
        elif status >= 400:
            severity = "warning"
        elif method in AUDIT_METHODS:
            severity = "info"

        # Determine category
        category = "api_call"
        for prefix, cat in AUDIT_CATEGORIES.items():
            if path.startswith(prefix):
                category = cat
                break

        # Determine resource type from path
        resource_type = None
        parts = path.strip("/").split("/")
        if len(parts) >= 3 and parts[0] == "api" and parts[1] == "v1":
            resource_type = parts[2]

        # Build action string
        action = f"{method} {path}"

        # Build metadata
        metadata = {
            "status_code": status,
            "method": method,
            "elapsed_ms": elapsed_ms,
            "query_params": dict(request.query_params) if request.query_params else None,
            "user_agent": request.headers.get("user-agent", ""),
        }

        # Log to activity table (non-blocking, best-effort)
        try:
            from sqlmodel import Session as SQLSession
            from common_lib.modules.data_storage.database.connection import engine
            ActivityLogCls, _ = _get_loggers()

            with SQLSession(engine) as session:
                activity_log = ActivityLogCls(session)
                activity_log.log(
                    action=action,
                    category=category,
                    severity=severity,
                    user_id=str(user_id) if user_id else None,
                    user_email=user_email,
                    user_role=user_role,
                    ip_address=ip_address,
                    description=f"{method} {path} → {status} ({elapsed_ms}ms)",
                    resource_type=resource_type,
                    source_module="api_middleware",
                    metadata=metadata,
                )
                session.commit()
        except Exception as e:
            logger.debug(f"Activity logging skipped: {e}")

        # For critical mutations, also log to audit table + entity_audit_log
        if method in AUDIT_METHODS and category in ("auth", "rbac", "user_management", "data"):
            try:
                from sqlmodel import Session as SQLSession
                from common_lib.modules.data_storage.database.connection import engine
                _, AuditLogCls = _get_loggers()

                with SQLSession(engine) as session:
                    audit_log = AuditLogCls(session)
                    # ── Also write to entity_audit_log for auth events (same transaction) ──
                    entity_audit = None
                    if category == "auth":
                        from common_lib.modules.marketplace.entity_audit_models import EntityAuditLog
                        entity_audit = EntityAuditLog(
                            entity_type="auth",
                            entity_id=str(user_id) if user_id else (user_email or "anonymous"),
                            entity_name=user_email,
                            action=_AUTH_ACTION_MAP.get(action, "updated"),
                            actor_id=str(user_id) if user_id else None,
                            actor_name=user_email,
                            changes_json={
                                "method": method,
                                "endpoint": path,
                                "status_code": status,
                                "success": status < 400,
                            },
                            ip_address=ip_address,
                            user_agent=metadata.get("user_agent", ""),
                            metadata_json={
                                "category": category,
                                "severity": severity,
                                "source": "api_middleware",
                                "user_role": user_role,
                            },
                        )
                        session.add(entity_audit)

                    # ── Audit trail entry ──
                    audit_log.audit(
                        action=action,
                        user_id=str(user_id) if user_id else None,
                        user_email=user_email,
                        user_role=user_role,
                        ip_address=ip_address,
                        action_category=category,
                        severity=severity,
                        resource_type=resource_type,
                        method=method,
                        endpoint=path,
                        success=status < 400,
                        error_message=None if status < 400 else f"HTTP {status}",
                        source_module="api_middleware",
                    )
                    # Single commit for both audit_log + entity_audit_log
                    session.commit()

            except Exception as e:
                logger.debug(f"Audit logging skipped: {e}")

        return response
