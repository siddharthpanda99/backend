"""
Create 9 missing RBAC route files and wire them into router.py.
Also fix MCP rbac.py to use the correct common_lib path.
"""
import os

BASE = "app/modules/rbac/routes"
os.makedirs(BASE, exist_ok=True)

# Template for _get_db_session
DBSESSION = '''def _get_db_session():
    from sqlmodel import Session
    from common_lib.modules.integration.adapters.database_adapter import get_db_port
    engine = get_db_port().get_engine()
    return Session(engine)

'''

def write_routes(fname, content):
    path = os.path.join(BASE, fname)
    if os.path.exists(path):
        print(f"SKIP {fname}")
        return False
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"CREATED {fname}")
    return True

# ── 1. tenancy_routes.py ────────────────────────────────────────────────────
write_routes("tenancy_routes.py", '''"""RBAC Tenancy API routes — SSOT 08."""
from __future__ import annotations
import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tenancy", tags=["rbac-tenancy"])

''' + DBSESSION + '''
class OrgCreate(BaseModel):
    name: str; slug: str; description: Optional[str] = None

@router.post("/orgs")
def create_org(req: OrgCreate):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.tenant_service import OrganizationService
        org = OrganizationService(session).create(name=req.name, slug=req.slug, description=req.description)
        return {"id": org.id, "name": org.name, "slug": org.slug}
    finally:
        session.close()

@router.get("/orgs")
def list_orgs():
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.tenant_service import OrganizationService
        orgs = OrganizationService(session).list_orgs()
        return {"organizations": [{"id": o.id, "name": o.name, "slug": o.slug} for o in orgs], "total": len(orgs)}
    finally:
        session.close()

@router.get("/orgs/{org_id}")
def get_org(org_id: int):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.tenant_service import OrganizationService
        org = OrganizationService(session).get_by_id(org_id)
        if not org: raise HTTPException(404)
        return {"id": org.id, "name": org.name, "slug": org.slug}
    finally:
        session.close()

@router.delete("/orgs/{org_id}")
def delete_org(org_id: int):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.tenant_service import OrganizationService
        OrganizationService(session).delete(org_id)
        return {"success": True}
    finally:
        session.close()

@router.post("/orgs/{org_id}/members")
def add_org_member(org_id: int, user_id: int, role: str = "member"):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.tenant_service import OrganizationService
        m = OrganizationService(session).add_member(org_id, user_id, role)
        return {"user_id": m.user_id, "role": m.role}
    finally:
        session.close()

@router.get("/orgs/{org_id}/members")
def list_org_members(org_id: int):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.tenant_service import OrganizationService
        members = OrganizationService(session).list_members(org_id)
        return {"members": [{"user_id": m.user_id, "role": m.role} for m in members], "total": len(members)}
    finally:
        session.close()

@router.post("/teams")
def create_team(name: str, slug: str, org_id: int):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.tenant_service import TeamServiceRBAC
        t = TeamServiceRBAC(session).create(name=name, slug=slug, org_id=org_id)
        return {"id": t.id, "name": t.name, "slug": t.slug}
    finally:
        session.close()

@router.get("/teams")
def list_teams(org_id: Optional[int] = None):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.tenant_service import TeamServiceRBAC
        teams = TeamServiceRBAC(session).list_teams(org_id=org_id)
        return {"teams": [{"id": t.id, "name": t.name} for t in teams], "total": len(teams)}
    finally:
        session.close()
''')

# ── 2. sessions_routes.py ───────────────────────────────────────────────────
write_routes("sessions_routes.py", '''"""RBAC Session/MFA API routes — SSOT 11 & 12."""
from __future__ import annotations
import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sessions", tags=["rbac-sessions"])

''' + DBSESSION + '''
class CreateSessionReq(BaseModel):
    user_id: int; ip_address: Optional[str] = None; user_agent: Optional[str] = None
    device_info: Optional[dict] = None; expires_in_hours: int = 24

@router.post("")
def create_session(req: CreateSessionReq):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.session_mfa_service import SessionService
        s, tok = SessionService(session).create_session(
            user_id=req.user_id, ip_address=req.ip_address, user_agent=req.user_agent,
            device_info=req.device_info, expires_in_hours=req.expires_in_hours)
        return {"session_id": s.id, "token": tok, "expires_at": s.expires_at.isoformat()}
    finally:
        session.close()

@router.post("/validate")
def validate_session(token: str):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.session_mfa_service import SessionService
        s = SessionService(session).validate_session(token)
        if not s: raise HTTPException(401, "Invalid session")
        return {"valid": True, "user_id": s.user_id, "session_id": s.id}
    finally:
        session.close()

@router.post("/{sid}/revoke")
def revoke_session(sid: int, reason: str = "user_request"):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.session_mfa_service import SessionService
        SessionService(session).revoke_session(sid, reason)
        return {"success": True}
    finally:
        session.close()

@router.post("/mfa/setup")
def mfa_setup(user_id: int):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.session_mfa_service import MFAService
        secret, uri = MFAService(session).setup_totp(user_id)
        return {"secret": secret, "uri": uri}
    finally:
        session.close()

@router.post("/mfa/verify")
def mfa_verify(user_id: int, code: str):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.session_mfa_service import MFAService
        ok = MFAService(session).verify_totp(user_id, code)
        return {"verified": ok}
    finally:
        session.close()

@router.get("/mfa/status/{user_id}")
def mfa_status(user_id: int):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.session_mfa_service import MFAService
        return {"user_id": user_id, "enabled": MFAService(session).is_enabled(user_id)}
    finally:
        session.close()
''')

