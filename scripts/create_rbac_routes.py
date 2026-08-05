"""Create 9 missing RBAC route files for submodules that lack API endpoints."""

import os

routes_dir = "app/modules/rbac/routes"

# =========================================================
# 1. tenancy_routes.py — Organization and Team CRUD
# =========================================================
tenancy_routes = '''"""RBAC Tenancy API routes — SSOT 08: Multi-Tenant Scope Boundaries.

Org/team CRUD plus membership management.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tenancy", tags=["rbac-tenancy"])


def _get_db_session():
    from sqlmodel import Session
    from common_lib.modules.integration.adapters.database_adapter import get_db_port
    engine = get_db_port().get_engine()
    return Session(engine)


class OrgCreateRequest(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None


class OrgUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    settings: Optional[dict] = None


class TeamCreateRequest(BaseModel):
    name: str
    slug: str
    org_id: int
    description: Optional[str] = None


class MemberAddRequest(BaseModel):
    user_id: int
    role: str = "member"


# -- Organizations --

@router.post("/orgs")
def create_org(request: OrgCreateRequest) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.tenant_service import OrganizationService
        svc = OrganizationService(session)
        org = svc.create(name=request.name, slug=request.slug,
                         created_by=None, description=request.description)
        return {"id": org.id, "name": org.name, "slug": org.slug}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        session.close()


@router.get("/orgs")
def list_orgs(skip: int = 0, limit: int = 100) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.tenant_service import OrganizationService
        svc = OrganizationService(session)
        orgs = svc.list_orgs(skip=skip, limit=limit)
        return {"organizations": [{"id": o.id, "name": o.name, "slug": o.slug} for o in orgs], "total": len(orgs)}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        session.close()


@router.get("/orgs/{org_id}")
def get_org(org_id: int) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.tenant_service import OrganizationService
        svc = OrganizationService(session)
        org = svc.get_by_id(org_id)
        if not org:
            raise HTTPException(404, "Organization not found")
        return {"id": org.id, "name": org.name, "slug": org.slug, "description": org.description}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        session.close()


@router.put("/orgs/{org_id}")
def update_org(org_id: int, request: OrgUpdateRequest) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.tenant_service import OrganizationService
        svc = OrganizationService(session)
        org = svc.update(org_id, **request.model_dump(exclude_unset=True))
        if not org:
            raise HTTPException(404, "Organization not found")
        return {"id": org.id, "name": org.name, "slug": org.slug}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        session.close()


@router.delete("/orgs/{org_id}")
def delete_org(org_id: int) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.tenant_service import OrganizationService
        svc = OrganizationService(session)
        svc.delete(org_id)
        return {"success": True}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        session.close()


@router.post("/orgs/{org_id}/members")
def add_org_member(org_id: int, request: MemberAddRequest) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.tenant_service import OrganizationService
        svc = OrganizationService(session)
        membership = svc.add_member(org_id, request.user_id, request.role)
        return {"user_id": membership.user_id, "role": membership.role}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        session.close()


@router.delete("/orgs/{org_id}/members/{user_id}")
def remove_org_member(org_id: int, user_id: int) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.tenant_service import OrganizationService
        svc = OrganizationService(session)
        svc.remove_member(org_id, user_id)
        return {"success": True}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        session.close()


@router.get("/orgs/{org_id}/members")
def list_org_members(org_id: int) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.tenant_service import OrganizationService
        svc = OrganizationService(session)
        members = svc.list_members(org_id)
        return {"members": [{"user_id": m.user_id, "role": m.role} for m in members], "total": len(members)}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        session.close()


# -- Teams --

@router.post("/teams")
def create_team(request: TeamCreateRequest) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.tenant_service import TeamServiceRBAC
        svc = TeamServiceRBAC(session)
        team = svc.create(name=request.name, slug=request.slug, org_id=request.org_id)
        return {"id": team.id, "name": team.name, "slug": team.slug, "org_id": team.org_id}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        session.close()


@router.get("/teams")
def list_teams(org_id: Optional[int] = None) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.tenant_service import TeamServiceRBAC
        svc = TeamServiceRBAC(session)
        teams = svc.list_teams(org_id=org_id)
        return {"teams": [{"id": t.id, "name": t.name, "slug": t.slug} for t in teams], "total": len(teams)}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        session.close()


@router.post("/teams/{team_id}/members")
def add_team_member(team_id: int, request: MemberAddRequest) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.tenant_service import TeamServiceRBAC
        svc = TeamServiceRBAC(session)
        membership = svc.add_member(team_id, request.user_id, request.role)
        return {"user_id": membership.user_id, "role": membership.role}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        session.close()


@router.get("/teams/{team_id}/members")
def list_team_members(team_id: int) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.tenant_service import TeamServiceRBAC
        svc = TeamServiceRBAC(session)
        members = svc.list_members(team_id)
        return {"members": [{"user_id": m.user_id, "role": m.role} for m in members], "total": len(members)}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        session.close()
'''

