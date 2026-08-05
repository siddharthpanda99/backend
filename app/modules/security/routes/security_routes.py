"""Security Module — REST API Routes.

/api/v1/security — Audit events, DLP scanning, compliance reporting, IP restrictions.
"""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()


def _get_session():
    from contextlib import contextmanager
    from common_lib.modules.integration.ports import get_db_port
    @contextmanager
    def _session_cm():
        session = get_db_port().get_session()
        try:
            yield session
        finally:
            session.close()
    return _session_cm()


def _get_service():
    from common_lib.modules.security.service import SecurityService
    return SecurityService


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


# ── Audit Event Routes ──────────────────────────────────────────────

@router.post("/audit/events", summary="Log a security audit event")
async def log_audit_event(req: AuditEventRequest):
    """Log a security audit event with actor, resource, action details."""
    try:
        with _get_session() as session:
            svc = _get_service()(session)
            return svc.log_audit_event(
                event_type=req.event_type,
                actor_id=req.actor_id,
                resource_id=req.resource_id,
                resource_type=req.resource_type,
                action=req.action,
                details=req.details,
                ip_address=req.ip_address,
                user_agent=req.user_agent,
            )
    except Exception as e:
        logger.error("Failed to log audit event: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/audit/events", summary="List security audit events")
async def list_audit_events(
    event_type: Optional[str] = Query(None),
    actor_id: Optional[str] = Query(None),
    resource_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List security audit events with optional filters."""
    try:
        with _get_session() as session:
            svc = _get_service()(session)
            return svc.list_audit_events(
                event_type=event_type,
                actor_id=actor_id,
                resource_type=resource_type,
                limit=limit,
                offset=offset,
            )
    except Exception as e:
        logger.error("Failed to list audit events: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/audit/stats", summary="Get security audit statistics")
async def get_audit_stats(days: int = Query(30, ge=1, le=365)):
    """Get security audit statistics for the last N days."""
    try:
        with _get_session() as session:
            svc = _get_service()(session)
            return svc.get_audit_stats(days=days)
    except Exception as e:
        logger.error("Failed to get audit stats: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ── DLP Routes ──────────────────────────────────────────────────────

@router.post("/dlp/scan", summary="Scan content for sensitive data (DLP)")
async def scan_content(req: ScanContentRequest):
    """Scan content for PII patterns: emails, phone numbers, SSNs, credit cards, API keys."""
    try:
        with _get_session() as session:
            svc = _get_service()(session)
            return svc.scan_content(content=req.content, content_type=req.content_type)
    except Exception as e:
        logger.error("Failed to scan content: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ── Compliance Routes ───────────────────────────────────────────────

@router.post("/compliance/report", summary="Generate compliance report")
async def generate_compliance_report(req: ComplianceReportRequest):
    """Generate a compliance report covering the specified period."""
    try:
        with _get_session() as session:
            svc = _get_service()(session)
            return svc.generate_compliance_report(
                report_type=req.report_type, days=req.days
            )
    except Exception as e:
        logger.error("Failed to generate compliance report: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ── IP Restriction Routes ──────────────────────────────────────────

@router.post("/ip/check", summary="Check if IP address is allowed")
async def check_ip_allowed(ip_address: str, rules: Optional[list] = None):
    """Check if an IP address is allowed based on restriction rules."""
    try:
        with _get_session() as session:
            svc = _get_service()(session)
            return svc.check_ip_allowed(ip_address=ip_address, rules=rules)
    except Exception as e:
        logger.error("Failed to check IP: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
