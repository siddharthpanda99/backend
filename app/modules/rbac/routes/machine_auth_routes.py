"""RBAC Machine Auth API routes — SSOT 23, 24."""
from __future__ import annotations
import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/machine-auth", tags=["rbac-machine-auth"])

def _get_db_session():
    from sqlmodel import Session
    from common_lib.modules.integration.adapters.database_adapter import get_db_port
    engine = get_db_port().get_engine()
    return Session(engine)


class APIKeyCreateReq(BaseModel):
    user_id: int
    name: str
    scopes: Optional[list[str]] = None
    expires_in_days: int = 365

@router.post("/api-keys")
def create_api_key(req: APIKeyCreateReq):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.agent_apikey_service import APIKeyService
        api_key, key = APIKeyService(session).create(name=req.name, owner_user_id=req.user_id, scopes=req.scopes, expires_in_days=req.expires_in_days)
        return {"id": api_key.id, "key": key, "name": api_key.name, "key_prefix": api_key.key_prefix}
    except Exception as e: raise HTTPException(500, str(e))
    finally: session.close()

@router.get("/api-keys/user/{user_id}")
def list_api_keys(user_id: int):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.agent_apikey_service import APIKeyService
        keys = APIKeyService(session).list_user_keys(user_id)
        return {"keys": [{"id": k.id, "name": k.name, "key_prefix": k.key_prefix, "scopes": k.scopes} for k in keys], "total": len(keys)}
    except Exception as e: raise HTTPException(500, str(e))
    finally: session.close()

@router.post("/api-keys/{kid}/revoke")
def revoke_api_key(kid: int):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.agent_apikey_service import APIKeyService
        APIKeyService(session).revoke(kid)
        return {"success": True, "key_id": kid}
    except Exception as e: raise HTTPException(500, str(e))
    finally: session.close()

@router.post("/validate")
def validate_api_key(token: str):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.agent_apikey_service import APIKeyService
        api_key = APIKeyService(session).validate(token)
        if not api_key: raise HTTPException(401, "Invalid or expired API key")
        return {"valid": True, "id": api_key.id, "owner_user_id": api_key.owner_user_id}
    except HTTPException: raise
    except Exception as e: raise HTTPException(500, str(e))
    finally: session.close()