# =========================================================
# 2. sessions_routes.py — Session and MFA endpoints
# =========================================================
sessions_routes = '''"""RBAC Session/MFA API routes — SSOT 11 & 12.

Session create/validate/revoke and MFA setup/verify/disable.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sessions", tags=["rbac-sessions"])


def _get_db_session():
    from sqlmodel import Session
    from common_lib.modules.integration.adapters.database_adapter import get_db_port
    engine = get_db_port().get_engine()
    return Session(engine)


class CreateSessionRequest(BaseModel):
    user_id: int
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    device_info: Optional[dict] = None
    expires_in_hours: int = 24


@router.post("")
def create_session(request: CreateSessionRequest) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.session_mfa_service import SessionService
        svc = SessionService(session)
        db_session, token = svc.create_session(
            user_id=request.user_id,
            ip_address=request.ip_address,
            user_agent=request.user_agent,
            device_info=request.device_info,
            expires_in_hours=request.expires_in_hours,
        )
        return {"session_id": db_session.id, "token": token, "expires_at": db_session.expires_at.isoformat()}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        session.close()


@router.post("/validate")
def validate_session(token: str) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.session_mfa_service import SessionService
        svc = SessionService(session)
        db_session = svc.validate_session(token)
        if not db_session:
            raise HTTPException(401, "Invalid or expired session")
        return {"valid": True, "user_id": db_session.user_id, "session_id": db_session.id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        session.close()


@router.get("/user/{user_id}")
def list_user_sessions(user_id: int) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.session_mfa_service import SessionService
        svc = SessionService(session)
        sessions = svc.list_user_sessions(user_id)
        return {"sessions": [{"id": s.id, "created_at": s.created_at.isoformat(), "is_active": s.is_active} for s in sessions], "total": len(sessions)}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        session.close()


@router.post("/{session_id}/revoke")
def revoke_session(session_id: int, reason: str = "user_request") -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.session_mfa_service import SessionService
        svc = SessionService(session)
        svc.revoke_session(session_id, reason)
        return {"success": True}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        session.close()


@router.post("/user/{user_id}/revoke-all")
def revoke_all_sessions(user_id: int, reason: str = "admin_request") -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.session_mfa_service import SessionService
        svc = SessionService(session)
        count = svc.revoke_all_user_sessions(user_id, reason)
        return {"success": True, "revoked_count": count}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        session.close()


# -- MFA endpoints --


class MFASetupRequest(BaseModel):
    user_id: int


class MFACodeRequest(BaseModel):
    user_id: int
    code: str


@router.post("/mfa/setup")
def mfa_setup(request: MFASetupRequest) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.session_mfa_service import MFAService
        svc = MFAService(session)
        secret, provisioning_uri = svc.setup_totp(request.user_id)
        return {"secret": secret, "provisioning_uri": provisioning_uri}
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        session.close()


@router.post("/mfa/verify")
def mfa_verify(request: MFACodeRequest) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.session_mfa_service import MFAService
        svc = MFAService(session)
        ok = svc.verify_totp(request.user_id, request.code)
        return {"verified": ok}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        session.close()


@router.post("/mfa/disable")
def mfa_disable(request: MFASetupRequest) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.session_mfa_service import MFAService
        svc = MFAService(session)
        svc.disable(request.user_id)
        return {"success": True}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        session.close()


@router.get("/mfa/status/{user_id}")
def mfa_status(user_id: int) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.session_mfa_service import MFAService
        svc = MFAService(session)
        enabled = svc.is_enabled(user_id)
        return {"user_id": user_id, "mfa_enabled": enabled}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        session.close()


@router.post("/mfa/backup-codes")
def mfa_generate_backup_codes(request: MFASetupRequest) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.session_mfa_service import MFAService
        svc = MFAService(session)
        codes = svc.generate_backup_codes(request.user_id)
        return {"codes": codes, "count": len(codes)}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        session.close()
'''

