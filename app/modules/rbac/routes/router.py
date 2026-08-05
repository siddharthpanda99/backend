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


class OrgPolicyRequest(BaseModel):
    default_role_ids: Optional[List[int]] = None
    enforce_role_inheritance: Optional[bool] = None
    max_roles_per_user: Optional[int] = None
    allow_guests: Optional[bool] = None
    allow_custom_roles: Optional[bool] = None
    denied_permissions: Optional[List[str]] = None


class ViewPermissionGrantRequest(BaseModel):
    view_id: str
    view_type: str = "saved_filter"
    user_id: Optional[int] = None
    role_id: Optional[int] = None
    workspace_id: Optional[str] = None
    access_level: str = "read"


class DashboardPermissionGrantRequest(BaseModel):
    dashboard_id: str
    user_id: Optional[int] = None
    role_id: Optional[int] = None
    workspace_id: Optional[str] = None
    access_level: str = "read"


# ---------------------------------------------------------------------------
# Lazy service loaders
# ---------------------------------------------------------------------------
def _get_db_session():
    from sqlmodel import Session
    from common_lib.modules.integration.adapters.database_adapter import get_db_port
    engine = get_db_port().get_engine()
    return Session(engine)


def _get_rbac_service():
    from common_lib.modules.rbac.service import RBACService
    return RBACService()


def _get_org_policy_svc(session):
    from common_lib.modules.rbac.organization_policy_service import OrganizationPolicyService
    return OrganizationPolicyService(session)


def _get_view_perm_svc(session):
    from common_lib.modules.rbac.view_permission_service import ViewPermissionService
    return ViewPermissionService(session)


def _get_dashboard_perm_svc(session):
    from common_lib.modules.rbac.dashboard_permission_service import DashboardPermissionService
    return DashboardPermissionService(session)


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


# ---------------------------------------------------------------------------
# Organization Policy endpoints (Domain 01.08)
# ---------------------------------------------------------------------------

