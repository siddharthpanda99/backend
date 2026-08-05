"""
Field Security and Guest Access — REST Routes for PM-specific RBAC.

Provides endpoints for:
- Field security rule CRUD (per-field visibility/editability per role)
- Field security user overrides
- Guest access management (grant, revoke, list, extend)
"""

from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlmodel import Session

from common_lib.modules.data_storage.database.connection import get_session
from app.modules.auth.dependencies import require_permission, require_tenant

router = APIRouter()


def _get_field_service(session: Session):
    from common_lib.modules.rbac.field_security_service import FieldSecurityService
    return FieldSecurityService(session)


def _get_guest_service(session: Session):
    from common_lib.modules.rbac.guest_access_service import GuestAccessService
    return GuestAccessService(session)


# ===========================================================================
# Field Security Rules
# ===========================================================================

@router.get(
    "/field-rules",
    dependencies=[
        Depends(require_tenant),
        require_permission("field.read", "*", "field"),
    ],
)
def list_field_rules(
    workspace_id: Optional[str] = Query(None),
    project_id: Optional[str] = Query(None),
    resource_type: Optional[str] = Query(None),
    role_name: Optional[str] = Query(None),
    session: Session = Depends(get_session),
):
    """List field security rules with optional filters."""
    svc = _get_field_service(session)
    rules = svc.list_rules(
        workspace_id=workspace_id,
        project_id=project_id,
        resource_type=resource_type,
        role_name=role_name,
    )
    return {"rules": [r.model_dump() for r in rules], "total": len(rules)}


@router.get(
    "/field-rules/{rule_id}",
    dependencies=[
        Depends(require_tenant),
        require_permission("field.read", "*", "field"),
    ],
)
def get_field_rule(rule_id: str, session: Session = Depends(get_session)):
    """Get a single field security rule."""
    svc = _get_field_service(session)
    rule = svc.get_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")
    return rule.model_dump()


@router.post(
    "/field-rules",
    status_code=201,
    dependencies=[
        Depends(require_tenant),
        require_permission("field.write", "*", "field"),
    ],
)
def create_field_rule(
    resource_type: str = Query(...),
    field_key: str = Query(...),
    role_name: str = Query(...),
    access_level: str = Query("read_only"),
    workspace_id: Optional[str] = Query(None),
    project_id: Optional[str] = Query(None),
    created_by: Optional[str] = Query(None),
    session: Session = Depends(get_session),
):
    """Create a field security rule."""
    svc = _get_field_service(session)
    data = {
        "resource_type": resource_type,
        "field_key": field_key,
        "role_name": role_name,
        "access_level": access_level,
        "workspace_id": workspace_id,
        "project_id": project_id,
        "created_by": created_by,
    }
    rule = svc.create_rule(data)
    return rule.model_dump()


@router.put(
    "/field-rules/{rule_id}",
    dependencies=[
        Depends(require_tenant),
        require_permission("field.write", "*", "field"),
    ],
)
def update_field_rule(
    rule_id: str,
    access_level: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    session: Session = Depends(get_session),
):
    """Update a field security rule."""
    svc = _get_field_service(session)
    data = {}
    if access_level is not None:
        data["access_level"] = access_level
    if is_active is not None:
        data["is_active"] = is_active
    rule = svc.update_rule(rule_id, data)
    if not rule:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")
    return rule.model_dump()


@router.delete(
    "/field-rules/{rule_id}",
    dependencies=[
        Depends(require_tenant),
        require_permission("field.write", "*", "field"),
    ],
)
def delete_field_rule(rule_id: str, session: Session = Depends(get_session)):
    """Delete a field security rule."""
    svc = _get_field_service(session)
    if not svc.delete_rule(rule_id):
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")
    return {"success": True, "rule_id": rule_id}


# ===========================================================================
# Field Access Checks
# ===========================================================================