# =========================================================
# 3. delegation_routes.py
# =========================================================
delegation_routes = '''"""RBAC Delegation API routes — SSOT 13.

Delegation and impersonation management.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/delegations", tags=["rbac-delegations"])


def _get_db_session():
    from sqlmodel import Session
    from common_lib.modules.integration.adapters.database_adapter import get_db_port
    engine = get_db_port().get_engine()
    return Session(engine)


class CreateDelegationRequest(BaseModel):
    delegator_user_id: int
    delegatee_user_id: int
    expires_at: str  # ISO datetime
    scope_type: str = "all"
    reason: Optional[str] = None


class EndImpersonationRequest(BaseModel):
    session_id: str


@router.post("")
def create_delegation(request: CreateDelegationRequest) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.delegation.service import DelegationService
        svc = DelegationService(session)
        expires = datetime.fromisoformat(request.expires_at)
        record = svc.create_delegation(
            delegator_user_id=request.delegator_user_id,
            delegatee_user_id=request.delegatee_user_id,
            expires_at=expires,
            scope_type=request.scope_type,
            reason=request.reason,
        )
        return {"delegation_id": record.delegation_id, "expires_at": record.expires_at.isoformat()}
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        session.close()


@router.get("/active-for/{user_id}")
def get_active_delegations(user_id: int) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.delegation.service import DelegationService
        svc = DelegationService(session)
        records = svc.get_active_delegations_for_user(user_id)
        return {"delegations": [{"delegation_id": r.delegation_id, "delegator_user_id": r.delegator_user_id, "expires_at": r.expires_at.isoformat()} for r in records], "total": len(records)}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        session.close()


@router.post("/{delegation_id}/revoke")
def revoke_delegation(delegation_id: str, reason: Optional[str] = None) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.delegation.service import DelegationService
        svc = DelegationService(session)
        svc.revoke_delegation(delegation_id, reason=reason)
        return {"success": True}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        session.close()


@router.get("/summary/{user_id}")
def get_delegation_summary(user_id: int) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.delegation.service import DelegationService
        svc = DelegationService(session)
        return svc.get_delegation_summary(user_id)
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        session.close()


# -- Impersonation --

class StartImpersonationRequest(BaseModel):
    admin_user_id: int
    target_user_id: int
    reason: str


@router.post("/impersonations")
def start_impersonation(request: StartImpersonationRequest) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.delegation.service import ImpersonationService
        svc = ImpersonationService(session)
        log = svc.start_impersonation(request.admin_user_id, request.target_user_id, request.reason)
        return {"session_id": log.session_id, "started_at": log.started_at.isoformat()}
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        session.close()


@router.post("/impersonations/end")
def end_impersonation(request: EndImpersonationRequest) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.delegation.service import ImpersonationService
        svc = ImpersonationService(session)
        svc.end_impersonation(request.session_id)
        return {"success": True}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        session.close()


@router.get("/impersonations/logs")
def list_impersonation_logs(admin_user_id: Optional[int] = None) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.delegation.service import ImpersonationService
        svc = ImpersonationService(session)
        logs = svc.list_impersonation_logs(admin_user_id=admin_user_id)
        return {"logs": [{"session_id": l.session_id, "admin_user_id": l.admin_user_id, "target_user_id": l.target_user_id, "started_at": l.started_at.isoformat(), "is_active": l.is_active} for l in logs], "total": len(logs)}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        session.close()
'''

