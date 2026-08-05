"""Secrets Scanning — FastAPI routes (SSOT §13)."""

from typing import Optional
from fastapi import APIRouter, Depends
from sqlmodel import Session
from app.modules.secrets_manager.deps import get_sm_session
from common_lib.modules.secrets_manager.scanning.service import ScanningService

router = APIRouter()


@router.get("/secrets/scanning/targets", summary="List scan targets")
def list_targets(target_type: Optional[str] = None, session: Session = Depends(get_sm_session)):
    svc = ScanningService(session)
    return svc.list_targets(target_type=target_type)


@router.post("/secrets/scanning/targets", summary="Register scan target")
def register_target(body: dict, session: Session = Depends(get_sm_session)):
    svc = ScanningService(session)
    return svc.register_target(**body)


@router.post("/secrets/scanning/scan", summary="Scan text for secrets")
def scan_text(body: dict, session: Session = Depends(get_sm_session)):
    svc = ScanningService(session)
    return svc.scan_text(**body)


@router.get("/secrets/scanning/findings", summary="List findings")
def list_findings(status: Optional[str] = None, severity: Optional[str] = None,
                  session: Session = Depends(get_sm_session)):
    svc = ScanningService(session)
    return svc.list_findings(status=status, severity=severity)


@router.post("/secrets/scanning/findings/{finding_id}/remediate", summary="Remediate finding")
def remediate_finding(finding_id: str, body: dict, session: Session = Depends(get_sm_session)):
    svc = ScanningService(session)
    return svc.remediate_finding(finding_id=finding_id, **body)
