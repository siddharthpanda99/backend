"""Security Module — REST API Routes.

/api/v1/security — module health, DLP scanning, security feature flags.

Audit-event persistence, compliance reporting and IP restriction rules are NOT
implemented here: they need a persisted security-audit store (a schema change,
which is out of scope for this module). Those routes answer `501` with a pointer
to the working alternative rather than failing with an internal traceback — see
`_not_implemented` and the module audit report.

The live secrets/keys/policies/users/sessions surface for this prefix is served
by `app.modules.db_studio.security.routes.router`, which `app/core/routers.py`
mounts at the same `/security` prefix. The two sets of paths do not collide
(measured: 0 shadowed keys).
"""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()


def _get_service():
    """Return the security service class.

    `SecurityService` is the module's CLI-shaped facade (`health`, `scrub_env`,
    `list_credentials`, `encrypt`, `decrypt`) and takes **no** session argument.
    The audit/DLP/compliance/IP handlers used to call `SecurityService(session)`
    and then `svc.log_audit_event(...)` — a method that exists neither on the
    service nor anywhere in `common_lib/modules/security` — so they could only
    ever fail.
    """
    from common_lib.modules.security.service import SecurityService

    return SecurityService


def _service_error_detail(exc: Exception) -> str:
    """Build a client-safe error message.

    The handlers used `detail=str(e)`, which surfaced absolute server filesystem
    paths (for example `.../common_lib/modules/integration/ports/__init__.py`)
    back to the caller — internal-path disclosure from a *security* endpoint. The
    exception *type* is safe to echo; the message is logged, not returned.
    """
    return f"{type(exc).__name__} while handling the request"


# ── Request/Response Models ──────────────────────────────────────────


class AuditEventRequest(BaseModel):
    event_type: str
    actor_id: str
    resource_id: Optional[str] = None
    resource_type: Optional[str] = None
    action: str = "unknown"
    details: Optional[dict] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


class ScanContentRequest(BaseModel):
    content: str
    content_type: str = "text"


class ComplianceReportRequest(BaseModel):
    report_type: str = "general"
    days: int = 30


def _not_implemented(capability: str, alternative: str) -> HTTPException:
    """Honest 501 for a capability this module does not actually have."""
    return HTTPException(
        status_code=501,
        detail=(
            f"'{capability}' is not implemented by the security module: there is no "
            f"persisted security-audit store behind it. Use {alternative} instead."
        ),
    )


# ── Module routes ─────────────────────────────────────────────────────


@router.get("/health", summary="Security module health")
async def security_health():
    """Report which security subcomponents are loaded."""
    try:
        return _get_service()().health()
    except Exception as e:  # noqa: BLE001
        logger.error("Security health check failed: %s", e)
        raise HTTPException(status_code=500, detail=_service_error_detail(e)) from e


@router.get("/feature-flags", summary="Security module feature flags")
async def security_feature_flags():
    """Report every security feature flag and its current value (all default OFF)."""
    try:
        from common_lib.modules.security.flags import describe_flags

        return {"flags": describe_flags()}
    except Exception as e:  # noqa: BLE001
        logger.error("Security feature-flag read failed: %s", e)
        raise HTTPException(status_code=500, detail=_service_error_detail(e)) from e


# ── Audit Event Routes ──────────────────────────────────────────────


@router.post("/audit/events", summary="Log a security audit event")
async def log_audit_event(req: AuditEventRequest):
    """Log a security audit event with actor, resource, action details."""
    logger.info(
        "audit event received but not persisted: type=%s actor=%s",
        req.event_type,
        req.actor_id,
    )
    raise _not_implemented("POST /security/audit/events", "GET /api/v1/security/audit")


@router.get("/audit/events", summary="List security audit events")
async def list_audit_events(
    event_type: Optional[str] = Query(None),
    actor_id: Optional[str] = Query(None),
    resource_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List security audit events with optional filters."""
    raise _not_implemented("GET /security/audit/events", "GET /api/v1/security/audit")


@router.get("/audit/stats", summary="Get security audit statistics")
async def get_audit_stats(days: int = Query(30, ge=1, le=365)):
    """Get security audit statistics for the last N days."""
    raise _not_implemented(
        "GET /security/audit/stats", "GET /api/v1/security/dashboard"
    )


# ── DLP Routes ──────────────────────────────────────────────────────


@router.post("/dlp/scan", summary="Scan content for sensitive data (DLP)")
async def scan_content(req: ScanContentRequest):
    """Scan content for PII: emails, phones, SSNs, credit cards, API keys, passwords.

    Backed by the module's real detector (`common_lib.modules.security.pii`), so
    this route works. `matches` reports entity *types and offsets*; `scrubbed` is
    the redaction callers should persist. Matched values are intentionally not
    echoed, so a DLP report cannot itself become a leak.
    """
    try:
        from common_lib.modules.security.pii import detect_pii

        result = detect_pii(req.content)
        return {
            "status": "ok",
            "content_type": req.content_type,
            "level": result.level.value,
            "match_count": len(result.entities),
            "matches": [
                {
                    "type": e.get("type"),
                    "start": e.get("start"),
                    "end": e.get("end"),
                    "level": e.get("level"),
                }
                for e in result.entities
            ],
            "scrubbed": result.scrubbed_content if result.entities else None,
        }
    except Exception as e:  # noqa: BLE001
        logger.error("DLP scan failed: %s", e)
        raise HTTPException(status_code=500, detail=_service_error_detail(e)) from e


# ── Compliance Routes ───────────────────────────────────────────────


@router.post("/compliance/report", summary="Generate compliance report")
async def generate_compliance_report(req: ComplianceReportRequest):
    """Generate a compliance report covering the specified period."""
    raise _not_implemented(
        "POST /security/compliance/report",
        "GET /api/v1/security/compliance/reports",
    )


# ── IP Restriction Routes ───────────────────────────────────────────


@router.post("/ip/check", summary="Check if IP address is allowed")
async def check_ip_allowed(ip_address: str, rules: Optional[list] = None):
    """Check if an IP address is allowed based on restriction rules."""
    raise _not_implemented("POST /security/ip/check", "GET /api/v1/security/policies")
