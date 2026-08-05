"""Secrets Manager Kubernetes API routes — SSOT 10: K8s / DevOps / CI/CD."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/kubernetes", tags=["secrets-manager-kubernetes"])


def _get_db_session():
    from sqlmodel import Session
    from common_lib.modules.integration.adapters.database_adapter import get_db_port
    engine = get_db_port().get_engine()
    return Session(engine)


class K8sAuthCreateRequest(BaseModel):
    name: str
    cluster_name: str
    api_server_url: str = ""
    namespace: str = "default"
    created_by: Optional[str] = None


class CsiDriverCreateRequest(BaseModel):
    name: str
    driver_name: str = "secrets.csi.example.com"
    namespace: str = "default"
    created_by: Optional[str] = None


class OperatorCreateRequest(BaseModel):
    name: str
    operator_type: str = "sync"
    target_namespace: str = "default"
    created_by: Optional[str] = None


class ExternalSecretCreateRequest(BaseModel):
    name: str
    provider: str = "aws"
    provider_config: Optional[dict] = None
    created_by: Optional[str] = None


@router.post("/auth")
def create_k8s_auth(request: K8sAuthCreateRequest) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.kubernetes.service import KubernetesService

        svc = KubernetesService(session)
        return svc.create_auth_config(
            name=request.name, cluster_name=request.cluster_name,
            api_server_url=request.api_server_url, namespace=request.namespace,
            created_by=request.created_by,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/auth")
def list_k8s_auth() -> List[Dict[str, Any]]:
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.kubernetes.service import KubernetesService

        return KubernetesService(session).list_auth_configs()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.post("/csi-drivers")
def create_csi_driver(request: CsiDriverCreateRequest) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.kubernetes.service import KubernetesService

        svc = KubernetesService(session)
        return svc.create_csi_driver(
            name=request.name, driver_name=request.driver_name,
            namespace=request.namespace, created_by=request.created_by,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/csi-drivers")
def list_csi_drivers() -> List[Dict[str, Any]]:
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.kubernetes.service import KubernetesService

        return KubernetesService(session).list_csi_drivers()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.post("/operators")
def create_operator(request: OperatorCreateRequest) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.kubernetes.service import KubernetesService

        svc = KubernetesService(session)
        return svc.create_operator_config(
            name=request.name, operator_type=request.operator_type,
            target_namespace=request.target_namespace, created_by=request.created_by,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/operators")
def list_operators() -> List[Dict[str, Any]]:
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.kubernetes.service import KubernetesService

        return KubernetesService(session).list_operator_configs()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.post("/external-secrets")
def create_external_secret(request: ExternalSecretCreateRequest) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.kubernetes.service import KubernetesService

        svc = KubernetesService(session)
        return svc.create_external_secret(
            name=request.name, provider=request.provider,
            provider_config=request.provider_config, created_by=request.created_by,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/external-secrets")
def list_external_secrets() -> List[Dict[str, Any]]:
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.kubernetes.service import KubernetesService

        return KubernetesService(session).list_external_secrets()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()
