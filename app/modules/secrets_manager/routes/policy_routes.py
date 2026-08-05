"""Secrets Manager Policy API routes — SSOT 02: Policy Engine.

Thin routing layer for policy CRUD, evaluation, binding, and checking.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/policies", tags=["secrets-manager-policy"])


def _get_db_session():
    from sqlmodel import Session
    from common_lib.modules.integration.adapters.database_adapter import get_db_port
    engine = get_db_port().get_engine()
    return Session(engine)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class PolicyCreateRequest(BaseModel):
    name: str
    rules: List[dict]
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    tenant_id: Optional[str] = None
    created_by: Optional[str] = None


class PolicyBindRequest(BaseModel):
    policy_name: str
    secret_id: Optional[str] = None
    path: Optional[str] = None
    priority: int = 100


class PolicyEvaluateRequest(BaseModel):
    action: str
    resource: str
    secret_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = None


class PolicyCheckRequest(BaseModel):
    secret_name: str
    action: str = "read_value"
    context: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("")
def create_policy(request: PolicyCreateRequest) -> Dict[str, Any]:
    """Create a new policy with rules."""
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.policy.service import PolicyEngine

        engine = PolicyEngine(session=session)
        return engine.create_policy(
            name=request.name,
            rules=request.rules,
            description=request.description,
            tags=request.tags,
            tenant_id=request.tenant_id,
            created_by=request.created_by,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/{name}")
def get_policy(name: str) -> Dict[str, Any]:
    """Get a policy by name with parsed rules."""
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.policy.service import PolicyEngine

        engine = PolicyEngine(session=session)
        result = engine.get_policy(name=name)
        if result is None:
            raise HTTPException(status_code=404, detail=f"Policy '{name}' not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("")
def list_policies(tenant_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """List all active policies."""
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.policy.service import PolicyEngine

        engine = PolicyEngine(session=session)
        return engine.list_policies(tenant_id=tenant_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.delete("/{name}")
def delete_policy(name: str) -> Dict[str, Any]:
    """Soft-delete a policy."""
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.policy.service import PolicyEngine

        engine = PolicyEngine(session=session)
        success = engine.delete_policy(name=name)
        if not success:
            raise HTTPException(status_code=404, detail=f"Policy '{name}' not found")
        return {"deleted": True, "name": name}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.post("/bind")
def bind_policy(request: PolicyBindRequest) -> Dict[str, Any]:
    """Bind a policy to a secret or path."""
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.policy.service import PolicyEngine

        engine = PolicyEngine(session=session)
        result = engine.bind_policy(
            policy_name=request.policy_name,
            secret_id=request.secret_id,
            path=request.path,
            priority=request.priority,
        )
        if result is None:
            raise HTTPException(
                status_code=404, detail=f"Policy '{request.policy_name}' not found"
            )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/bindings")
def list_bindings(
    secret_id: Optional[str] = None,
    path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """List policy bindings."""
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.policy.service import PolicyEngine

        engine = PolicyEngine(session=session)
        return engine.list_bindings(secret_id=secret_id, path=path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.post("/evaluate")
def evaluate_policy(request: PolicyEvaluateRequest) -> Dict[str, Any]:
    """Evaluate whether an action on a resource is allowed."""
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.policy.service import PolicyEngine

        engine = PolicyEngine(session=session)
        return engine.evaluate(
            action=request.action,
            resource=request.resource,
            secret_id=request.secret_id,
            context=request.context,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.post("/check-access")
def check_secret_access(request: PolicyCheckRequest) -> Dict[str, Any]:
    """Quick check if an action on a secret is allowed."""
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.policy.service import PolicyEngine

        engine = PolicyEngine(session=session)
        allowed = engine.check_secret_access(
            secret_name=request.secret_name,
            action=request.action,
            context=request.context,
        )
        return {
            "allowed": allowed,
            "secret_name": request.secret_name,
            "action": request.action,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()
