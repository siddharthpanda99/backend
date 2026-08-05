"""Plugin SDK — FastAPI routes (SSOT §23)."""

from typing import Optional
from fastapi import APIRouter, Depends
from sqlmodel import Session
from app.modules.secrets_manager.deps import get_sm_session
from common_lib.modules.secrets_manager.plugins.service import PluginService

router = APIRouter()


@router.get("/secrets/plugins", summary="List plugins")
def list_plugins(plugin_type: Optional[str] = None, session: Session = Depends(get_sm_session)):
    svc = PluginService(session)
    return svc.list_plugins(plugin_type=plugin_type)


@router.post("/secrets/plugins", summary="Register plugin")
def register_plugin(body: dict, session: Session = Depends(get_sm_session)):
    svc = PluginService(session)
    return svc.register_plugin(**body)


@router.get("/secrets/plugins/{plugin_id}", summary="Get plugin manifest")
def get_plugin(plugin_id: str, session: Session = Depends(get_sm_session)):
    svc = PluginService(session)
    return svc.get_plugin(plugin_id=plugin_id)


@router.post("/secrets/plugins/{plugin_id}/verify", summary="Verify plugin integrity")
def verify_plugin(plugin_id: str, session: Session = Depends(get_sm_session)):
    svc = PluginService(session)
    return svc.verify_plugin_integrity(plugin_id=plugin_id)


@router.post("/secrets/plugins/{plugin_id}/disable", summary="Disable plugin")
def disable_plugin(plugin_id: str, session: Session = Depends(get_sm_session)):
    svc = PluginService(session)
    return {"ok": svc.disable_plugin(plugin_id=plugin_id)}
