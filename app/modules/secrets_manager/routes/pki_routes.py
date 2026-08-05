"""Secrets Manager PKI API routes — SSOT 07: PKI / Certificates / ACME."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pki", tags=["secrets-manager-pki"])


def _get_db_session():
    from sqlmodel import Session
    from common_lib.modules.integration.adapters.database_adapter import get_db_port
    engine = get_db_port().get_engine()
    return Session(engine)


class CACreateRequest(BaseModel):
    name: str
    type: str = "internal"
    default_ttl_seconds: int = 2592000
    max_ttl_seconds: int = 31536000
    allowed_domains: Optional[str] = None
    created_by: Optional[str] = None


class CertIssueRequest(BaseModel):
    common_name: str
    ca_name: str
    ttl_seconds: Optional[int] = None
    subject_alt_names: Optional[List[str]] = None
    requested_by: Optional[str] = None


class CertRevokeRequest(BaseModel):
    serial_number: str
    reason: str = "unspecified"


@router.post("/cas")
def create_ca(request: CACreateRequest) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.pki.service import CertificateService
        svc = CertificateService(session=session)
        return svc.create_ca(
            name=request.name, type=request.type,
            default_ttl_seconds=request.default_ttl_seconds,
            max_ttl_seconds=request.max_ttl_seconds,
            allowed_domains=request.allowed_domains,
            created_by=request.created_by,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/cas")
def list_cas() -> List[Dict[str, Any]]:
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.pki.service import CertificateService
        return CertificateService(session=session).list_cas()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.post("/certificates")
def issue_certificate(request: CertIssueRequest) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.pki.service import CertificateService
        svc = CertificateService(session=session)
        result = svc.issue_certificate(
            common_name=request.common_name, ca_name=request.ca_name,
            ttl_seconds=request.ttl_seconds,
            subject_alt_names=request.subject_alt_names,
            requested_by=request.requested_by,
        )
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/certificates")
def list_certificates(
    ca_name: Optional[str] = None, status: Optional[str] = None,
) -> List[Dict[str, Any]]:
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.pki.service import CertificateService
        return CertificateService(session=session).list_certificates(
            ca_name=ca_name, status=status,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.post("/certificates/revoke")
def revoke_certificate(request: CertRevokeRequest) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.pki.service import CertificateService
        success = CertificateService(session=session).revoke_certificate(
            serial_number=request.serial_number, reason=request.reason,
        )
        if not success:
            raise HTTPException(status_code=404, detail="Certificate not found")
        return {"revoked": True, "serial_number": request.serial_number}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/certificates/expiring")
def get_expiring_certificates(days: int = 30) -> List[Dict[str, Any]]:
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.pki.service import CertificateService
        return CertificateService(session=session).get_expiring(days=days)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()