@router.get("/org-policies/{org_id}")
async def get_org_policy(org_id: str) -> Dict[str, Any]:
    """Get the RBAC policy for an organization."""
    session = _get_db_session()
    try:
        svc = _get_org_policy_svc(session)
        result = svc.get_org_policy_summary(org_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()



@router.put("/org-policies/{org_id}")
async def update_org_policy(org_id: str, request: OrgPolicyRequest) -> Dict[str, Any]:
    """Create or update the RBAC policy for an organization."""
    session = _get_db_session()
    try:
        svc = _get_org_policy_svc(session)
        data = request.model_dump(exclude_unset=True)
        result = svc.create_or_update_policy(org_id, data)
        return {"policy": svc.get_org_policy_summary(org_id), "message": "Policy updated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()



@router.delete("/org-policies/{org_id}")
async def delete_org_policy(org_id: str) -> Dict[str, Any]:
    """Delete the RBAC policy for an organization (reverts to defaults)."""
    session = _get_db_session()
    try:
        svc = _get_org_policy_svc(session)
        svc.delete_policy(org_id)
        return {"success": True, "message": "Policy deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()



@router.post("/org-policies/{org_id}/deny-permission")
async def deny_org_permission(org_id: str, permission_name: str) -> Dict[str, Any]:
    """Deny a permission org-wide."""
    session = _get_db_session()
    try:
        svc = _get_org_policy_svc(session)
        svc.deny_permission(org_id, permission_name)
        return {"success": True, "message": f"Permission '{permission_name}' denied for org {org_id}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()



@router.post("/org-policies/{org_id}/allow-permission")
async def allow_org_permission(org_id: str, permission_name: str) -> Dict[str, Any]:
    """Remove a permission from the org-wide deny list."""
    session = _get_db_session()
    try:
        svc = _get_org_policy_svc(session)
        svc.allow_permission(org_id, permission_name)
        return {"success": True, "message": f"Permission '{permission_name}' allowed for org {org_id}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()



@router.get("/org-policies/{org_id}/effective-permissions/{role_id}")
async def get_effective_role_permissions(org_id: str, role_id: int) -> Dict[str, Any]:
    """Get the effective permissions for a role in an org, considering overrides."""
    session = _get_db_session()
    try:
        svc = _get_org_policy_svc(session)
        perms = svc.get_effective_role_permissions(org_id, role_id)
        return {"org_id": org_id, "role_id": role_id, "permissions": perms}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()



# ---------------------------------------------------------------------------
# View Permissions endpoints (Domain 14.09)
# ---------------------------------------------------------------------------

@router.post("/view-permissions/grant")
async def grant_view_permission(request: ViewPermissionGrantRequest) -> Dict[str, Any]:
    """Grant access to a view for a user, role, or workspace."""
    session = _get_db_session()
    try:
        svc = _get_view_perm_svc(session)
        result = svc.grant_access(
            view_id=request.view_id,
            view_type=request.view_type,
            user_id=request.user_id,
            role_id=request.role_id,
            workspace_id=request.workspace_id,
            access_level=request.access_level,
        )
        return {"id": result.id, "message": "Access granted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()



@router.post("/view-permissions/revoke")
async def revoke_view_permission(
    view_id: str,
    user_id: Optional[int] = None,
    role_id: Optional[int] = None,
    workspace_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Revoke access to a view."""
    session = _get_db_session()
    try:
        svc = _get_view_perm_svc(session)
        result = svc.revoke_access(view_id, user_id=user_id, role_id=role_id, workspace_id=workspace_id)
        return {"success": result, "message": "Access revoked" if result else "Not found"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()



@router.post("/view-permissions/check")
async def check_view_access(
    view_id: str,
    user_id: int,
    required_level: str = "read",
    user_roles: Optional[List[int]] = None,
    workspace_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Check if a user has the required access level for a view."""
    session = _get_db_session()
    try:
        svc = _get_view_perm_svc(session)
        result = svc.check_access(
            view_id=view_id,
            user_id=user_id,
            user_roles=user_roles,
            workspace_id=workspace_id,
            required_level=required_level,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()



@router.get("/view-permissions")
async def list_view_permissions(
    view_id: Optional[str] = None,
    user_id: Optional[int] = None,
) -> Dict[str, Any]:
    """List view permissions with optional filters."""
    session = _get_db_session()
    try:
        svc = _get_view_perm_svc(session)
        perms = svc.list_view_permissions(view_id=view_id, user_id=user_id)
        return {"permissions": [p.model_dump() for p in perms], "count": len(perms)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()



# ---------------------------------------------------------------------------
# Dashboard Permissions endpoints (Domain 20.08)
# ---------------------------------------------------------------------------

@router.post("/dashboard-permissions/grant")
async def grant_dashboard_permission(request: DashboardPermissionGrantRequest) -> Dict[str, Any]:
    """Grant access to a dashboard."""
    session = _get_db_session()
    try:
        svc = _get_dashboard_perm_svc(session)
        result = svc.grant_access(
            dashboard_id=request.dashboard_id,
            user_id=request.user_id,
            role_id=request.role_id,
            workspace_id=request.workspace_id,
            access_level=request.access_level,
        )
        return {"id": result.id, "message": "Access granted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()



@router.post("/dashboard-permissions/revoke")
async def revoke_dashboard_permission(
    dashboard_id: str,
    user_id: Optional[int] = None,
    role_id: Optional[int] = None,
    workspace_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Revoke access to a dashboard."""
    session = _get_db_session()
    try:
        svc = _get_dashboard_perm_svc(session)
        result = svc.revoke_access(dashboard_id, user_id=user_id, role_id=role_id, workspace_id=workspace_id)
        return {"success": result, "message": "Access revoked" if result else "Not found"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()



@router.post("/dashboard-permissions/check")
async def check_dashboard_access(
    dashboard_id: str,
    user_id: int,
    required_level: str = "read",
    user_roles: Optional[List[int]] = None,
    workspace_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Check if a user has the required access level for a dashboard."""
    session = _get_db_session()
    try:
        svc = _get_dashboard_perm_svc(session)
        result = svc.check_access(
            dashboard_id=dashboard_id,
            user_id=user_id,
            user_roles=user_roles,
            workspace_id=workspace_id,
            required_level=required_level,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()



@router.get("/dashboard-permissions")
async def list_dashboard_permissions(
    dashboard_id: Optional[str] = None,
    user_id: Optional[int] = None,
) -> Dict[str, Any]:
    """List dashboard permissions with optional filters."""
    session = _get_db_session()
    try:
        svc = _get_dashboard_perm_svc(session)
        perms = svc.list_dashboard_permissions(dashboard_id=dashboard_id, user_id=user_id)
        return {"permissions": [p.model_dump() for p in perms], "count": len(perms)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()



# ---------------------------------------------------------------------------
# Include sub-routers (including field_security_routes.py)
# ---------------------------------------------------------------------------

from app.modules.rbac.routes.field_security_routes import router as field_security_router
router.include_router(field_security_router)


# ---------------------------------------------------------------------------
# Include sub-routers
# ---------------------------------------------------------------------------

from app.modules.rbac.routes.policy_routes import router as policy_router
router.include_router(policy_router)

from app.modules.rbac.routes.integrations_routes import router as integrations_router
router.include_router(integrations_router)

from app.modules.rbac.routes.guest_routes import router as guest_router
router.include_router(guest_router)

from app.modules.rbac.routes.plugins_routes import router as plugins_router
router.include_router(plugins_router)

from app.modules.rbac.routes.testing_routes import router as testing_router
router.include_router(testing_router)

from app.modules.rbac.routes.debug_routes import router as debug_router
router.include_router(debug_router)
from app.modules.rbac.routes.tenancy_routes import router as tenancy_router
router.include_router(tenancy_router)

from app.modules.rbac.routes.sessions_routes import router as sessions_router
router.include_router(sessions_router)

from app.modules.rbac.routes.delegation_routes import router as delegation_router
router.include_router(delegation_router)

from app.modules.rbac.routes.audit_routes import router as audit_router
router.include_router(audit_router)

from app.modules.rbac.routes.machine_auth_routes import router as machine_auth_router
router.include_router(machine_auth_router)

from app.modules.rbac.routes.api_routes import router as api_router
router.include_router(api_router)

from app.modules.rbac.routes.ownership_routes import router as ownership_router
router.include_router(ownership_router)

from app.modules.rbac.routes.cache_routes import router as cache_router
router.include_router(cache_router)

from app.modules.rbac.routes.hardening_routes import router as hardening_router
router.include_router(hardening_router)


