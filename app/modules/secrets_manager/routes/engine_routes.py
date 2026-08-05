"""Secrets Manager Engines — FastAPI routes for secret engine providers."""

from __future__ import annotations

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from pydantic import BaseModel

from common_lib.modules.data_storage.database.connection import get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/secrets/engines", tags=["secrets-engines"])


class RegisterEngineRequest(BaseModel):
    name: str
    engine_type: str
    mount_path: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    max_lease_ttl: int = 86400
    default_lease_ttl: int = 3600


class RecordHealthRequest(BaseModel):
    is_healthy: bool
    latency_ms: float = 0.0
    error_message: Optional[str] = None


@router.get("")
def list_engines(
    engine_type: Optional[str] = None,
    status: Optional[str] = None,
    session: Session = Depends(get_session),
):
    """List registered secret engines."""
    from common_lib.modules.secrets_manager.engines.service import EngineRegistryService
    svc = EngineRegistryService(session)
    return {"engines": svc.list_engines(engine_type=engine_type, status=status)}


@router.post("")
def register_engine(data: RegisterEngineRequest, session: Session = Depends(get_session)):
    """Register a new secret engine provider."""
    from common_lib.modules.secrets_manager.engines.service import EngineRegistryService
    svc = EngineRegistryService(session)
    return svc.register_engine(
        name=data.name,
        engine_type=data.engine_type,
        mount_path=data.mount_path,
        display_name=data.display_name,
        description=data.description,
        max_lease_ttl=data.max_lease_ttl,
        default_lease_ttl=data.default_lease_ttl,
    )


@router.get("/{engine_id}")
def get_engine(engine_id: str, session: Session = Depends(get_session)):
    """Get engine details."""
    from common_lib.modules.secrets_manager.engines.service import EngineRegistryService
    svc = EngineRegistryService(session)
    engine = svc.get_engine(engine_id=engine_id)
    if not engine:
        raise HTTPException(status_code=404, detail="Engine not found")
    return engine


@router.post("/{engine_id}/enable")
def enable_engine(engine_id: str, session: Session = Depends(get_session)):
    """Enable a disabled engine."""
    from common_lib.modules.secrets_manager.engines.service import EngineRegistryService
    svc = EngineRegistryService(session)
    if not svc.enable_engine(engine_id):
        raise HTTPException(status_code=404, detail="Engine not found")
    return {"success": True}


@router.post("/{engine_id}/disable")
def disable_engine(engine_id: str, session: Session = Depends(get_session)):
    """Disable an engine."""
    from common_lib.modules.secrets_manager.engines.service import EngineRegistryService
    svc = EngineRegistryService(session)
    if not svc.disable_engine(engine_id):
        raise HTTPException(status_code=404, detail="Engine not found")
    return {"success": True}


@router.delete("/{engine_id}")
def remove_engine(engine_id: str, session: Session = Depends(get_session)):
    """Remove an engine registration."""
    from common_lib.modules.secrets_manager.engines.service import EngineRegistryService
    svc = EngineRegistryService(session)
    if not svc.remove_engine(engine_id):
        raise HTTPException(status_code=404, detail="Engine not found")
    return {"success": True}


@router.post("/{engine_id}/health")
def record_engine_health(engine_id: str, data: RecordHealthRequest,
                         session: Session = Depends(get_session)):
    """Record a health check result for an engine."""
    from common_lib.modules.secrets_manager.engines.service import EngineRegistryService
    svc = EngineRegistryService(session)
    return svc.record_health(engine_id, data.is_healthy,
                             latency_ms=data.latency_ms,
                             error_message=data.error_message)


@router.get("/{engine_id}/health")
def get_engine_health(engine_id: str, session: Session = Depends(get_session)):
    """Get latest health status for an engine."""
    from common_lib.modules.secrets_manager.engines.service import EngineRegistryService
    svc = EngineRegistryService(session)
    health = svc.get_engine_health(engine_id)
    if not health:
        raise HTTPException(status_code=404, detail="Engine not found")
    return health
