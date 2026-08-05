"""
PM Module — Field Security Dependencies.

Provides FastAPI dependencies that integrate RBAC field-level security
with PM route handlers. Each endpoint can optionally apply field filtering
to response data based on the caller's roles.

Usage in routes:
    from app.modules.project_management.field_security_deps import apply_field_security

    @router.get("/{issue_id}")
    def get_issue(issue_id: str, ...):
        issue = svc.get_issue(issue_id)
        return apply_field_security(request, session, "issue", issue, project_id=issue.project_id)
"""

import logging
from typing import Any, Dict, Optional, Union
from fastapi import Request
from sqlmodel import Session

logger = logging.getLogger(__name__)

# Fields that are NEVER filtered out (structural/identity fields)
_IMMUTABLE_FIELDS = {
    "id", "key", "project_id", "created_at", "updated_at", "created_by",
    "issue_type_id", "sprint_id", "identifier",
}

# Fields that are commonly sensitive and subject to field security
_SENSITIVE_FIELDS = {
    "cost_estimate", "budget", "actual_cost", "revenue_impact",
    "story_points", "time_estimate", "time_spent",
    "priority", "assignee_id", "labels",
}


def get_field_security_service(session: Session):
    """Get a FieldSecurityService instance."""
    from common_lib.modules.rbac.field_security_service import FieldSecurityService
    return FieldSecurityService(session)


def _get_user_id(request: Request) -> Optional[int]:
    """Extract user ID from the request's auth state.

    Returns None if no user is authenticated (allows unauthenticated
    endpoints to skip field security).
    """
    identity = getattr(request.state, "identity", None)
    if identity and hasattr(identity, "subject_id"):
        try:
            return int(identity.subject_id)
        except (ValueError, TypeError):
            return None

    # Fallback: try to get from the auth header
    try:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            from common_lib.modules.auth.security import decode_access_token
            token = auth_header[7:]
            payload = decode_access_token(token)
            user_id = payload.get("sub") or payload.get("user_id")
            if user_id is not None:
                return int(user_id)
    except Exception:
        pass

    return None


def _get_user_roles(request: Request) -> list[str]:
    """Extract user roles from the request's auth state."""
    identity = getattr(request.state, "identity", None)
    if identity and hasattr(identity, "roles"):
        return identity.roles or []
    return []


def filter_single_response(
    request: Request,
    session: Session,
    resource_type: str,
    data: Dict[str, Any],
    project_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Apply field security to a single resource response.

    Filters out hidden fields and marks read-only fields.

    Args:
        request: The FastAPI request (for user identity)
        session: DB session
        resource_type: "issue", "project", "sprint", or "release"
        data: The resource dict (from model_dump())
        project_id: Project scope for per-project rules
        workspace_id: Workspace scope for workspace-wide rules

    Returns:
        Filtered dict with field_security metadata attached
    """
    user_id = _get_user_id(request)
    if user_id is None:
        return data  # No auth — skip filtering

    # Only filter sensitive fields, keep structural fields intact
    fields_to_check = {
        k: v for k, v in data.items()
        if k in _SENSITIVE_FIELDS or k not in _IMMUTABLE_FIELDS
    }

    if not fields_to_check:
        return data

    svc = get_field_security_service(session)
    result = svc.filter_visible_fields(
        user_id=user_id,
        resource_type=resource_type,
        fields=fields_to_check,
        workspace_id=workspace_id,
        project_id=project_id,
    )

    # Merge: keep immutable fields, add filtered fields, add metadata
    filtered = {}
    for k, v in data.items():
        if k in _IMMUTABLE_FIELDS:
            filtered[k] = v
        elif k in result["fields"]:
            filtered[k] = result["fields"][k]
        # Hidden fields are simply omitted

    # Attach field security metadata for frontend consumption (stripped before Pydantic validation)
    filtered["_field_security"] = {
        "read_only_fields": result["read_only_fields"],
        "hidden_fields": result["hidden_fields"],
        "resource_type": resource_type,
    }

    return filtered


def strip_field_security_metadata(data: dict) -> dict:
    """Remove _field_security metadata before Pydantic model_validate()."""
    cleaned = {k: v for k, v in data.items() if k != "_field_security"}
    return cleaned


def filter_list_response(
    request: Request,
    session: Session,
    resource_type: str,
    items: list[Dict[str, Any]],
    project_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> list[Dict[str, Any]]:
    """Apply field security to a list of resource responses.

    Args:
        request: The FastAPI request
        session: DB session
        resource_type: "issue", "project", "sprint", or "release"
        items: List of resource dicts
        project_id: Project scope
        workspace_id: Workspace scope

    Returns:
        List of filtered dicts
    """
    user_id = _get_user_id(request)
    if user_id is None:
        return items  # No auth — skip filtering

    svc = get_field_security_service(session)

    # Collect all field keys across all items (for batch resolution)
    all_field_keys = set()
    for item in items:
        all_field_keys.update(
            k for k in item.keys()
            if k in _SENSITIVE_FIELDS or k not in _IMMUTABLE_FIELDS
        )

    if not all_field_keys:
        return items

    # Get access levels for all fields at once
    access_map = svc.get_resource_fields_access(
        user_id=user_id,
        resource_type=resource_type,
        field_keys=list(all_field_keys),
        workspace_id=workspace_id,
        project_id=project_id,
    )

    hidden = [k for k, v in access_map.items() if v == "hidden"]
    read_only = [k for k, v in access_map.items() if v == "read_only"]

    # Apply filtering to each item
    filtered_items = []
    for item in items:
        filtered = {}
        for k, v in item.items():
            if k in _IMMUTABLE_FIELDS:
                filtered[k] = v
            elif k in hidden:
                continue  # Skip hidden fields
            else:
                filtered[k] = v
        filtered_items.append(filtered)

    return filtered_items


def check_field_editable(
    request: Request,
    session: Session,
    resource_type: str,
    field_key: str,
    project_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> bool:
    """Check if the current user can edit a specific field.

    Returns True if the field is editable, False if hidden or read-only.
    Raises no exceptions — safe to use in route handlers.
    """
    user_id = _get_user_id(request)
    if user_id is None:
        return True  # No auth — allow (auth deps handle that)

    svc = get_field_security_service(session)
    level = svc.get_field_access(
        user_id=user_id,
        resource_type=resource_type,
        field_key=field_key,
        workspace_id=workspace_id,
        project_id=project_id,
    )
    return level == "editable"


def reject_if_field_read_only(
    request: Request,
    session: Session,
    resource_type: str,
    field_key: str,
    project_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> None:
    """Raise HTTP 403 if the field is not editable for the current user.

    Use this in PATCH/PUT handlers to reject updates to read-only fields.
    """
    from fastapi import HTTPException

    if not check_field_editable(request, session, resource_type, field_key, project_id, workspace_id):
        raise HTTPException(
            status_code=403,
            detail=f"Field '{field_key}' is not editable for your role",
        )