# ── 3. delegation_routes.py ─────────────────────────────────────────────────
write_routes("delegation_routes.py", '''"""RBAC Delegation API routes — SSOT 13."""
from __future__ import annotations
import logging
from typing import Any, Dict, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/delegations", tags=["rbac-delegations"])

''' + DBSESSION + '''
class CreateDelegationReq(BaseModel):
    delegator_user_id: int; delegatee_user_id: int; expires_at: str
    scope_type: str = "all"; reason: Optional[str] = None

@router.post("")
def create_delegation(req: CreateDelegationReq):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.delegation.service import DelegationService
        r = DelegationService(session).create_delegation(
            req.delegator_user_id, req.delegatee_user_id,
            datetime.fromisoformat(req.expires_at), req.scope_type, reason=req.reason)
        return {"delegation_id": r.delegation_id, "expires_at": r.expires_at.isoformat()}
    except ValueError as e: raise HTTPException(400, str(e))
    finally: session.close()

@router.get("/active/{user_id}")
def active_delegations(user_id: int):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.delegation.service import DelegationService
        rs = DelegationService(session).get_active_delegations_for_user(user_id)
        return {"delegations": [{"id": r.delegation_id, "from": r.delegator_user_id, "expires": r.expires_at.isoformat()} for r in rs], "total": len(rs)}
    finally: session.close()

@router.post("/{did}/revoke")
def revoke_delegation(did: str):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.delegation.service import DelegationService
        DelegationService(session).revoke_delegation(did)
        return {"success": True}
    finally: session.close()

@router.post("/impersonations")
def start_impersonation(admin_user_id: int, target_user_id: int, reason: str):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.delegation.service import ImpersonationService
        log = ImpersonationService(session).start_impersonation(admin_user_id, target_user_id, reason)
        return {"session_id": log.session_id}
    except ValueError as e: raise HTTPException(400, str(e))
    finally: session.close()

@router.post("/impersonations/end")
def end_impersonation(session_id: str):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.delegation.service import ImpersonationService
        ImpersonationService(session).end_impersonation(session_id)
        return {"success": True}
    finally: session.close()
''')

# ── 4. audit_routes.py ──────────────────────────────────────────────────────
write_routes("audit_routes.py", '''"""RBAC Audit API routes — SSOT 19, 20, 21."""
from __future__ import annotations
import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/audit", tags=["rbac-audit"])

''' + DBSESSION + '''
@router.post("/access-reviews")
def create_access_review(name: str, review_type: str = "role_assignment", scope_type: Optional[str] = None, scope_id: Optional[str] = None):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.audit.access_reviews import AccessReviewService
        r = AccessReviewService(session).create_review(name=name, review_type=review_type, scope_type=scope_type, scope_id=scope_id)
        return {"id": r.id, "name": r.name, "status": r.status}
    except Exception as e: raise HTTPException(500, str(e))
    finally: session.close()

@router.post("/access-reviews/decide")
def decide_review_item(item_id: str, decision: str, reason: Optional[str] = None):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.audit.access_reviews import AccessReviewService
        AccessReviewService(session).decide_item(item_id, decision, reason)
        return {"success": True}
    except Exception as e: raise HTTPException(500, str(e))
    finally: session.close()

@router.post("/entitlement-requests")
def create_entitlement_request(requester_id: int, permission_name: Optional[str] = None, role_name: Optional[str] = None, reason: Optional[str] = None):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.audit.entitlement_requests import EntitlementRequestService
        er = EntitlementRequestService(session).create_request(requester_id, permission_name=permission_name, role_name=role_name, reason=reason)
        return {"id": er.id, "status": er.status}
    except Exception as e: raise HTTPException(500, str(e))
    finally: session.close()

@router.post("/entitlement-requests/{rid}/approve")
def approve_entitlement_request(rid: str, reviewer_id: int):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.audit.entitlement_requests import EntitlementRequestService
        er = EntitlementRequestService(session).approve_request(rid, reviewer_id)
        return {"id": er.id, "status": er.status}
    except Exception as e: raise HTTPException(500, str(e))
    finally: session.close()

@router.post("/entitlement-requests/{rid}/deny")
def deny_entitlement_request(rid: str, reviewer_id: int, reason: Optional[str] = None):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.audit.entitlement_requests import EntitlementRequestService
        er = EntitlementRequestService(session).deny_request(rid, reviewer_id, reason)
        return {"id": er.id, "status": er.status}
    except Exception as e: raise HTTPException(500, str(e))
    finally: session.close()
''')

