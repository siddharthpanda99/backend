"""Secrets Manager SSH API routes — SSOT 08: SSH / Remote Access."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ssh", tags=["secrets-manager-ssh"])


def _get_db_session():
    from sqlmodel import Session
    from common_lib.modules.integration.adapters.database_adapter import get_db_port
    engine = get_db_port().get_engine()
    return Session(engine)


class KeyPairCreateRequest(BaseModel):
    name: str
    key_type: str = "ed25519"
    key_size: int = 256
    ttl_seconds: Optional[int] = None
    tenant_id: Optional[str] = None
    created_by: Optional[str] = None


class TargetRegisterRequest(BaseModel):
    hostname: str
    port: int = 22
    username: str = "root"
    labels: Optional[dict] = None
    tenant_id: Optional[str] = None
    created_by: Optional[str] = None


class OtpGenerateRequest(BaseModel):
    target_hostname: str
    username: str = "root"
    ttl_seconds: int = 300
    requested_by: Optional[str] = None


class OtpValidateRequest(BaseModel):
    otp_code: str
    target_hostname: str


class CertIssueRequest(BaseModel):
    key_id: str
    cert_type: str = "user"
    ca_key_pair_name: Optional[str] = None
    principals: Optional[List[str]] = None
    ttl_seconds: int = 86400
    requested_by: Optional[str] = None


class CertRevokeRequest(BaseModel):
    serial_number: str


@router.post("/key-pairs")
def create_ssh_key_pair(request: KeyPairCreateRequest) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.ssh.service import SshService
        return SshService(session).create_key_pair(
            name=request.name, key_type=request.key_type,
            key_size=request.key_size, ttl_seconds=request.ttl_seconds,
            tenant_id=request.tenant_id, created_by=request.created_by,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/key-pairs")
def list_ssh_key_pairs(status: Optional[str] = None) -> List[Dict[str, Any]]:
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.ssh.service import SshService
        return SshService(session).list_key_pairs(status=status)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.post("/key-pairs/{name}/revoke")
def revoke_ssh_key_pair(name: str) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.ssh.service import SshService
        success = SshService(session).revoke_key_pair(name=name)
        if not success:
            raise HTTPException(status_code=404, detail=f"Key pair '{name}' not found")
        return {"revoked": True, "name": name}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.post("/targets")
def register_target(request: TargetRegisterRequest) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.ssh.service import SshService
        return SshService(session).register_target(
            hostname=request.hostname, port=request.port,
            username=request.username, labels=request.labels,
            tenant_id=request.tenant_id, created_by=request.created_by,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/targets")
def list_targets() -> List[Dict[str, Any]]:
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.ssh.service import SshService
        return SshService(session).list_targets()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.post("/otp/generate")
def generate_otp(request: OtpGenerateRequest) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.ssh.service import SshService
        result = SshService(session).generate_otp(
            target_hostname=request.target_hostname,
            username=request.username,
            ttl_seconds=request.ttl_seconds,
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


@router.post("/otp/validate")
def validate_otp(request: OtpValidateRequest) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.ssh.service import SshService
        valid = SshService(session).validate_otp(
            otp_code=request.otp_code,
            target_hostname=request.target_hostname,
        )
        return {"valid": valid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.post("/certificates")
def issue_ssh_certificate(request: CertIssueRequest) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.ssh.service import SshService
        result = SshService(session).issue_certificate(
            key_id=request.key_id, cert_type=request.cert_type,
            ca_key_pair_name=request.ca_key_pair_name,
            principals=request.principals,
            ttl_seconds=request.ttl_seconds,
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


@router.post("/certificates/revoke")
def revoke_ssh_certificate(request: CertRevokeRequest) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.ssh.service import SshService
        success = SshService(session).revoke_certificate(
            serial_number=request.serial_number,
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
