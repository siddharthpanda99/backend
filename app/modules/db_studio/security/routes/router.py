"""Thin FastAPI router for Security, Auth & Secret Management (UDS Module 18)."""

from fastapi import APIRouter, HTTPException
from common_lib.modules.db_studio.security import (
    SecurityService,
    LoginRequest, LoginResponse, SessionOut,
    UserCreate, UserOut,
    ApiKeyCreate, ApiKeyOut, ApiKeyFullOut,
    SecretCreate, SecretOut,
    CertificateCreate, CertificateOut,
    AuditEventOut,
    ComplianceReportOut,
    SecurityPolicyCreate, SecurityPolicyOut,
    SecurityDashboardOut,
)

router = APIRouter(prefix="/api/v1/security", tags=["Security"])
svc = SecurityService()


# ── Authentication ──────────────────────────────────────────────────

@router.post("/auth/login", response_model=LoginResponse)
def login(req: LoginRequest):
    return svc.login(req)


@router.get("/sessions", response_model=list[SessionOut])
def list_sessions(user_id: str = None, is_active: bool = None, limit: int = 50):
    return svc.list_sessions(user_id, is_active, limit)


# ── Users ───────────────────────────────────────────────────────────

@router.post("/users", response_model=UserOut)
def create_user(req: UserCreate):
    try:
        return svc.create_user(req)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/users", response_model=list[UserOut])
def list_users(status: str = None, limit: int = 50):
    return svc.list_users(status, limit)


# ── API Keys ────────────────────────────────────────────────────────

@router.post("/api-keys", response_model=ApiKeyFullOut)
def create_api_key(req: ApiKeyCreate):
    return svc.create_api_key(req)


@router.get("/api-keys", response_model=list[ApiKeyOut])
def list_api_keys(user_id: str = None, limit: int = 50):
    return svc.list_api_keys(user_id, limit)


@router.patch("/api-keys/{key_id}/revoke", response_model=ApiKeyOut)
def revoke_api_key(key_id: str):
    result = svc.revoke_api_key(key_id)
    if not result:
        raise HTTPException(status_code=404, detail="API key not found")
    return result


# ── Secrets ─────────────────────────────────────────────────────────

@router.post("/secrets", response_model=SecretOut)
def create_secret(req: SecretCreate):
    return svc.create_secret(req)


@router.get("/secrets", response_model=list[SecretOut])
def list_secrets(provider: str = None, limit: int = 50):
    return svc.list_secrets(provider, limit)


@router.get("/secrets/{secret_id}/value")
def get_secret_value(secret_id: str):
    value = svc.get_secret_value(secret_id)
    if value is None:
        raise HTTPException(status_code=404, detail="Secret not found")
    return {"value": value}


@router.post("/secrets/{secret_id}/rotate", response_model=SecretOut)
def rotate_secret(secret_id: str, new_value: str = None):
    result = svc.rotate_secret(secret_id, new_value)
    if not result:
        raise HTTPException(status_code=404, detail="Secret not found")
    return result


# ── Certificates ────────────────────────────────────────────────────

@router.post("/certificates", response_model=CertificateOut)
def create_certificate(req: CertificateCreate):
    return svc.create_certificate(req)


@router.get("/certificates", response_model=list[CertificateOut])
def list_certificates(status: str = None, limit: int = 50):
    return svc.list_certificates(status, limit)


# ── Audit ───────────────────────────────────────────────────────────

@router.get("/audit", response_model=list[AuditEventOut])
def list_audit_events(event_type: str = None, severity: str = None,
                      user_id: str = None, limit: int = 100):
    return svc.list_audit_events(event_type, severity, user_id, limit)


# ── Compliance ──────────────────────────────────────────────────────

@router.post("/compliance/scan", response_model=ComplianceReportOut)
def run_compliance_scan(report_type: str = "soc2"):
    return svc.run_compliance_scan(report_type)


@router.get("/compliance/reports", response_model=list[ComplianceReportOut])
def list_compliance_reports(report_type: str = None, limit: int = 20):
    return svc.list_compliance_reports(report_type, limit)


# ── Security Policies ───────────────────────────────────────────────

@router.post("/policies", response_model=SecurityPolicyOut)
def create_policy(req: SecurityPolicyCreate):
    return svc.create_policy(req)


@router.get("/policies", response_model=list[SecurityPolicyOut])
def list_policies(policy_type: str = None, enabled: bool = None, limit: int = 50):
    return svc.list_policies(policy_type, enabled, limit)


# ── Dashboard ───────────────────────────────────────────────────────

@router.get("/dashboard", response_model=SecurityDashboardOut)
def get_dashboard():
    return svc.get_dashboard()
