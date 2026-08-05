"""Secrets Manager Seal — FastAPI routes for seal/unseal operations."""

from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session
from pydantic import BaseModel
from typing import Optional

from common_lib.modules.data_storage.database.connection import get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/secrets/seal", tags=["secrets-seal"])


class ConfigureSealRequest(BaseModel):
    total_shares: int = 5
    threshold: int = 3
    auto_unseal_provider: Optional[str] = None
    auto_unseal_key_id: Optional[str] = None


class SubmitShareRequest(BaseModel):
    operator_id: str
    share_key: str


@router.get("/status")
def get_seal_status(session: Session = Depends(get_session)):
    """Get current seal status."""
    from common_lib.modules.secrets_manager.seal.service import SealService
    svc = SealService(session)
    return svc.get_seal_status()


@router.post("/configure")
def configure_seal(data: ConfigureSealRequest, session: Session = Depends(get_session)):
    """Configure seal/unseal parameters."""
    from common_lib.modules.secrets_manager.seal.service import SealService
    svc = SealService(session)
    return svc.configure_seal(
        total_shares=data.total_shares,
        threshold=data.threshold,
        auto_unseal_provider=data.auto_unseal_provider,
        auto_unseal_key_id=data.auto_unseal_key_id,
    )


@router.post("/submit-share")
def submit_unseal_share(data: SubmitShareRequest, session: Session = Depends(get_session)):
    """Submit a single Shamir unseal share."""
    from common_lib.modules.secrets_manager.seal.service import SealService
    svc = SealService(session)
    return svc.submit_unseal_share(data.operator_id, data.share_key)


@router.post("/seal")
def seal(session: Session = Depends(get_session)):
    """Seal the secrets manager."""
    from common_lib.modules.secrets_manager.seal.service import SealService
    svc = SealService(session)
    return svc.seal()


@router.post("/auto-unseal")
def auto_unseal(session: Session = Depends(get_session)):
    """Attempt automatic unseal via configured KMS provider."""
    from common_lib.modules.secrets_manager.seal.service import SealService
    svc = SealService(session)
    return svc.auto_unseal()


@router.post("/recovery-keys/generate")
def generate_recovery_keys(count: int = Query(3), session: Session = Depends(get_session)):
    """Generate emergency recovery keys."""
    from common_lib.modules.secrets_manager.seal.service import SealService
    svc = SealService(session)
    return {"keys": svc.generate_recovery_keys(count=count)}


@router.get("/recovery-keys")
def list_recovery_keys(session: Session = Depends(get_session)):
    """List recovery key metadata."""
    from common_lib.modules.secrets_manager.seal.service import SealService
    svc = SealService(session)
    return {"keys": svc.list_recovery_keys()}
