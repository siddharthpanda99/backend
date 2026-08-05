"""Notification Channel Routes — Provider config CRUD, circuit breaker, health checks (SSOT §22)."""

from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from sqlmodel import Session

from common_lib.modules.notification.channels.service import CircuitBreakerService

router = APIRouter(prefix="/notification/providers", tags=["notification-providers"])


def _get_session():
    """Dependency: get DB session."""
    from common_lib.database import get_session
    session = next(get_session())
    try:
        yield session
    finally:
        session.close()


@router.get("/configs")
async def list_provider_configs(
    channel_type: Optional[str] = None,
    session: Session = Depends(_get_session),
):
    """List provider configurations, optionally filtered by channel type."""
    svc = CircuitBreakerService(session)
    return {"configs": svc.list_provider_configs(channel_type=channel_type)}


@router.post("/configs")
async def create_provider_config(
    name: str,
    channel_type: str,
    provider_class: str,
    credential_ref: Optional[str] = None,
    config_json: Optional[dict] = None,
    session: Session = Depends(_get_session),
):
    """Create a new provider configuration."""
    svc = CircuitBreakerService(session)
    result = svc.create_provider_config(
        name=name,
        channel_type=channel_type,
        provider_class=provider_class,
        credential_ref=credential_ref,
        config_json=config_json,
    )
    return {"config": result}


@router.get("/configs/{config_id}")
async def get_provider_config(config_id: str, session: Session = Depends(_get_session)):
    """Get details of a specific provider configuration."""
    svc = CircuitBreakerService(session)
    state = svc.get_state(config_id)
    if not state:
        raise HTTPException(status_code=404, detail="Provider config not found")
    return {"config": state}


@router.get("/circuit/{config_id}")
async def get_circuit_breaker_state(config_id: str, session: Session = Depends(_get_session)):
    """Get circuit breaker state for a provider."""
    svc = CircuitBreakerService(session)
    state = svc.get_state(config_id)
    if not state:
        raise HTTPException(status_code=404, detail="Provider config not found")
    return {"circuit_breaker": state}


@router.post("/circuit/{config_id}/success")
async def record_circuit_success(config_id: str, session: Session = Depends(_get_session)):
    """Record a delivery success for circuit breaker tracking."""
    svc = CircuitBreakerService(session)
    result = svc.record_success(config_id)
    return result


@router.post("/circuit/{config_id}/failure")
async def record_circuit_failure(
    config_id: str,
    error_message: Optional[str] = None,
    session: Session = Depends(_get_session),
):
    """Record a delivery failure for circuit breaker tracking."""
    svc = CircuitBreakerService(session)
    result = svc.record_failure(config_id, error_message=error_message)
    return result


@router.get("/circuit/{config_id}/check")
async def check_circuit(config_id: str, session: Session = Depends(_get_session)):
    """Check if circuit allows requests for a provider."""
    svc = CircuitBreakerService(session)
    allowed = svc.check_circuit(config_id)
    return {"allowed": allowed, "provider_config_id": config_id}


@router.get("/circuit/{config_id}/history")
async def get_circuit_history(
    config_id: str,
    limit: int = 20,
    session: Session = Depends(_get_session),
):
    """Get circuit breaker state transition history."""
    svc = CircuitBreakerService(session)
    history = svc.get_history(config_id, limit=limit)
    return {"history": history}