# =========================================================
# 4. audit_routes.py
# =========================================================
audit_routes = '''"""RBAC Audit API routes — SSOT 19, 20, 21.

Audit logging, access reviews, and entitlement requests.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/audit", tags=["rbac-audit"])


def _get_db_session():
    from sqlmodel import Session
    from common_lib.modules.integration.adapters.database_adapter import get_db_port
    engine = get_db_port().get_engine()
    return Session(engine)


class AccessReviewCreateRequest(BaseModel):
    name: str
    review_type: str = "role_assignment"
    scope_type: Optional[str] = None
    scope_id: Optional[str] = None
    reviewer_ids: Optional[list[int]] = None
    due_at: Optional[str] = None


class AccessReviewItemDecisionRequest(BaseModel):
    item_id: str
    decision: str  # approve, revoke, no_change
    reason: Optional[str] = None


class EntitlementRequestCreate(BaseModel):
    requester_id: int
    permission_name: Optional[str] = None
    role_name: Optional[str] = None
    reason: Optional[str] = None


class EntitlementRequestDecision(BaseModel):
    request_id: str
    decision: str  # approve, deny
    reviewer_id: int
    reason: Optional[str] = None


# -- Audit Logs --

@router.get("/logs")
def list_audit_logs(action: Optional[str] = None, limit: int = 50) -> Dict[str, Any]:
    from common_lib.modules.rbac.audit_service import RBACAuditService
    svc = RBACAuditService()
    return {"logs": [], "message": "Audit logs are written to the Python logger; no DB fetch available."}


# -- Access Reviews --

@router.post("/access-reviews")
def create_access_review(request: AccessReviewCreateRequest) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.audit.access_reviews import AccessReviewService
        svc = AccessReviewService(session)
        review = svc.create_review(
            name=request.name,
            review_type=request.review_type,
            scope_type=request.scope_type,
            scope_id=request.scope_id,
            reviewer_ids=request.reviewer_ids,
            due_at=request.due_at,
        )
        return {"id": review.id, "name": review.name, "status": review.status}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        session.close()


@router.post("/access-reviews/decide")
def decide_review_item(request: AccessReviewItemDecisionRequest) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.audit.access_reviews import AccessReviewService
        svc = AccessReviewService(session)
        result = svc.decide_item(request.item_id, request.decision, request.reason)
        return {"item_id": request.item_id, "decision": request.decision, "success": True}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        session.close()


@router.get("/access-reviews/{review_id}/summary")
def get_review_summary(review_id: str) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.audit.access_reviews import AccessReviewService
        svc = AccessReviewService(session)
        return svc.get_review_summary(review_id)
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        session.close()


# -- Entitlement Requests --

@router.post("/entitlement-requests")
def create_entitlement_request(request: EntitlementRequestCreate) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.audit.entitlement_requests import EntitlementRequestService
        svc = EntitlementRequestService(session)
        er = svc.create_request(
            requester_id=request.requester_id,
            permission_name=request.permission_name,
            role_name=request.role_name,
            reason=request.reason,
        )
        return {"id": er.id, "status": er.status}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        session.close()


@router.post("/entitlement-requests/decide")
def decide_entitlement_request(request: EntitlementRequestDecision) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.audit.entitlement_requests import EntitlementRequestService
        svc = EntitlementRequestService(session)
        if request.decision == "approve":
            er = svc.approve_request(request.request_id, request.reviewer_id)
        else:
            er = svc.deny_request(request.request_id, request.reviewer_id, request.reason)
        return {"id": er.id, "status": er.status}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        session.close()
'''

# =========================================================
# 5. machine_auth_routes.py — API Keys and Agent Credentials
# =========================================================
machine_auth_routes = '''"""RBAC Machine Auth API routes — SSOT 23, 24.

API key CRUD, agent credential management, and guest access.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/machine-auth", tags=["rbac-machine-auth"])


def _get_db_session():
    from sqlmodel import Session
    from common_lib.modules.integration.adapters.database_adapter import get_db_port
    engine = get_db_port().get_engine()
    return Session(engine)


class APIKeyCreateRequest(BaseModel):
    user_id: int
    name: str
    scopes: Optional[list[str]] = None
    expires_in_days: int = 365


@router.post("/api-keys")
def create_api_key(request: APIKeyCreateRequest) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.machine_auth.nodes import create_api_key as create_key
        result = create_key(user_id=request.user_id, name=request.name,
                            scopes=request.scopes, expires_in_days=request.expires_in_days)
        return result
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        session.close()


@router.get("/api-keys/user/{user_id}")
def list_api_keys(user_id: int) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.machine_auth.nodes import list_api_keys_for_user
        result = list_api_keys_for_user(user_id=user_id)
        return result
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        session.close()


@router.post("/api-keys/{key_id}/revoke")
def revoke_api_key(key_id: int) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.machine_auth.nodes import revoke_api_key
        result = revoke_api_key(key_id=key_id)
        return result
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        session.close()


@router.post("/validate")
def validate_api_key(token: str) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.machine_auth.nodes import validate_api_key
        result = validate_api_key(token=token)
        return result
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        session.close()
'''

