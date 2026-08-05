"""Secrets Manager Cloud API routes — SSOT 11: Cloud Federation / External Vaults."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cloud", tags=["secrets-manager-cloud"])


def _get_db_session():
    from sqlmodel import Session
    from common_lib.modules.integration.adapters.database_adapter import get_db_port
    engine = get_db_port().get_engine()
    return Session(engine)


class ProviderCreateRequest(BaseModel):
    name: str
    provider_type: str = "aws"
    region: str = "us-east-1"
    created_by: Optional[str] = None


class VaultRegisterRequest(BaseModel):
    name: str
    vault_type: str = "hashicorp"
    endpoint_url: str = ""
    sync_direction: str = "import"
    created_by: Optional[str] = None


class ReplicationCreateRequest(BaseModel):
    name: str
    target_cluster: str
    replication_mode: str = "async"
    path_filter: Optional[str] = None
    created_by: Optional[str] = None


@router.post("/providers")
def create_provider(request: ProviderCreateRequest) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.cloud.service import CloudFederationService

        svc = CloudFederationService(session)
        return svc.create_provider(
            name=request.name, provider_type=request.provider_type,
            region=request.region, created_by=request.created_by,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/providers")
def list_providers() -> List[Dict[str, Any]]:
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.cloud.service import CloudFederationService

        return CloudFederationService(session).list_providers()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.post("/vaults")
def register_vault(request: VaultRegisterRequest) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.cloud.service import CloudFederationService

        svc = CloudFederationService(session)
        return svc.register_vault(
            name=request.name, vault_type=request.vault_type,
            endpoint_url=request.endpoint_url,
            sync_direction=request.sync_direction, created_by=request.created_by,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/vaults")
def list_external_vaults() -> List[Dict[str, Any]]:
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.cloud.service import CloudFederationService

        return CloudFederationService(session).list_external_vaults()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.post("/replications")
def create_replication(request: ReplicationCreateRequest) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.cloud.service import CloudFederationService

        svc = CloudFederationService(session)
        return svc.create_replication(
            name=request.name, target_cluster=request.target_cluster,
            replication_mode=request.replication_mode,
            path_filter=request.path_filter, created_by=request.created_by,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/replications")
def list_replications() -> List[Dict[str, Any]]:
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.cloud.service import CloudFederationService

        return CloudFederationService(session).list_replications()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()
