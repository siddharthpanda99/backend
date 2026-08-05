"""RBAC Policy Engine API routes — SSOT 05, 06, 07, 10, 15.

Thin routing layer for policy check, simulate, ABAC condition evaluation,
ReBAC relationship management, and explicit deny operations.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/policies", tags=["rbac-policies"])


# ---------------------------------------------------------------------------


def _get_db_session():
    from sqlmodel import Session
    from common_lib.modules.integration.adapters.database_adapter import get_db_port
    engine = get_db_port().get_engine()
    return Session(engine)


# ---------------------------------------------------------------------------


class PolicyCheckRequest(BaseModel):
    user_id: int
    resource_type: str
    action: str
    resource_id: Optional[str] = None
    org_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    rbac_allowed: bool = False


class PolicySimulateRequest(BaseModel):
    user_id: int
    resource_type: str
    action: str
    context: Optional[Dict[str, Any]] = None


class ExplicitDenyRequest(BaseModel):
    user_id: int
    resource_type: str
    action: str
    org_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = None


class ABACEvaluateRequest(BaseModel):
    condition_ids: List[str]
    context: Dict[str, Dict[str, Any]]
    logic: str = "and"


class ReBACCheckRequest(BaseModel):
    subject_type: str
    subject_id: str
    relation: str
    object_type: str
    object_id: str
    transitive: bool = False
    max_depth: int = 5


class ReBACGrantRequest(BaseModel):
    subject_type: str
    subject_id: str
    relation: str
    object_type: str
    object_id: str
    org_id: Optional[str] = None
    transitive: bool = False
    granted_by: Optional[str] = None
    expires_at: Optional[str] = None


class ReBACRevokeRequest(BaseModel):
    subject_type: str
    subject_id: str
    relation: str
    object_type: str
    object_id: str
    reason: Optional[str] = None


# ---------------------------------------------------------------------------


@router.post("/check")
async def policy_check(request: PolicyCheckRequest) -> Dict[str, Any]:
    """Full policy evaluation combining RBAC, ABAC, ReBAC, and explicit deny."""
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.policies.service import PolicyEngine
        engine = PolicyEngine(session=session)
        result = engine.evaluate(
            user_id=request.user_id,
            resource_type=request.resource_type,
            action=request.action,
            resource_id=request.resource_id,
            org_id=request.org_id,
            context=request.context,
            rbac_allowed=request.rbac_allowed,
        )
        return {
            "allowed": result.allowed,
            "decision": result.decision.value,
            "reasons": result.reasons,
            "denied_by": result.denied_by,
            "applied_rules": result.applied_rules,
            "abac_matched": result.abac_matched,
            "rebac_matched": result.rebac_matched,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.post("/simulate")
async def policy_simulate(request: PolicySimulateRequest) -> Dict[str, Any]:
    """Simulate policy evaluation — dry run with reasoning chain."""
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.policies.service import PolicyEngine
        engine = PolicyEngine(session=session)
        return engine.simulate(
            user_id=request.user_id,
            resource_type=request.resource_type,
            action=request.action,
            context=request.context,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.post("/deny-check")
async def explicit_deny_check(request: ExplicitDenyRequest) -> Dict[str, Any]:
    """Check if a user has an explicit deny rule."""
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.policies.service import ExplicitDenyResolver
        resolver = ExplicitDenyResolver(session=session)
        is_denied, rule_name = resolver.has_explicit_deny(
            request.user_id, request.resource_type, request.action,
            request.org_id, request.context,
        )
        return {"is_denied": is_denied, "rule_name": rule_name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


# ---------------------------------------------------------------------------


@router.post("/abac/evaluate")
async def abac_evaluate(request: ABACEvaluateRequest) -> Dict[str, Any]:
    """Evaluate ABAC conditions against attributes."""
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.policies.service import ABACEvaluator
        evaluator = ABACEvaluator(session=session)
        allowed = evaluator.evaluate_rule_conditions(
            request.condition_ids, request.logic, request.context,
        )
        return {"allowed": allowed, "condition_ids": request.condition_ids}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


# ---------------------------------------------------------------------------


@router.post("/rebac/check")
async def rebac_check(request: ReBACCheckRequest) -> Dict[str, Any]:
    """Check if a relationship exists between subject and object."""
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.policies.service import ReBACEvaluator
        evaluator = ReBACEvaluator(session=session)
        if request.transitive:
            has = evaluator.resolve_transitive(
                request.subject_type, request.subject_id, request.relation,
                request.object_type, request.object_id, request.max_depth,
            )
        else:
            has = evaluator.has_relation(
                request.subject_type, request.subject_id, request.relation,
                request.object_type, request.object_id,
            )
        return {
            "has_relation": has,
            "subject_type": request.subject_type,
            "subject_id": request.subject_id,
            "relation": request.relation,
            "object_type": request.object_type,
            "object_id": request.object_id,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.post("/rebac/grant")
async def rebac_grant(request: ReBACGrantRequest) -> Dict[str, Any]:
    """Grant a ReBAC relationship (idempotent, race-condition safe)."""
    session = _get_db_session()
    try:
        from datetime import datetime as dt
        from common_lib.modules.rbac.policies.service import ReBACEvaluator
        evaluator = ReBACEvaluator(session=session)
        expiry = dt.fromisoformat(request.expires_at) if request.expires_at else None
        rel = evaluator.grant_relation(
            subject_type=request.subject_type,
            subject_id=request.subject_id,
            relation=request.relation,
            object_type=request.object_type,
            object_id=request.object_id,
            org_id=request.org_id,
            transitive=request.transitive,
            granted_by=request.granted_by,
            expires_at=expiry,
        )
        return {
            "id": rel.id,
            "subject_type": rel.subject_type,
            "subject_id": rel.subject_id,
            "relation": rel.relation,
            "object_type": rel.object_type,
            "object_id": rel.object_id,
            "message": "Relation granted",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.post("/rebac/revoke")
async def rebac_revoke(request: ReBACRevokeRequest) -> Dict[str, Any]:
    """Soft-revoke a ReBAC relationship."""
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.policies.service import ReBACEvaluator
        evaluator = ReBACEvaluator(session=session)
        success = evaluator.revoke_relation(
            request.subject_type, request.subject_id, request.relation,
            request.object_type, request.object_id, request.reason,
        )
        return {"success": success, "message": "Relation revoked" if success else "Not found"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/rebac/relations")
async def rebac_list_relations(
    subject_type: Optional[str] = None,
    subject_id: Optional[str] = None,
    object_type: Optional[str] = None,
    object_id: Optional[str] = None,
    relation: Optional[str] = None,
    limit: int = 50,
) -> Dict[str, Any]:
    """List ReBAC relationships with optional filters."""
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.policies.service import ReBACEvaluator
        evaluator = ReBACEvaluator(session=session)
        if subject_type and subject_id:
            rels = evaluator.get_related_objects(
                subject_type, subject_id, relation, object_type, limit,
            )
        elif object_type and object_id:
            rels = evaluator.get_related_subjects(object_type, object_id, relation)
        else:
            from sqlmodel import select
            from common_lib.modules.rbac.policies.models import ReBACRelation
            query = select(ReBACRelation).where(
                ReBACRelation.revoked_at == None  # noqa: E711
            )
            if subject_type:
                query = query.where(ReBACRelation.subject_type == subject_type)
            if object_type:
                query = query.where(ReBACRelation.object_type == object_type)
            if relation:
                query = query.where(ReBACRelation.relation == relation)
            query = query.limit(limit)
            rels = list(session.execute(query).scalars().all())
        return {
            "relations": [
                {
                    "id": r.id,
                    "subject_type": r.subject_type,
                    "subject_id": r.subject_id,
                    "relation": r.relation,
                    "object_type": r.object_type,
                    "object_id": r.object_id,
                }
                for r in rels
            ],
            "total": len(rels),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()