# =========================================================
# 6. api_routes.py — Permission Check API
# =========================================================
api_routes = '''"""RBAC Permission Check API routes — SSOT 17, 18, 26.

Single check, batch check, simulate, explain, and permission matrix.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/permissions", tags=["rbac-permissions"])


def _get_db_session():
    from sqlmodel import Session
    from common_lib.modules.integration.adapters.database_adapter import get_db_port
    engine = get_db_port().get_engine()
    return Session(engine)


class CheckRequest(BaseModel):
    user_id: int
    resource: str
    action: str
    resource_id: Optional[str] = None
    org_id: Optional[str] = None


class CheckManyRequest(BaseModel):
    user_id: int
    checks: List[dict]


class SimulateRequest(BaseModel):
    user_id: int
    resource: str
    action: str


@router.post("/check")
def check_permission(request: CheckRequest) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.api.service import PermissionCheckService
        svc = PermissionCheckService(session)
        return svc.check(
            user_id=request.user_id,
            resource=request.resource,
            action=request.action,
            resource_id=request.resource_id,
            org_id=request.org_id,
        )
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        session.close()


@router.post("/check-many")
def check_many_permissions(request: CheckManyRequest) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.api.service import PermissionCheckService
        svc = PermissionCheckService(session)
        results = svc.check_many(user_id=request.user_id, checks=request.checks)
        return {"results": results, "total": len(results)}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        session.close()


@router.post("/simulate")
def simulate_permission(request: SimulateRequest) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.api.service import PermissionCheckService
        svc = PermissionCheckService(session)
        return svc.simulate(user_id=request.user_id, resource=request.resource, action=request.action)
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        session.close()


@router.post("/explain")
def explain_permission(request: SimulateRequest) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.api.service import PermissionCheckService
        svc = PermissionCheckService(session)
        return svc.explain(user_id=request.user_id, resource=request.resource, action=request.action)
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        session.close()


@router.get("/matrix")
def get_permission_matrix(role_ids: Optional[str] = None, resource_filter: Optional[str] = None) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.api.service import PermissionCheckService
        svc = PermissionCheckService(session)
        rids = [int(x) for x in role_ids.split(",")] if role_ids else None
        return svc.get_permission_matrix(role_ids=rids, resource_filter=resource_filter)
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        session.close()
'''

# =========================================================
# 7. ownership_routes.py
# =========================================================
ownership_routes = '''"""RBAC Resource Ownership API routes — SSOT 09.

Register, check, transfer, and list resource ownership.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ownership", tags=["rbac-ownership"])


def _get_db_session():
    from sqlmodel import Session
    from common_lib.modules.integration.adapters.database_adapter import get_db_port
    engine = get_db_port().get_engine()
    return Session(engine)


class RegisterOwnershipRequest(BaseModel):
    resource_type: str
    resource_id: str
    owner_user_id: Optional[int] = None
    owner_team_id: Optional[str] = None
    owner_org_id: Optional[str] = None


class TransferOwnershipRequest(BaseModel):
    new_owner_user_id: Optional[int] = None
    new_owner_team_id: Optional[str] = None
    new_owner_org_id: Optional[str] = None


@router.post("/register")
def register_ownership(request: RegisterOwnershipRequest) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.ownership_service import OwnershipService
        svc = OwnershipService(session)
        owner = svc.register(
            resource_type=request.resource_type,
            resource_id=request.resource_id,
            owner_user_id=request.owner_user_id,
            owner_team_id=request.owner_team_id,
            owner_org_id=request.owner_org_id,
        )
        return {"id": owner.id, "resource_type": owner.resource_type, "resource_id": owner.resource_id}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        session.close()


@router.get("/{resource_type}/{resource_id}")
def get_ownership(resource_type: str, resource_id: str) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.ownership_service import OwnershipService
        svc = OwnershipService(session)
        owner = svc.get_owner(resource_type, resource_id)
        if not owner:
            raise HTTPException(404, "No ownership record found")
        return {"id": owner.id, "resource_type": owner.resource_type, "resource_id": owner.resource_id,
                "owner_user_id": owner.owner_user_id, "owner_team_id": owner.owner_team_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        session.close()


@router.post("/{resource_type}/{resource_id}/transfer")
def transfer_ownership(resource_type: str, resource_id: str, request: TransferOwnershipRequest) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.ownership_service import OwnershipService
        svc = OwnershipService(session)
        owner = svc.transfer(
            resource_type=resource_type,
            resource_id=resource_id,
            new_owner_user_id=request.new_owner_user_id,
            new_owner_team_id=request.new_owner_team_id,
            new_owner_org_id=request.new_owner_org_id,
        )
        if not owner:
            raise HTTPException(404, "No ownership record found")
        return {"success": True, "owner_user_id": owner.owner_user_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        session.close()


@router.delete("/{resource_type}/{resource_id}")
def delete_ownership(resource_type: str, resource_id: str) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.ownership_service import OwnershipService
        svc = OwnershipService(session)
        svc.delete(resource_type, resource_id)
        return {"success": True}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        session.close()
'''