@router.get(
    "/field-access",
    dependencies=[
        Depends(require_tenant),
        require_permission("field.read", "*", "field"),
    ],
)
def get_field_access(
    user_id: int = Query(...),
    resource_type: str = Query(...),
    field_key: str = Query(...),
    workspace_id: Optional[str] = Query(None),
    project_id: Optional[str] = Query(None),
    session: Session = Depends(get_session),
):
    """Get effective field access level for a user on a specific field."""
    svc = _get_field_service(session)
    level = svc.get_field_access(
        user_id=user_id,
        resource_type=resource_type,
        field_key=field_key,
        workspace_id=workspace_id,
        project_id=project_id,
    )
    return {"access_level": level}


@router.post(
    "/field-access/filter",
    dependencies=[
        Depends(require_tenant),
        require_permission("field.read", "*", "field"),
    ],
)
def filter_visible_fields(
    user_id: int = Query(...),
    resource_type: str = Query(...),
    fields: Dict[str, Any] = Body(..., description="JSON object with field keys and values"),
    workspace_id: Optional[str] = Query(None),
    project_id: Optional[str] = Query(None),
    session: Session = Depends(get_session),
):
    """Filter visible fields for a user on a resource type.
    
    Body should be a JSON object with field keys as property names.
    Returns the filtered fields dict plus lists of read-only and hidden fields.
    """
    svc = _get_field_service(session)
    return svc.filter_visible_fields(
        user_id=user_id,
        resource_type=resource_type,
        fields=fields,
        workspace_id=workspace_id,
        project_id=project_id,
    )


# ===========================================================================
# Guest Access Management
# ===========================================================================

@router.get(
    "/guests",
    dependencies=[
        Depends(require_tenant),
        require_permission("role.manage", "*", "role"),
    ],
)
def list_guest_users(
    workspace_id: str = Query(...),
    include_expired: bool = Query(False),
    session: Session = Depends(get_session),
):
    """List all guest users in a workspace."""
    svc = _get_guest_service(session)
    guests = svc.list_guest_users(workspace_id=workspace_id, include_expired=include_expired)
    return {"guests": guests, "total": len(guests)}


@router.post(
    "/guests",
    status_code=201,
    dependencies=[
        Depends(require_tenant),
        require_permission("role.manage", "*", "role"),
    ],
)
def grant_guest_access(
    user_id: int = Query(...),
    workspace_id: str = Query(...),
    granted_by: Optional[int] = Query(None),
    expires_in_days: int = Query(30),
    session: Session = Depends(get_session),
):
    """Grant guest-level access to a user."""
    from datetime import datetime, timedelta
    svc = _get_guest_service(session)
    expires_at = datetime.utcnow() + timedelta(days=expires_in_days)
    result = svc.grant_guest_access(
        user_id=user_id,
        workspace_id=workspace_id,
        granted_by=granted_by,
        expires_at=expires_at,
    )
    return {
        "success": True,
        "user_id": result.user_id,
        "role": "guest",
        "expires_at": result.expires_at.isoformat() if result.expires_at else None,
    }


@router.post(
    "/guests/{user_id}/revoke",
    dependencies=[
        Depends(require_tenant),
        require_permission("role.manage", "*", "role"),
    ],
)
def revoke_guest_access(
    user_id: int,
    reason: Optional[str] = Query(None),
    session: Session = Depends(get_session),
):
    """Revoke guest access for a user."""
    svc = _get_guest_service(session)
    success = svc.revoke_guest_access(user_id=user_id, reason=reason or "")
    return {"success": success}


@router.post(
    "/guests/{user_id}/extend",
    dependencies=[
        Depends(require_tenant),
        require_permission("role.manage", "*", "role"),
    ],
)
def extend_guest_access(
    user_id: int,
    workspace_id: str = Query(...),
    additional_days: int = Query(30),
    session: Session = Depends(get_session),
):
    """Extend guest access by additional days."""
    svc = _get_guest_service(session)
    success = svc.extend_guest_access(
        user_id=user_id,
        workspace_id=workspace_id,
        additional_days=additional_days,
    )
    return {"success": success}