# ── 5. machine_auth_routes.py ───────────────────────────────────────────────
write_routes("machine_auth_routes.py", '''"""RBAC Machine Auth API routes — SSOT 23, 24."""
from __future__ import annotations
import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/machine-auth", tags=["rbac-machine-auth"])

''' + DBSESSION + '''
class APIKeyCreateReq(BaseModel):
    user_id: int; name: str; scopes: Optional[list[str]] = None; expires_in_days: int = 365

@router.post("/api-keys")
def create_api_key(req: APIKeyCreateReq):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.machine_auth.nodes import create_api_key
        return create_api_key(user_id=req.user_id, name=req.name, scopes=req.scopes, expires_in_days=req.expires_in_days)
    except Exception as e: raise HTTPException(500, str(e))
    finally: session.close()

@router.get("/api-keys/user/{user_id}")
def list_api_keys(user_id: int):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.machine_auth.nodes import list_api_keys_for_user
        return list_api_keys_for_user(user_id=user_id)
    except Exception as e: raise HTTPException(500, str(e))
    finally: session.close()

@router.post("/api-keys/{kid}/revoke")
def revoke_api_key(kid: int):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.machine_auth.nodes import revoke_api_key
        return revoke_api_key(key_id=kid)
    except Exception as e: raise HTTPException(500, str(e))
    finally: session.close()

@router.post("/validate")
def validate_api_key(token: str):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.machine_auth.nodes import validate_api_key
        return validate_api_key(token=token)
    except Exception as e: raise HTTPException(500, str(e))
    finally: session.close()
''')

# ── 6. api_routes.py ────────────────────────────────────────────────────────
write_routes("api_routes.py", '''"""RBAC Permission Check API routes — SSOT 17, 18, 26."""
from __future__ import annotations
import logging
from typing import Any, Dict, Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/permissions", tags=["rbac-permissions"])

''' + DBSESSION + '''
class CheckReq(BaseModel):
    user_id: int; resource: str; action: str; resource_id: Optional[str] = None; org_id: Optional[str] = None

class CheckManyReq(BaseModel):
    user_id: int; checks: List[dict]

@router.post("/check")
def check(req: CheckReq):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.api.service import PermissionCheckService
        return PermissionCheckService(session).check(user_id=req.user_id, resource=req.resource, action=req.action, resource_id=req.resource_id, org_id=req.org_id)
    except Exception as e: raise HTTPException(500, str(e))
    finally: session.close()

@router.post("/check-many")
def check_many(req: CheckManyReq):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.api.service import PermissionCheckService
        results = PermissionCheckService(session).check_many(user_id=req.user_id, checks=req.checks)
        return {"results": results, "total": len(results)}
    except Exception as e: raise HTTPException(500, str(e))
    finally: session.close()

@router.post("/simulate")
def simulate(user_id: int, resource: str, action: str):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.api.service import PermissionCheckService
        return PermissionCheckService(session).simulate(user_id=user_id, resource=resource, action=action)
    except Exception as e: raise HTTPException(500, str(e))
    finally: session.close()

@router.post("/explain")
def explain(user_id: int, resource: str, action: str):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.api.service import PermissionCheckService
        return PermissionCheckService(session).explain(user_id=user_id, resource=resource, action=action)
    except Exception as e: raise HTTPException(500, str(e))
    finally: session.close()

@router.get("/matrix")
def matrix(role_ids: Optional[str] = None, resource_filter: Optional[str] = None):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.api.service import PermissionCheckService
        rids = [int(x) for x in role_ids.split(",")] if role_ids else None
        return PermissionCheckService(session).get_permission_matrix(role_ids=rids, resource_filter=resource_filter)
    except Exception as e: raise HTTPException(500, str(e))
    finally: session.close()
''')

