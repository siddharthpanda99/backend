"""Import/Export — FastAPI routes (SSOT §27)."""

from typing import Optional
from fastapi import APIRouter, Depends
from sqlmodel import Session
from app.modules.secrets_manager.deps import get_sm_session
from common_lib.modules.secrets_manager.import_export.service import ImportExportService

router = APIRouter()


@router.get("/secrets/export", summary="Export secrets as JSON")
def export_secrets(mount_path: Optional[str] = None, session: Session = Depends(get_sm_session)):
    svc = ImportExportService(session)
    return svc.export_secrets_to_json(mount_path=mount_path)


@router.get("/secrets/export/policies", summary="Export policies as JSON")
def export_policies(session: Session = Depends(get_sm_session)):
    svc = ImportExportService(session)
    return svc.export_policies_to_json()


@router.get("/secrets/export/audit", summary="Export audit log as JSON")
def export_audit(since_hours: int = 168, session: Session = Depends(get_sm_session)):
    svc = ImportExportService(session)
    return svc.export_audit_log(since_hours=since_hours)


@router.post("/secrets/import", summary="Import secrets from JSON")
def import_secrets(body: dict, session: Session = Depends(get_sm_session)):
    svc = ImportExportService(session)
    return svc.import_from_json(json_str=body.get("data", "{}"))
