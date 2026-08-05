"""Secrets Manager Proxy API routes — SSOT 09: App SDK / CLI / Agent / CSI."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/proxy", tags=["secrets-manager-proxy"])


def _get_db_session():
    from sqlmodel import Session
    from common_lib.modules.integration.adapters.database_adapter import get_db_port
    engine = get_db_port().get_engine()
    return Session(engine)


class ApiKeyCreateRequest(BaseModel):
    name: str
    role_id: Optional[str] = None
    scopes: Optional[List[str]] = None
    ttl_seconds: Optional[int] = None
    tenant_id: Optional[str] = None
    created_by: Optional[str] = None


class ClientConfigCreateRequest(BaseModel):
    name: str
    client_type: str = "rest"
    base_url: Optional[str] = None
    api_key_id: Optional[str] = None
    timeout_seconds: int = 30
    options: Optional[dict] = None
    created_by: Optional[str] = None


class AgentConfigCreateRequest(BaseModel):
    name: str
    agent_type: str = "sidecar"
    api_key_id: Optional[str] = None
    cache_ttl_seconds: int = 300
    created_by: Optional[str] = None


class ProxyRouteCreateRequest(BaseModel):
    name: str
    source_path: str
    target_path: str
    route_type: str = "env"
    agent_id: Optional[str] = None

class ApiKeyValidateRequest(BaseModel):
    raw_key: str


@router.post("/api-keys")
def create_api_key(request: ApiKeyCreateRequest) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.proxy.service import ProxyService

        svc = ProxyService(session)
        return svc.create_api_key(
            name=request.name, role_id=request.role_id, scopes=request.scopes,
            ttl_seconds=request.ttl_seconds, tenant_id=request.tenant_id,
            created_by=request.created_by,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/api-keys")
def list_api_keys() -> List[Dict[str, Any]]:
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.proxy.service import ProxyService

        return ProxyService(session).list_api_keys()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.post("/api-keys/validate")
def validate_api_key(request: ApiKeyValidateRequest) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.proxy.service import ProxyService

        result = ProxyService(session).validate_api_key(raw_key=request.raw_key)
        if result is None:
            raise HTTPException(status_code=401, detail="Invalid API key")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.post("/api-keys/{name}/revoke")
def revoke_api_key(name: str) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.proxy.service import ProxyService

        success = ProxyService(session).revoke_api_key(name=name)
        if not success:
            raise HTTPException(status_code=404, detail="Key not found")
        return {"revoked": True, "name": name}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.post("/client-configs")
def create_client_config(request: ClientConfigCreateRequest) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.proxy.service import ProxyService

        svc = ProxyService(session)
        return svc.create_client_config(
            name=request.name, client_type=request.client_type,
            base_url=request.base_url, api_key_id=request.api_key_id,
            timeout_seconds=request.timeout_seconds, options=request.options,
            created_by=request.created_by,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/client-configs")
def list_client_configs() -> List[Dict[str, Any]]:
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.proxy.service import ProxyService

        return ProxyService(session).list_client_configs()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.post("/agent-configs")
def create_agent_config(request: AgentConfigCreateRequest) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.proxy.service import ProxyService

        svc = ProxyService(session)
        return svc.create_agent_config(
            name=request.name, agent_type=request.agent_type,
            api_key_id=request.api_key_id,
            cache_ttl_seconds=request.cache_ttl_seconds,
            created_by=request.created_by,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/agent-configs")
def list_agent_configs() -> List[Dict[str, Any]]:
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.proxy.service import ProxyService

        return ProxyService(session).list_agent_configs()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.post("/proxy-routes")
def create_proxy_route(request: ProxyRouteCreateRequest) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.proxy.service import ProxyService

        svc = ProxyService(session)
        return svc.create_proxy_route(
            name=request.name, source_path=request.source_path,
            target_path=request.target_path, route_type=request.route_type,
            agent_id=request.agent_id,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/proxy-routes")
def list_proxy_routes() -> List[Dict[str, Any]]:
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.proxy.service import ProxyService

        return ProxyService(session).list_proxy_routes()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()
