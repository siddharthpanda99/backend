from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from common_lib.modules.governance.auth.service import get_auth_service

router = APIRouter(prefix="/auth", tags=["Governance - Auth"])


class IssueTokenRequest(BaseModel):
    agent_id: str
    name: str = ""
    capabilities: list[str] = []
    ttl_hours: int = 0


class RevokeTokenRequest(BaseModel):
    token: str


class IssueApiKeyRequest(BaseModel):
    agent_id: str
    label: str = ""


class RevokeApiKeyRequest(BaseModel):
    key: str


class RegisterMtlsRequest(BaseModel):
    agent_id: str
    fingerprint: str
    metadata: dict = {}


@router.get("/tokens")
def list_tokens():
    svc = get_auth_service()
    return svc._tokens if hasattr(svc, "_tokens") else []


@router.post("/tokens")
def issue_token(body: IssueTokenRequest):
    svc = get_auth_service()
    token = svc.issue_token(body.agent_id, body.name, body.capabilities, body.ttl_hours)
    return {
        "token": token,
        "agent_id": body.agent_id,
        "name": body.name,
        "revoked": False,
    }


@router.post("/tokens/revoke")
def revoke_token(body: RevokeTokenRequest):
    svc = get_auth_service()
    svc.revoke_token(body.token)
    return {"success": True}


@router.get("/api-keys")
def list_api_keys():
    svc = get_auth_service()
    return svc._api_keys if hasattr(svc, "_api_keys") else []


@router.post("/api-keys")
def issue_api_key(body: IssueApiKeyRequest):
    svc = get_auth_service()
    key = svc.issue_api_key(body.agent_id, body.label)
    return {
        "key": key,
        "agent_id": body.agent_id,
        "label": body.label,
        "revoked": False,
    }


@router.post("/api-keys/revoke")
def revoke_api_key(body: RevokeApiKeyRequest):
    svc = get_auth_service()
    svc.revoke_api_key(body.key)
    return {"success": True}


@router.get("/mtls")
def list_mtls():
    svc = get_auth_service()
    return svc._mtls_creds if hasattr(svc, "_mtls_creds") else []


@router.post("/mtls")
def register_mtls(body: RegisterMtlsRequest):
    svc = get_auth_service()
    svc.register_mtls_credential(body.agent_id, body.fingerprint, body.metadata)
    return {
        "fingerprint": body.fingerprint,
        "agent_id": body.agent_id,
        "metadata": body.metadata,
    }
