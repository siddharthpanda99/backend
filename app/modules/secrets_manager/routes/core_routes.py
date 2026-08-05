"""Secrets Manager Encryption Core API routes — SSOT 05, 06: Encryption & KMS.

Thin routing layer for encryption key management and encrypt/decrypt operations.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/encryption", tags=["secrets-manager-core"])


def _get_db_session():
    from sqlmodel import Session
    from common_lib.modules.integration.adapters.database_adapter import get_db_port
    engine = get_db_port().get_engine()
    return Session(engine)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class KeyCreateRequest(BaseModel):
    name: str
    purpose: str = "encryption"
    algorithm: str = "aes-256-gcm"
    key_size: int = 256
    kms_provider: str = "local"
    auto_rotate: bool = False
    rotation_period_days: Optional[int] = None
    created_by: Optional[str] = None


class EncryptRequest(BaseModel):
    plaintext: str
    key_name: Optional[str] = None


class DecryptRequest(BaseModel):
    ciphertext: str


class RotateKeyRequest(BaseModel):
    name: str
    rotated_by: Optional[str] = None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/keys")
def create_encryption_key(request: KeyCreateRequest) -> Dict[str, Any]:
    """Create a new encryption key."""
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.core.service import EncryptionService

        svc = EncryptionService(session=session)
        return svc.create_key(
            name=request.name,
            purpose=request.purpose,
            algorithm=request.algorithm,
            key_size=request.key_size,
            kms_provider=request.kms_provider,
            auto_rotate=request.auto_rotate,
            rotation_period_days=request.rotation_period_days,
            created_by=request.created_by,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/keys")
def list_encryption_keys(purpose: Optional[str] = None) -> Dict[str, Any]:
    """List all encryption keys."""
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.core.service import EncryptionService

        svc = EncryptionService(session=session)
        return svc.list_keys(purpose=purpose)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.post("/encrypt")
def encrypt_value(request: EncryptRequest) -> Dict[str, Any]:
    """Encrypt a value using the encryption service."""
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.core.service import EncryptionService

        svc = EncryptionService(session=session)
        result = svc.encrypt_value(
            plaintext=request.plaintext,
            key_name=request.key_name,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.post("/decrypt")
def decrypt_value(request: DecryptRequest) -> Dict[str, Any]:
    """Decrypt a value using the encryption service."""
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.core.service import EncryptionService

        svc = EncryptionService(session=session)
        plaintext = svc.decrypt_value(ciphertext=request.ciphertext)
        return {"plaintext": plaintext}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.post("/keys/{name}/rotate")
def rotate_key(name: str, request: Optional[RotateKeyRequest] = None) -> Dict[str, Any]:
    """Rotate an encryption key."""
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.core.service import EncryptionService

        svc = EncryptionService(session=session)
        result = svc.rotate_key(
            name=name,
            rotated_by=request.rotated_by if request else None,
        )
        if result is None:
            raise HTTPException(status_code=404, detail=f"Key '{name}' not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()
