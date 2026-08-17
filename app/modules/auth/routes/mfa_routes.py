"""Auth MFA — FastAPI routes for multi-factor authentication.

Provides TOTP setup/verify, backup codes, and trusted device endpoints.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlmodel import Session
from pydantic import BaseModel

from common_lib.modules.data_storage.database.connection import get_session
from app.modules.auth.dependencies import get_current_active_user
from common_lib.modules.auth.users.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth/mfa", tags=["auth-mfa"])


class TOTPSetupResponse(BaseModel):
    secret: str
    otpauth_url: str
    is_verified: bool = False


class TOTPVerifyRequest(BaseModel):
    code: str


class TOTPVerifyResponse(BaseModel):
    verified: bool


class BackupCodeResponse(BaseModel):
    codes: list[dict]


class BackupCodeVerifyRequest(BaseModel):
    code: str


class BackupCodeVerifyResponse(BaseModel):
    verified: bool


class TrustDeviceRequest(BaseModel):
    device_fingerprint: str
    device_name: Optional[str] = None
    duration_days: int = 30


class TrustDeviceResponse(BaseModel):
    id: str
    expires_at: str


class MFAStatusResponse(BaseModel):
    has_mfa: bool
    is_verified: bool
    primary_secret_id: Optional[str] = None
    trusted_devices: int = 0
    methods: list[str] = []


@router.get("/status", response_model=MFAStatusResponse)
def get_mfa_status(
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session),
):
    """Get MFA status for the current user."""
    from common_lib.modules.auth.mfa.service import MFAService
    svc = MFAService(session)
    return svc.get_mfa_status(str(current_user.id))


@router.post("/totp/setup", response_model=TOTPSetupResponse)
def setup_totp(
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session),
):
    """Set up TOTP multi-factor authentication."""
    from common_lib.modules.auth.mfa.service import MFAService
    svc = MFAService(session)
    return svc.setup_totp(str(current_user.id), current_user.email)


@router.post("/totp/verify", response_model=TOTPVerifyResponse)
def verify_totp(
    data: TOTPVerifyRequest,
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session),
):
    """Verify a TOTP code to complete MFA setup."""
    from common_lib.modules.auth.mfa.service import MFAService
    svc = MFAService(session)
    try:
        verified = svc.verify_totp(str(current_user.id), data.code)
        return TOTPVerifyResponse(verified=verified)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/backup-codes/generate", response_model=BackupCodeResponse)
def generate_backup_codes(
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session),
):
    """Generate backup recovery codes for MFA."""
    from common_lib.modules.auth.mfa.service import MFAService
    svc = MFAService(session)
    codes = svc.generate_backup_codes(str(current_user.id))
    return BackupCodeResponse(codes=codes)


@router.post("/backup-codes/verify", response_model=BackupCodeVerifyResponse)
def verify_backup_code(
    data: BackupCodeVerifyRequest,
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session),
):
    """Verify and consume a backup recovery code."""
    from common_lib.modules.auth.mfa.service import MFAService
    svc = MFAService(session)
    verified = svc.verify_backup_code(str(current_user.id), data.code)
    return BackupCodeVerifyResponse(verified=verified)


@router.get("/backup-codes/remaining")
def get_backup_codes_remaining(
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session),
):
    """Get count of remaining unused backup codes."""
    from common_lib.modules.auth.mfa.service import MFAService
    svc = MFAService(session)
    count = svc.get_backup_codes_remaining(str(current_user.id))
    return {"remaining": count}


@router.post("/devices/trust", response_model=TrustDeviceResponse)
def trust_device(
    data: TrustDeviceRequest,
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session),
):
    """Mark current device as trusted to skip MFA."""
    from common_lib.modules.auth.mfa.service import MFAService
    svc = MFAService(session)
    return svc.trust_device(
        str(current_user.id),
        data.device_fingerprint,
        device_name=data.device_name,
        duration_days=data.duration_days,
    )


@router.get("/devices")
def list_trusted_devices(
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session),
):
    """List all trusted devices."""
    from common_lib.modules.auth.mfa.service import MFAService
    svc = MFAService(session)
    return {"devices": svc.list_trusted_devices(str(current_user.id))}


@router.delete("/devices/{device_id}")
def remove_trusted_device(
    device_id: str,
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session),
):
    """Remove a trusted device."""
    from common_lib.modules.auth.mfa.service import MFAService
    svc = MFAService(session)
    ok = svc.remove_trusted_device(device_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Device not found")
    return {"success": True}


@router.delete("/remove")
def remove_mfa(
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session),
):
    """Remove all MFA configuration for the current user."""
    from common_lib.modules.auth.mfa.service import MFAService
    svc = MFAService(session)
    svc.remove_mfa(str(current_user.id))
    return {"success": True, "message": "MFA removed"}
