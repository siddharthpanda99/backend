"""FastAPI routes for RBAC Plugin Permission Discovery — SSOT 31."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/plugins", tags=["rbac-plugins"])


def _get_db_session():
    from sqlmodel import Session
    from common_lib.modules.integration.adapters.database_adapter import get_db_port
    engine = get_db_port().get_engine()
    return Session(engine)


class RegisterPermissionsRequest(BaseModel):
    plugin_name: str
    plugin_version: str
    permissions: List[Dict[str, Any]]


class DiscoverRequest(BaseModel):
    module_path: str


class SyncRequest(BaseModel):
    module_paths: List[str]


@router.post("/register")
async def register_plugin_permissions(request: RegisterPermissionsRequest) -> Dict[str, Any]:
    """Register permissions from a plugin. Creates Permission records in the DB."""
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.plugins.service import DynamicPermissionDiscoveryService
        svc = DynamicPermissionDiscoveryService(session)
        count = svc.register_plugin_permissions(
            request.plugin_name, request.plugin_version, request.permissions,
        )
        return {"new_permissions": count, "plugin_name": request.plugin_name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.post("/discover")
async def discover_module_permissions(request: DiscoverRequest) -> Dict[str, Any]:
    """Auto-discover permissions from a Python module by scanning for PERMISSIONS constants."""
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.plugins.service import DynamicPermissionDiscoveryService
        svc = DynamicPermissionDiscoveryService(session)
        discovered = svc.discover_module_permissions(request.module_path)
        return {"discovered": discovered, "count": len(discovered)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/coverage")
async def get_permission_coverage() -> Dict[str, Any]:
    """Get permission coverage summary across all registered plugins."""
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.plugins.service import DynamicPermissionDiscoveryService
        svc = DynamicPermissionDiscoveryService(session)
        return svc.get_permission_coverage()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.post("/sync")
async def sync_discovered_to_db(request: SyncRequest) -> Dict[str, Any]:
    """Auto-discover permissions from modules and register them in the DB."""
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.plugins.service import DynamicPermissionDiscoveryService
        svc = DynamicPermissionDiscoveryService(session)
        return svc.sync_discovered_to_db(request.module_paths)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()