# ── 7. ownership_routes.py ──────────────────────────────────────────────────
write_routes("ownership_routes.py", '''"""RBAC Resource Ownership API routes — SSOT 09."""
from __future__ import annotations
import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ownership", tags=["rbac-ownership"])

''' + DBSESSION + '''
class RegisterOwnershipReq(BaseModel):
    resource_type: str; resource_id: str
    owner_user_id: Optional[int] = None; owner_team_id: Optional[str] = None; owner_org_id: Optional[str] = None

@router.post("/register")
def register(req: RegisterOwnershipReq):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.ownership_service import OwnershipService
        o = OwnershipService(session).register(req.resource_type, req.resource_id, req.owner_user_id, req.owner_team_id, req.owner_org_id)
        return {"id": o.id, "resource_type": o.resource_type, "resource_id": o.resource_id}
    except Exception as e: raise HTTPException(500, str(e))
    finally: session.close()

@router.get("/{rtype}/{rid}")
def get_ownership(rtype: str, rid: str):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.ownership_service import OwnershipService
        o = OwnershipService(session).get_owner(rtype, rid)
        if not o: raise HTTPException(404)
        return {"resource_type": o.resource_type, "resource_id": o.resource_id, "owner_user_id": o.owner_user_id}
    finally: session.close()

@router.post("/{rtype}/{rid}/transfer")
def transfer(rtype: str, rid: str, new_owner_user_id: Optional[int] = None):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.ownership_service import OwnershipService
        o = OwnershipService(session).transfer(rtype, rid, new_owner_user_id=new_owner_user_id)
        if not o: raise HTTPException(404)
        return {"success": True, "owner_user_id": o.owner_user_id}
    finally: session.close()

@router.delete("/{rtype}/{rid}")
def delete_ownership(rtype: str, rid: str):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.ownership_service import OwnershipService
        OwnershipService(session).delete(rtype, rid)
        return {"success": True}
    except Exception as e: raise HTTPException(500, str(e))
    finally: session.close()
''')

# ── 8. cache_routes.py ──────────────────────────────────────────────────────
write_routes("cache_routes.py", '''"""RBAC Cache API routes — SSOT 27."""
from __future__ import annotations
import logging
from typing import Any, Dict
from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/cache", tags=["rbac-cache"])

@router.get("/stats")
def cache_stats():
    from common_lib.modules.rbac.permission_cache import get_permission_cache
    return {"stats": get_permission_cache().stats}

@router.post("/invalidate/user/{user_id}")
def invalidate_user(user_id: int):
    from common_lib.modules.rbac.permission_cache import get_permission_cache
    get_permission_cache().invalidate_user(user_id)
    return {"success": True}

@router.post("/invalidate/all")
def invalidate_all():
    from common_lib.modules.rbac.permission_cache import get_permission_cache
    get_permission_cache().invalidate_all()
    return {"success": True}
''')

# ── 9. hardening_routes.py ──────────────────────────────────────────────────
write_routes("hardening_routes.py", '''"""RBAC Hardening API routes — SSOT 28."""
from __future__ import annotations
import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/hardening", tags=["rbac-hardening"])

''' + DBSESSION + '''
class EscalationCheckReq(BaseModel):
    actor_user_id: int; target_user_id: int; role_ids: list[int]

@router.post("/check-escalation")
def check_escalation(req: EscalationCheckReq):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.hardening.service import PrivilegeEscalationGuard
        r = PrivilegeEscalationGuard(session).check_escalation(req.actor_user_id, req.target_user_id, req.role_ids)
        return {"allowed": r.allowed, "reason": r.reason, "severity": r.severity}
    except Exception as e: raise HTTPException(500, str(e))
    finally: session.close()

@router.get("/threats")
def list_threats():
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.hardening.service import ThreatDetectionService
        threats = ThreatDetectionService(session).list_threats()
        return {"threats": threats, "total": len(threats)}
    except Exception as e: raise HTTPException(500, str(e))
    finally: session.close()
''')

# ── Now update router.py to wire all sub-routers ───────────────────────────
router_path = os.path.join(BASE, "router.py")
with open(router_path, "r", encoding="utf-8") as f:
    router_content = f.read()

# Check what sub-routers are already included
import re
existing = set(re.findall(r'from app\.modules\.rbac\.routes\.(\w+) import', router_content))
print(f"\nAlready wired: {sorted(existing)}")

# Sub-routers to add
to_add = ["tenancy_routes", "sessions_routes", "delegation_routes", "audit_routes",
          "machine_auth_routes", "api_routes", "ownership_routes", "cache_routes", "hardening_routes"]

# Build the include block
new_includes = ""
for name in to_add:
    new_includes += f"\nfrom app.modules.rbac.routes.{name} import router as {name.replace('_routes', '_router')}\nrouter.include_router({name.replace('_routes', '_router')})\n"

# Find the last include_router line and append after it
# The last include_router line is for debug_routes
marker = 'router.include_router(debug_router)'
if marker in router_content:
    insert_idx = router_content.index(marker) + len(marker)
    router_content = router_content[:insert_idx] + new_includes + router_content[insert_idx:]
    with open(router_path, "w", encoding="utf-8") as f:
        f.write(router_content)
    print(f"\nWired {len(to_add)} new route files into router.py")
else:
    print(f"\nWARNING: Could not find marker '{marker}' in router.py")

print("\nDone.")
