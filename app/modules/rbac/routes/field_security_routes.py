"""RBAC Field Security API routes — SSOT 09.

Extracted from router.py to provide dedicated endpoints for field-level
security rule management, permission checks, and user overrides.
"""

from __future__ import annotations
import logging
from typing import Any, Dict, Optional, List
from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/field-security", tags=["rbac-field-security"])


def _get_db_session():
    from sqlmodel import Session
    from common_lib.modules.integration.adapters.database_adapter import get_db_port
    engine = get_db_port().get_engine()
    return Session(engine)


@router.post("/rules")
def create_rule(
    resource_type: str,
    field_key: str,
    role_name: str,
    access_level: str = "editable",
    workspace_id: Optional[str] = None,
    project_id: Optional[str] = None,
    conditions: Optional[str] = None,
    created_by: Optional[str] = None,
):
    """Create a field security rule."""
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.field_security_service import FieldSecurityService
        import json
        data = {
            "resource_type": resource_type,
            "field_key": field_key,
            "role_name": role_name,
            "access_level": access_level,
            "workspace_id": workspace_id,
            "project_id": project_id,
            "conditions": json.loads(conditions) if conditions else None,
            "created_by": created_by,
        }
        rule = FieldSecurityService(session).create_rule(data={k: v for k, v in data.items() if v is not None})
        return {"id": rule.id, "resource_type": rule.resource_type, "field_key": rule.field_key, "access_level": rule.access_level}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        session.close()


@router.get("/rules")
def list_rules(
    resource_type: Optional[str] = None,
    role_name: Optional[str] = None,
    workspace_id: Optional[str] = None,
):
    """List field security rules with optional filters."""
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.field_security_service import FieldSecurityService
        rules = FieldSecurityService(session).list_rules(
            resource_type=resource_type, role_name=role_name, workspace_id=workspace_id,
        )
        return {
            "rules": [{"id": r.id, "resource_type": r.resource_type, "field_key": r.field_key,
                       "access_level": r.access_level, "role_name": r.role_name} for r in rules],
            "total": len(rules),
        }
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        session.close()


@router.put("/rules/{rule_id}")
def update_rule(rule_id: str, access_level: str, conditions: Optional[str] = None):
    """Update a field security rule."""
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.field_security_service import FieldSecurityService
        import json
        data = {
            "access_level": access_level,
            "conditions": json.loads(conditions) if conditions else None,
        }
        rule = FieldSecurityService(session).update_rule(rule_id, data={k: v for k, v in data.items() if v is not None})
        if not rule:
            raise HTTPException(404, "Field security rule not found")
        return {"id": rule.id, "access_level": rule.access_level}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        session.close()


@router.delete("/rules/{rule_id}")
def delete_rule(rule_id: str):
    """Delete a field security rule."""
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.field_security_service import FieldSecurityService
        ok = FieldSecurityService(session).delete_rule(rule_id)
        if not ok:
            raise HTTPException(404, "Field security rule not found")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        session.close()


@router.post("/check")
def check_field_access(
    user_id: int, resource_type: str, field_key: str,
    role_name: Optional[str] = None, workspace_id: Optional[str] = None,
):
    """Check what access level a user has for a specific field."""
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.field_security_service import FieldSecurityService
        result = FieldSecurityService(session).check_field_access(
            user_id=user_id, resource_type=resource_type,
            field_key=field_key, role_name=role_name, workspace_id=workspace_id,
        )
        return result
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        session.close()


@router.post("/overrides")
def create_override(
    user_id: int, resource_type: str, field_key: str,
    access_level: str = "editable", rule_id: Optional[str] = None,
    reason: Optional[str] = None, granted_by: Optional[int] = None,
):
    """Create a user-level override for a field security rule."""
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.field_security_service import FieldSecurityService
        data = {
            "user_id": user_id,
            "resource_type": resource_type,
            "field_key": field_key,
            "access_level": access_level,
            "rule_id": rule_id,
            "reason": reason,
            "granted_by": granted_by,
        }
        override = FieldSecurityService(session).create_override(data={k: v for k, v in data.items() if v is not None})
        return {"id": override.id, "user_id": override.user_id, "access_level": override.access_level}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        session.close()


@router.post("/filter")
def filter_fields(
    user_id: int, resource_type: str, fields: List[str],
    role_name: Optional[str] = None, workspace_id: Optional[str] = None,
):
    """Filter a list of fields to only those visible to the user."""
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.field_security_service import FieldSecurityService
        visible = FieldSecurityService(session).filter_visible_fields(
            user_id=user_id, resource_type=resource_type,
            fields=fields, role_name=role_name, workspace_id=workspace_id,
        )
        return {"visible_fields": visible, "hidden": len(fields) - len(visible)}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        session.close()
