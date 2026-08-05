"""Auth Domain Verification — FastAPI routes for domain ownership verification.

Provides claiming domains, DNS verification checks, and domain management.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session
from pydantic import BaseModel

from common_lib.modules.data_storage.database.connection import get_session
from app.modules.auth.dependencies import get_current_active_user
from common_lib.modules.users.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth/domains", tags=["auth-domains"])


class ClaimDomainRequest(BaseModel):
    domain: str
    org_id: str


class VerifyDomainResponse(BaseModel):
    id: str
    domain: str
    status: str
    verified: bool
    dns_value_found: str | None = None
    dns_value_expected: str | None = None


@router.post("/claim")
def claim_domain(
    data: ClaimDomainRequest,
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session),
):
    """Claim a domain for verification via DNS TXT record."""
    from common_lib.modules.auth.domain_verification.service import DomainVerificationService
    svc = DomainVerificationService(session)
    try:
        return svc.claim_domain(data.org_id, data.domain)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{claim_id}/verify")
def verify_domain(
    claim_id: str,
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session),
):
    """Verify a domain claim by checking its DNS TXT record."""
    from common_lib.modules.auth.domain_verification.service import DomainVerificationService
    svc = DomainVerificationService(session)
    try:
        return svc.verify_domain(claim_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/org/{org_id}")
def list_org_domains(
    org_id: str,
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session),
):
    """List all domains claimed by an organization."""
    from common_lib.modules.auth.domain_verification.service import DomainVerificationService
    svc = DomainVerificationService(session)
    return {"domains": svc.list_org_domains(org_id)}


@router.get("/check/{domain}")
def check_domain_status(
    domain: str,
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session),
):
    """Check the verification status of a domain."""
    from common_lib.modules.auth.domain_verification.service import DomainVerificationService
    svc = DomainVerificationService(session)
    status = svc.get_domain_status(domain)
    if not status:
        raise HTTPException(status_code=404, detail="Domain not found")
    return status


@router.post("/org/{org_id}/verify-all")
def verify_all_pending(
    org_id: str,
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session),
):
    """Attempt to verify all pending domains for an organization."""
    from common_lib.modules.auth.domain_verification.service import DomainVerificationService
    svc = DomainVerificationService(session)
    return {"results": svc.verify_all_pending(org_id)}


@router.delete("/{claim_id}")
def remove_domain(
    claim_id: str,
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session),
):
    """Remove a domain claim."""
    from common_lib.modules.auth.domain_verification.service import DomainVerificationService
    svc = DomainVerificationService(session)
    ok = svc.remove_domain(claim_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Domain claim not found")
    return {"success": True}
