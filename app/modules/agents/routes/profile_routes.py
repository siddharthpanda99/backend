"""Agent Profile routes — thin wrappers around TeammateRegistryService."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session as SQLSession

from common_lib.modules.data_storage.database.connection import (
    get_session as get_db_session,
)
from common_lib.modules.agents.models.profile_models import AgentStatus
from common_lib.modules.agents.services.teammate_registry_service import (
    TeammateRegistryService,
)

router = APIRouter()
svc = TeammateRegistryService()


def _or_404(result, detail="Resource not found"):
    if result is None:
        raise HTTPException(status_code=404, detail=detail)
    return result


def _handle_profile_error(e: ValueError):
    msg = str(e)
    if "not found" in msg.lower():
        raise HTTPException(status_code=404, detail=msg)
    raise HTTPException(status_code=409, detail=msg)


# ── Request / Response schemas ──────────────────────────────────────────────────


class CreateProfileRequest(BaseModel):
    display_name: str
    avatar_url: Optional[str] = None
    description: str = ""
    roles: List[str] = []
    capabilities: List[str] = []
    status: str = AgentStatus.OFFLINE.value
    runtime_info: dict = {}
    concurrency_limit: int = 5
    metadata: dict = {}


class UpdateProfileRequest(BaseModel):
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    description: Optional[str] = None
    roles: Optional[List[str]] = None
    capabilities: Optional[List[str]] = None
    status: Optional[str] = None
    runtime_info: Optional[dict] = None
    concurrency_limit: Optional[int] = None
    metadata: Optional[dict] = None


class UpdateStatusRequest(BaseModel):
    status: str
    runtime_info: Optional[dict] = None


class ProfileResponse(BaseModel):
    id: str
    display_name: str
    avatar_url: Optional[str]
    description: str
    roles: list
    capabilities: list
    status: str
    runtime_info: dict
    concurrency_limit: int
    metadata_json: dict
    created_at: Optional[str]
    updated_at: Optional[str]
    last_seen_at: Optional[str]


def _profile_to_response(p) -> ProfileResponse:
    return ProfileResponse(
        id=p.id,
        display_name=p.display_name,
        avatar_url=p.avatar_url,
        description=p.description or "",
        roles=p.roles or [],
        capabilities=p.capabilities or [],
        status=p.status,
        runtime_info=p.runtime_info or {},
        concurrency_limit=p.concurrency_limit,
        metadata_json=p.metadata_json or {},
        created_at=p.created_at.isoformat() if p.created_at else None,
        updated_at=p.updated_at.isoformat() if p.updated_at else None,
        last_seen_at=p.last_seen_at.isoformat() if p.last_seen_at else None,
    )


# ── Endpoints ──────────────────────────────────────────────────────────────────


@router.post("/", response_model=dict)
def create_profile(
    body: CreateProfileRequest,
    db: SQLSession = Depends(get_db_session),
):
    profile = svc.create_profile(
        display_name=body.display_name,
        avatar_url=body.avatar_url,
        description=body.description,
        roles=body.roles,
        capabilities=body.capabilities,
        status=body.status,
        runtime_info=body.runtime_info,
        concurrency_limit=body.concurrency_limit,
        metadata=body.metadata,
        db=db,
    )
    return {"success": True, "data": _profile_to_response(profile).model_dump()}


@router.get("/", response_model=dict)
def list_profiles(
    status: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: SQLSession = Depends(get_db_session),
):
    profiles = svc.list_profiles(
        status=status, role=role, limit=limit, offset=offset, db=db
    )
    return {
        "success": True,
        "data": [_profile_to_response(p).model_dump() for p in profiles],
    }


@router.get("/available", response_model=dict)
def get_available_agents(db: SQLSession = Depends(get_db_session)):
    profiles = svc.get_available_agents(db=db)
    return {
        "success": True,
        "data": [_profile_to_response(p).model_dump() for p in profiles],
    }


@router.get("/role/{role}", response_model=dict)
def get_by_role(role: str, db: SQLSession = Depends(get_db_session)):
    profiles = svc.get_by_role(role, db=db)
    return {
        "success": True,
        "data": [_profile_to_response(p).model_dump() for p in profiles],
    }


@router.get("/{profile_id}", response_model=dict)
def get_profile(profile_id: str, db: SQLSession = Depends(get_db_session)):
    profile = _or_404(
        svc.get_profile(profile_id, db=db), f"Profile {profile_id} not found"
    )
    return {"success": True, "data": _profile_to_response(profile).model_dump()}


@router.patch("/{profile_id}", response_model=dict)
def update_profile(
    profile_id: str,
    body: UpdateProfileRequest,
    db: SQLSession = Depends(get_db_session),
):
    try:
        profile = svc.update_profile(
            profile_id,
            display_name=body.display_name,
            avatar_url=body.avatar_url,
            description=body.description,
            roles=body.roles,
            capabilities=body.capabilities,
            status=body.status,
            runtime_info=body.runtime_info,
            concurrency_limit=body.concurrency_limit,
            metadata=body.metadata,
            db=db,
        )
    except ValueError as e:
        _handle_profile_error(e)
    return {"success": True, "data": _profile_to_response(profile).model_dump()}


@router.put("/{profile_id}/status", response_model=dict)
def update_status(
    profile_id: str,
    body: UpdateStatusRequest,
    db: SQLSession = Depends(get_db_session),
):
    try:
        profile = svc.update_status(
            profile_id, body.status, runtime_info=body.runtime_info, db=db
        )
    except ValueError as e:
        _handle_profile_error(e)
    return {"success": True, "data": _profile_to_response(profile).model_dump()}


@router.delete("/{profile_id}", response_model=dict)
def delete_profile(profile_id: str, db: SQLSession = Depends(get_db_session)):
    try:
        svc.delete_profile(profile_id, db=db)
    except ValueError as e:
        _handle_profile_error(e)
    return {"success": True, "data": {"deleted": profile_id}}
