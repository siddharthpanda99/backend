"""HITL Policy Builder — Thin FastAPI routes.

All business logic lives in common_lib.modules.hitl.service.
Routes only handle HTTP concerns: parsing, status codes, response shaping.
"""

from fastapi import APIRouter, HTTPException, Query
from common_lib.modules.hitl.service import get_hitl_policy_service
from common_lib.modules.hitl.schemas import (
    HITLPolicyCreate,
    HITLPolicyUpdate,
    HITLPolicyDetailResponse,
    HITLPolicyListResponse,
    PolicyStats,
    ToggleResponse,
)

router = APIRouter(prefix="/policies", tags=["HITL - Policies"])


@router.get("", response_model=HITLPolicyListResponse)
def list_policies(
    search: str = Query(default="", max_length=256),
    enabled: bool = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    service = get_hitl_policy_service()
    return service.list_policies(
        search=search or None,
        enabled=enabled,
        page=page,
        page_size=page_size,
    )


@router.get("/stats", response_model=PolicyStats)
def get_stats():
    service = get_hitl_policy_service()
    return service.get_stats()


@router.get("/{policy_id}", response_model=HITLPolicyDetailResponse)
def get_policy(policy_id: str):
    service = get_hitl_policy_service()
    result = service.get_policy(policy_id)
    if not result:
        raise HTTPException(status_code=404, detail="Policy not found")
    return result


@router.post("", response_model=HITLPolicyDetailResponse, status_code=201)
def create_policy(body: HITLPolicyCreate):
    service = get_hitl_policy_service()
    return service.create_policy(body)


@router.put("/{policy_id}", response_model=HITLPolicyDetailResponse)
def update_policy(policy_id: str, body: HITLPolicyUpdate):
    service = get_hitl_policy_service()
    result = service.update_policy(policy_id, body)
    if not result:
        raise HTTPException(status_code=404, detail="Policy not found")
    return result


@router.delete("/{policy_id}", status_code=204)
def delete_policy(policy_id: str):
    service = get_hitl_policy_service()
    if not service.delete_policy(policy_id):
        raise HTTPException(status_code=404, detail="Policy not found")


@router.patch("/{policy_id}/toggle", response_model=ToggleResponse)
def toggle_policy(policy_id: str):
    service = get_hitl_policy_service()
    result = service.toggle_policy(policy_id)
    if not result:
        raise HTTPException(status_code=404, detail="Policy not found")
    return result


@router.post(
    "/{policy_id}/duplicate", response_model=HITLPolicyDetailResponse, status_code=201
)
def duplicate_policy(policy_id: str):
    service = get_hitl_policy_service()
    result = service.duplicate_policy(policy_id)
    if not result:
        raise HTTPException(status_code=404, detail="Policy not found")
    return result