# =========================================================
# 8. cache_routes.py
# =========================================================
cache_routes = '''"""RBAC Cache API routes — SSOT 27.

Permission cache invalidation and statistics.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cache", tags=["rbac-cache"])


@router.get("/stats")
def cache_stats() -> Dict[str, Any]:
    try:
        from common_lib.modules.rbac.permission_cache import get_permission_cache
        cache = get_permission_cache()
        return {"stats": cache.stats}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/invalidate/user/{user_id}")
def invalidate_user_cache(user_id: int) -> Dict[str, Any]:
    try:
        from common_lib.modules.rbac.permission_cache import get_permission_cache
        cache = get_permission_cache()
        cache.invalidate_user(user_id)
        return {"success": True, "user_id": user_id}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/invalidate/all")
def invalidate_all_cache() -> Dict[str, Any]:
    try:
        from common_lib.modules.rbac.permission_cache import get_permission_cache
        cache = get_permission_cache()
        cache.invalidate_all()
        return {"success": True}
    except Exception as e:
        raise HTTPException(500, str(e))
'''

# =========================================================
# 9. hardening_routes.py
# =========================================================
hardening_routes = '''"""RBAC Hardening API routes — SSOT 28.

Privilege escalation detection, threat detection, and service hardening.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/hardening", tags=["rbac-hardening"])


def _get_db_session():
    from sqlmodel import Session
    from common_lib.modules.integration.adapters.database_adapter import get_db_port
    engine = get_db_port().get_engine()
    return Session(engine)


class ThreatCheckRequest(BaseModel):
    actor_user_id: int
    target_user_id: int
    role_ids: list[int]


@router.post("/check-escalation")
def check_privilege_escalation(request: ThreatCheckRequest) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.hardening.service import PrivilegeEscalationGuard
        svc = PrivilegeEscalationGuard(session)
        result = svc.check_escalation(
            actor_user_id=request.actor_user_id,
            target_user_id=request.target_user_id,
            role_ids=request.role_ids,
        )
        return {"allowed": result.allowed, "reason": result.reason, "severity": result.severity}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        session.close()


@router.get("/threats")
def list_threats(status: Optional[str] = None) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.hardening.service import ThreatDetectionService
        svc = ThreatDetectionService(session)
        threats = svc.list_threats(status=status)
        return {"threats": threats, "total": len(threats)}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        session.close()


@router.get("/threats/{threat_id}")
def get_threat(threat_id: str) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.hardening.service import ThreatDetectionService
        svc = ThreatDetectionService(session)
        threat = svc.get_threat(threat_id)
        if not threat:
            raise HTTPException(404, "Threat not found")
        return threat
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        session.close()
'''

# =========================================================
# Write all files
# =========================================================
files = {
    "tenancy_routes.py": tenancy_routes,
    "sessions_routes.py": sessions_routes,
    "delegation_routes.py": delegation_routes,
    "audit_routes.py": audit_routes,
    "machine_auth_routes.py": machine_auth_routes,
    "api_routes.py": api_routes,
    "ownership_routes.py": ownership_routes,
    "cache_routes.py": cache_routes,
    "hardening_routes.py": hardening_routes,
}

for fname, content in files.items():
    fpath = os.path.join(routes_dir, fname)
    if os.path.exists(fpath):
        print(f"SKIP {fname} — already exists")
        continue
    with open(fpath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"CREATED {fname}")

print(f"\nDone. {len(files)} route files processed.")
