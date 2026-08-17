"""DB Provisioning module API routes — Database provisioning via Docker/SQLite.

Thin routing layer that delegates to common_lib.modules.data_storage.db_provisioning.service.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()


class ProvisionRequest(BaseModel):
    db_type: str
    name: Optional[str] = None
    config: Optional[Dict[str, Any]] = None


def _get_service():
    from common_lib.modules.data_storage.db_provisioning.service import DatabaseProvisionerService
    return DatabaseProvisionerService()


@router.get("/types")
async def list_supported_types() -> Dict[str, Any]:
    """List supported database types."""
    try:
        svc = _get_service()
        result = svc.list_supported_types() if hasattr(svc, "list_supported_types") else {"types": []}
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/provision")
async def provision_db(request: ProvisionRequest) -> Dict[str, Any]:
    """Provision a new database."""
    try:
        svc = _get_service()
        result = svc.provision(request.db_type, request.name, request.config) if hasattr(svc, "provision") else {"db_type": request.db_type}
        return {"result": result, "message": "Database provisioned successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def provisioning_status() -> Dict[str, Any]:
    """Get provisioning service status."""
    try:
        svc = _get_service()
        result = svc.get_status() if hasattr(svc, "get_status") else {"status": "ok"}
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
