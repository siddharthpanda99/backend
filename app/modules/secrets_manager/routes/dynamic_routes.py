"""Secrets Manager Dynamic Secrets API routes — SSOT 03: Dynamic Secrets & Leases."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dynamic", tags=["secrets-manager-dynamic"])


def _get_db_session():
    from sqlmodel import Session
    from common_lib.modules.integration.adapters.database_adapter import get_db_port
    engine = get_db_port().get_engine()
    return Session(engine)


class DynamicSecretCreateRequest(BaseModel):
    name: str
    secret_type: str = "database"
    provider: str = ""
    config: Optional[dict] = None
    default_ttl_seconds: int = 3600
    max_ttl_seconds: int = 86400
    created_by: Optional[str] = None


class LeaseIssueRequest(BaseModel):
    dynamic_secret_name: str
    ttl_seconds: Optional[int] = None
    requested_by: Optional[str] = None
    tenant_id: Optional[str] = None


class LeaseRenewRequest(BaseModel):
    lease_id: str
    ttl_seconds: Optional[int] = None


class LeaseRevokeRequest(BaseModel):
    lease_id: str
    reason: str = "user_request"


@router.post("/secrets")
def create_dynamic_secret(request: DynamicSecretCreateRequest) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.dynamic.service import DynamicSecretsService
        svc = DynamicSecretsService(session=session)
        return svc.create_dynamic_secret(
            name=request.name, secret_type=request.secret_type,
            provider=request.provider, config=request.config,
            default_ttl_seconds=request.default_ttl_seconds,
            max_ttl_seconds=request.max_ttl_seconds,
            created_by=request.created_by,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/secrets")
def list_dynamic_secrets() -> List[Dict[str, Any]]:
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.dynamic.service import DynamicSecretsService
        return DynamicSecretsService(session=session).list_dynamic_secrets()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.post("/leases")
def issue_lease(request: LeaseIssueRequest) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.dynamic.service import DynamicSecretsService
        svc = DynamicSecretsService(session=session)
        result = svc.issue_lease(
            dynamic_secret_name=request.dynamic_secret_name,
            ttl_seconds=request.ttl_seconds,
            requested_by=request.requested_by,
            tenant_id=request.tenant_id,
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


@router.post("/leases/renew")
def renew_lease(request: LeaseRenewRequest) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.dynamic.service import DynamicSecretsService
        result = DynamicSecretsService(session=session).renew_lease(
            lease_id=request.lease_id, ttl_seconds=request.ttl_seconds,
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


@router.post("/leases/revoke")
def revoke_lease(request: LeaseRevokeRequest) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.dynamic.service import DynamicSecretsService
        success = DynamicSecretsService(session=session).revoke_lease(
            lease_id=request.lease_id, reason=request.reason,
        )
        if not success:
            raise HTTPException(status_code=404, detail="Lease not found")
        return {"revoked": True, "lease_id": request.lease_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/leases")
def list_active_leases(dynamic_secret_name: Optional[str] = None) -> List[Dict[str, Any]]:
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.dynamic.service import DynamicSecretsService
        return DynamicSecretsService(session=session).list_active_leases(
            dynamic_secret_name=dynamic_secret_name,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.post("/leases/cleanup")
def cleanup_expired_leases() -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.dynamic.service import DynamicSecretsService
        count = DynamicSecretsService(session=session).cleanup_expired_leases()
        return {"cleaned": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()
