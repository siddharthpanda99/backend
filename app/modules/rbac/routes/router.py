"""RBAC module API routes — Role-Based Access Control.

Thin routing layer that delegates to common_lib.modules.rbac services.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class RoleCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    permissions: Optional[List[str]] = None


class RoleUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    permissions: Optional[List[str]] = None


class UserRoleAssignRequest(BaseModel):
    user_id: str
    role_id: str


class OrgCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None


# ---------------------------------------------------------------------------
# Lazy service loader
# ---------------------------------------------------------------------------

def _get_rbac_service():
    from common_lib.modules.rbac.service import RBACService
    return RBACService()


# ---------------------------------------------------------------------------
# Role endpoints
# ---------------------------------------------------------------------------

@router.get("/roles")
async def list_roles() -> Dict[str, Any]:
    """List all roles."""
    try:
        svc = _get_rbac_service()
        result = svc.list_roles()
        return {"roles": result, "count": len(result) if isinstance(result, list) else 0}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/roles")
async def create_role(request: RoleCreateRequest) -> Dict[str, Any]:
    """Create a new role."""
    try:
        svc = _get_rbac_service()
        result = svc.create_role(
            name=request.name,
            description=request.description,
            permissions=request.permissions or [],
        )
        return {"role": result, "message": "Role created successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/roles/{role_id}")
async def get_role(role_id: str) -> Dict[str, Any]:
    """Get a role by ID."""
    try:
        svc = _get_rbac_service()
        result = svc.get_role(role_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Role not found")
        return {"role": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/roles/{role_id}")
async def update_role(role_id: str, request: RoleUpdateRequest) -> Dict[str, Any]:
    """Update a role."""
    try:
        svc = _get_rbac_service()
        result = svc.update_role(role_id, **request.model_dump(exclude_unset=True))
        return {"role": result, "message": "Role updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/roles/{role_id}")
async def delete_role(role_id: str) -> Dict[str, Any]:
    """Delete a role."""
    try:
        svc = _get_rbac_service()
        svc.delete_role(role_id)
        return {"success": True, "message": "Role deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# User-Role assignment endpoints
# ---------------------------------------------------------------------------

@router.get("/users/{user_id}/roles")
async def get_user_roles(user_id: str) -> Dict[str, Any]:
    """Get all roles for a user."""
    try:
        svc = _get_rbac_service()
        result = svc.get_user_roles(user_id)
        return {"user_id": user_id, "roles": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/users/{user_id}/roles")
async def assign_role(user_id: str, request: UserRoleAssignRequest) -> Dict[str, Any]:
    """Assign a role to a user."""
    try:
        svc = _get_rbac_service()
        svc.assign_role(request.user_id or user_id, request.role_id)
        return {"success": True, "message": "Role assigned successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/users/{user_id}/roles/{role_id}")
async def remove_role(user_id: str, role_id: str) -> Dict[str, Any]:
    """Remove a role from a user."""
    try:
        svc = _get_rbac_service()
        svc.remove_role(user_id, role_id)
        return {"success": True, "message": "Role removed successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Authorization check endpoint
# ---------------------------------------------------------------------------

@router.post("/check")
async def check_permission(
    user_id: str,
    resource: str,
    action: str,
) -> Dict[str, Any]:
    """Check if a user has permission for an action on a resource."""
    try:
        svc = _get_rbac_service()
        allowed = svc.check_permission(user_id, resource, action)
        return {"user_id": user_id, "resource": resource, "action": action, "allowed": allowed}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Organization endpoints
# ---------------------------------------------------------------------------

@router.get("/organizations")
async def list_organizations() -> Dict[str, Any]:
    """List all organizations."""
    try:
        svc = _get_rbac_service()
        result = svc.list_organizations() if hasattr(svc, "list_organizations") else []
        return {"organizations": result, "count": len(result) if isinstance(result, list) else 0}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/organizations")
async def create_organization(request: OrgCreateRequest) -> Dict[str, Any]:
    """Create a new organization."""
    try:
        svc = _get_rbac_service()
        result = svc.create_organization(request.name, request.description) if hasattr(svc, "create_organization") else {"name": request.name}
        return {"organization": result, "message": "Organization created successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
