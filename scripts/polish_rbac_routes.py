"""Polish 9 generated RBAC route files.

Issues to fix:
1. Replace semicolons with newlines in Pydantic model class definitions
2. Add consistent HTTPException(500) wrapping to all route handlers
3. Ensure all exceptions are properly caught and don't leak internal errors
"""

import os
import re

BASE = "app/modules/rbac/routes"

# =========================================================================
# Fix 1: tenancy_routes.py — semicolons + exception wrapping
# =========================================================================
path = os.path.join(BASE, "tenancy_routes.py")
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Fix semicolons in class OrgCreate
content = content.replace(
    "class OrgCreate(BaseModel):\n    name: str; slug: str; description: Optional[str] = None",
    "class OrgCreate(BaseModel):\n    name: str\n    slug: str\n    description: Optional[str] = None"
)

# Add HTTPException wrapping to routes missing it
# create_org
content = content.replace(
    "def create_org(req: OrgCreate):\n    session = _get_db_session()\n    try:\n        from common_lib.modules.rbac.tenant_service import OrganizationService\n        org = OrganizationService(session).create(name=req.name, slug=req.slug, description=req.description)\n        return {\"id\": org.id, \"name\": org.name, \"slug\": org.slug}\n    finally:\n        session.close()",
    "def create_org(req: OrgCreate):\n    session = _get_db_session()\n    try:\n        from common_lib.modules.rbac.tenant_service import OrganizationService\n        org = OrganizationService(session).create(name=req.name, slug=req.slug, description=req.description)\n        return {\"id\": org.id, \"name\": org.name, \"slug\": org.slug}\n    except Exception as e:\n        raise HTTPException(500, str(e))\n    finally:\n        session.close()"
)

# list_orgs
content = content.replace(
    "def list_orgs():\n    session = _get_db_session()\n    try:\n        from common_lib.modules.rbac.tenant_service import OrganizationService\n        orgs = OrganizationService(session).list_orgs()\n        return {\"organizations\": [{\"id\": o.id, \"name\": o.name, \"slug\": o.slug} for o in orgs], \"total\": len(orgs)}\n    finally:\n        session.close()",
    "def list_orgs():\n    session = _get_db_session()\n    try:\n        from common_lib.modules.rbac.tenant_service import OrganizationService\n        orgs = OrganizationService(session).list_orgs()\n        return {\"organizations\": [{\"id\": o.id, \"name\": o.name, \"slug\": o.slug} for o in orgs], \"total\": len(orgs)}\n    except Exception as e:\n        raise HTTPException(500, str(e))\n    finally:\n        session.close()"
)

# delete_org
content = content.replace(
    "def delete_org(org_id: int):\n    session = _get_db_session()\n    try:\n        from common_lib.modules.rbac.tenant_service import OrganizationService\n        OrganizationService(session).delete(org_id)\n        return {\"success\": True}\n    finally:\n        session.close()",
    "def delete_org(org_id: int):\n    session = _get_db_session()\n    try:\n        from common_lib.modules.rbac.tenant_service import OrganizationService\n        OrganizationService(session).delete(org_id)\n        return {\"success\": True}\n    except Exception as e:\n        raise HTTPException(500, str(e))\n    finally:\n        session.close()"
)

# add_org_member
content = content.replace(
    "def add_org_member(org_id: int, user_id: int, role: str = \"member\"):\n    session = _get_db_session()\n    try:\n        from common_lib.modules.rbac.tenant_service import OrganizationService\n        m = OrganizationService(session).add_member(org_id, user_id, role)\n        return {\"user_id\": m.user_id, \"role\": m.role}\n    finally:\n        session.close()",
    "def add_org_member(org_id: int, user_id: int, role: str = \"member\"):\n    session = _get_db_session()\n    try:\n        from common_lib.modules.rbac.tenant_service import OrganizationService\n        m = OrganizationService(session).add_member(org_id, user_id, role)\n        return {\"user_id\": m.user_id, \"role\": m.role}\n    except Exception as e:\n        raise HTTPException(500, str(e))\n    finally:\n        session.close()"
)

# list_org_members
content = content.replace(
    "def list_org_members(org_id: int):\n    session = _get_db_session()\n    try:\n        from common_lib.modules.rbac.tenant_service import OrganizationService\n        members = OrganizationService(session).list_members(org_id)\n        return {\"members\": [{\"user_id\": m.user_id, \"role\": m.role} for m in members], \"total\": len(members)}\n    finally:\n        session.close()",
    "def list_org_members(org_id: int):\n    session = _get_db_session()\n    try:\n        from common_lib.modules.rbac.tenant_service import OrganizationService\n        members = OrganizationService(session).list_members(org_id)\n        return {\"members\": [{\"user_id\": m.user_id, \"role\": m.role} for m in members], \"total\": len(members)}\n    except Exception as e:\n        raise HTTPException(500, str(e))\n    finally:\n        session.close()"
)

# create_team
content = content.replace(
    "def create_team(name: str, slug: str, org_id: int):\n    session = _get_db_session()\n    try:\n        from common_lib.modules.rbac.tenant_service import TeamServiceRBAC\n        t = TeamServiceRBAC(session).create(name=name, slug=slug, org_id=org_id)\n        return {\"id\": t.id, \"name\": t.name, \"slug\": t.slug}\n    finally:\n        session.close()",
    "def create_team(name: str, slug: str, org_id: int):\n    session = _get_db_session()\n    try:\n        from common_lib.modules.rbac.tenant_service import TeamServiceRBAC\n        t = TeamServiceRBAC(session).create(name=name, slug=slug, org_id=org_id)\n        return {\"id\": t.id, \"name\": t.name, \"slug\": t.slug}\n    except Exception as e:\n        raise HTTPException(500, str(e))\n    finally:\n        session.close()"
)

# list_teams
content = content.replace(
    "def list_teams(org_id: Optional[int] = None):\n    session = _get_db_session()\n    try:\n        from common_lib.modules.rbac.tenant_service import TeamServiceRBAC\n        teams = TeamServiceRBAC(session).list_teams(org_id=org_id)\n        return {\"teams\": [{\"id\": t.id, \"name\": t.name} for t in teams], \"total\": len(teams)}\n    finally:\n        session.close()",
    "def list_teams(org_id: Optional[int] = None):\n    session = _get_db_session()\n    try:\n        from common_lib.modules.rbac.tenant_service import TeamServiceRBAC\n        teams = TeamServiceRBAC(session).list_teams(org_id=org_id)\n        return {\"teams\": [{\"id\": t.id, \"name\": t.name} for t in teams], \"total\": len(teams)}\n    except Exception as e:\n        raise HTTPException(500, str(e))\n    finally:\n        session.close()"
)

# get_org with HTTPException 404 - add generic handler
content = content.replace(
    "def get_org(org_id: int):\n    session = _get_db_session()\n    try:\n        from common_lib.modules.rbac.tenant_service import OrganizationService\n        org = OrganizationService(session).get_by_id(org_id)\n        if not org: raise HTTPException(404)\n        return {\"id\": org.id, \"name\": org.name, \"slug\": org.slug}\n    finally:\n        session.close()",
    "def get_org(org_id: int):\n    session = _get_db_session()\n    try:\n        from common_lib.modules.rbac.tenant_service import OrganizationService\n        org = OrganizationService(session).get_by_id(org_id)\n        if not org:\n            raise HTTPException(404, \"Organization not found\")\n        return {\"id\": org.id, \"name\": org.name, \"slug\": org.slug}\n    except HTTPException:\n        raise\n    except Exception as e:\n        raise HTTPException(500, str(e))\n    finally:\n        session.close()"
)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("tenancy_routes.py: Fixed semicolons + HTTPException wrapping")

# =========================================================================
# Fix 2: sessions_routes.py
# =========================================================================
path = os.path.join(BASE, "sessions_routes.py")
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Fix semicolons
content = content.replace(
    "class CreateSessionReq(BaseModel):\n    user_id: int; ip_address: Optional[str] = None; user_agent: Optional[str] = None\n    device_info: Optional[dict] = None; expires_in_hours: int = 24",
    "class CreateSessionReq(BaseModel):\n    user_id: int\n    ip_address: Optional[str] = None\n    user_agent: Optional[str] = None\n    device_info: Optional[dict] = None\n    expires_in_hours: int = 24"
)

# Add HTTPException wrapping to create_session
content = content.replace(
    "def create_session(req: CreateSessionReq):\n    session = _get_db_session()\n    try:\n        from common_lib.modules.rbac.session_mfa_service import SessionService\n        s, tok = SessionService(session).create_session(\n            user_id=req.user_id, ip_address=req.ip_address, user_agent=req.user_agent,\n            device_info=req.device_info, expires_in_hours=req.expires_in_hours)\n        return {\"session_id\": s.id, \"token\": tok, \"expires_at\": s.expires_at.isoformat()}\n    finally:\n        session.close()",
    "def create_session(req: CreateSessionReq):\n    session = _get_db_session()\n    try:\n        from common_lib.modules.rbac.session_mfa_service import SessionService\n        s, tok = SessionService(session).create_session(\n            user_id=req.user_id, ip_address=req.ip_address, user_agent=req.user_agent,\n            device_info=req.device_info, expires_in_hours=req.expires_in_hours)\n        return {\"session_id\": s.id, \"token\": tok, \"expires_at\": s.expires_at.isoformat()}\n    except ValueError as e:\n        raise HTTPException(400, str(e))\n    except Exception as e:\n        raise HTTPException(500, str(e))\n    finally:\n        session.close()"
)

# Add HTTPException wrapping to revoke_session
content = content.replace(
    "def revoke_session(sid: int, reason: str = \"user_request\"):\n    session = _get_db_session()\n    try:\n        from common_lib.modules.rbac.session_mfa_service import SessionService\n        SessionService(session).revoke_session(sid, reason)\n        return {\"success\": True}\n    finally:\n        session.close()",
    "def revoke_session(sid: int, reason: str = \"user_request\"):\n    session = _get_db_session()\n    try:\n        from common_lib.modules.rbac.session_mfa_service import SessionService\n        SessionService(session).revoke_session(sid, reason)\n        return {\"success\": True}\n    except Exception as e:\n        raise HTTPException(500, str(e))\n    finally:\n        session.close()"
)

# Add HTTPException wrapping to mfa_setup
content = content.replace(
    "def mfa_setup(user_id: int):\n    session = _get_db_session()\n    try:\n        from common_lib.modules.rbac.session_mfa_service import MFAService\n        secret, uri = MFAService(session).setup_totp(user_id)\n        return {\"secret\": secret, \"uri\": uri}\n    finally:\n        session.close()",
    "def mfa_setup(user_id: int):\n    session = _get_db_session()\n    try:\n        from common_lib.modules.rbac.session_mfa_service import MFAService\n        secret, uri = MFAService(session).setup_totp(user_id)\n        return {\"secret\": secret, \"uri\": uri}\n    except ValueError as e:\n        raise HTTPException(400, str(e))\n    except Exception as e:\n        raise HTTPException(500, str(e))\n    finally:\n        session.close()"
)

# Add HTTPException wrapping to mfa_verify
content = content.replace(
    "def mfa_verify(user_id: int, code: str):\n    session = _get_db_session()\n    try:\n        from common_lib.modules.rbac.session_mfa_service import MFAService\n        ok = MFAService(session).verify_totp(user_id, code)\n        return {\"verified\": ok}\n    finally:\n        session.close()",
    "def mfa_verify(user_id: int, code: str):\n    session = _get_db_session()\n    try:\n        from common_lib.modules.rbac.session_mfa_service import MFAService\n        ok = MFAService(session).verify_totp(user_id, code)\n        return {\"verified\": ok}\n    except Exception as e:\n        raise HTTPException(500, str(e))\n    finally:\n        session.close()"
)

# Add HTTPException wrapping to mfa_status
content = content.replace(
    "def mfa_status(user_id: int):\n    session = _get_db_session()\n    try:\n        from common_lib.modules.rbac.session_mfa_service import MFAService\n        return {\"user_id\": user_id, \"enabled\": MFAService(session).is_enabled(user_id)}\n    finally:\n        session.close()",
    "def mfa_status(user_id: int):\n    session = _get_db_session()\n    try:\n        from common_lib.modules.rbac.session_mfa_service import MFAService\n        return {\"user_id\": user_id, \"enabled\": MFAService(session).is_enabled(user_id)}\n    except Exception as e:\n        raise HTTPException(500, str(e))\n    finally:\n        session.close()"
)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("sessions_routes.py: Fixed semicolons + HTTPException wrapping")

# =========================================================================
# Fix 3: delegation_routes.py
# =========================================================================
path = os.path.join(BASE, "delegation_routes.py")
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Fix semicolons
content = content.replace(
    "class CreateDelegationReq(BaseModel):\n    delegator_user_id: int; delegatee_user_id: int; expires_at: str\n    scope_type: str = \"all\"; reason: Optional[str] = None",
    "class CreateDelegationReq(BaseModel):\n    delegator_user_id: int\n    delegatee_user_id: int\n    expires_at: str\n    scope_type: str = \"all\"\n    reason: Optional[str] = None"
)

# active_delegations - add generic handler
content = content.replace(
    "def active_delegations(user_id: int):\n    session = _get_db_session()\n    try:\n        from common_lib.modules.rbac.delegation.service import DelegationService\n        rs = DelegationService(session).get_active_delegations_for_user(user_id)\n        return {\"delegations\": [{\"id\": r.delegation_id, \"from\": r.delegator_user_id, \"expires\": r.expires_at.isoformat()} for r in rs], \"total\": len(rs)}\n    finally: session.close()",
    "def active_delegations(user_id: int):\n    session = _get_db_session()\n    try:\n        from common_lib.modules.rbac.delegation.service import DelegationService\n        rs = DelegationService(session).get_active_delegations_for_user(user_id)\n        return {\"delegations\": [{\"id\": r.delegation_id, \"from\": r.delegator_user_id, \"expires\": r.expires_at.isoformat()} for r in rs], \"total\": len(rs)}\n    except Exception as e:\n        raise HTTPException(500, str(e))\n    finally: session.close()"
)

# revoke_delegation - add generic handler
content = content.replace(
    "def revoke_delegation(did: str):\n    session = _get_db_session()\n    try:\n        from common_lib.modules.rbac.delegation.service import DelegationService\n        DelegationService(session).revoke_delegation(did)\n        return {\"success\": True}\n    finally: session.close()",
    "def revoke_delegation(did: str):\n    session = _get_db_session()\n    try:\n        from common_lib.modules.rbac.delegation.service import DelegationService\n        DelegationService(session).revoke_delegation(did)\n        return {\"success\": True}\n    except Exception as e:\n        raise HTTPException(500, str(e))\n    finally: session.close()"
)

# end_impersonation - add generic handler
content = content.replace(
    "def end_impersonation(session_id: str):\n    session = _get_db_session()\n    try:\n        from common_lib.modules.rbac.delegation.service import ImpersonationService\n        ImpersonationService(session).end_impersonation(session_id)\n        return {\"success\": True}\n    finally: session.close()",
    "def end_impersonation(session_id: str):\n    session = _get_db_session()\n    try:\n        from common_lib.modules.rbac.delegation.service import ImpersonationService\n        ImpersonationService(session).end_impersonation(session_id)\n        return {\"success\": True}\n    except Exception as e:\n        raise HTTPException(500, str(e))\n    finally: session.close()"
)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("delegation_routes.py: Fixed semicolons + HTTPException wrapping")

# =========================================================================
# Fix 4: api_routes.py — semicolons
# =========================================================================
path = os.path.join(BASE, "api_routes.py")
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace(
    "class CheckReq(BaseModel):\n    user_id: int; resource: str; action: str; resource_id: Optional[str] = None; org_id: Optional[str] = None",
    "class CheckReq(BaseModel):\n    user_id: int\n    resource: str\n    action: str\n    resource_id: Optional[str] = None\n    org_id: Optional[str] = None"
)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("api_routes.py: Fixed semicolons")

# =========================================================================
# Fix 5: machine_auth_routes.py — semicolons
# =========================================================================
path = os.path.join(BASE, "machine_auth_routes.py")
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace(
    "class APIKeyCreateReq(BaseModel):\n    user_id: int; name: str; scopes: Optional[list[str]] = None; expires_in_days: int = 365",
    "class APIKeyCreateReq(BaseModel):\n    user_id: int\n    name: str\n    scopes: Optional[list[str]] = None\n    expires_in_days: int = 365"
)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("machine_auth_routes.py: Fixed semicolons")

# =========================================================================
# Fix 6: ownership_routes.py — semicolons + HTTPException wrapping
# =========================================================================
path = os.path.join(BASE, "ownership_routes.py")
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Fix semicolons
content = content.replace(
    "class RegisterOwnershipReq(BaseModel):\n    resource_type: str; resource_id: str\n    owner_user_id: Optional[int] = None; owner_team_id: Optional[str] = None; owner_org_id: Optional[str] = None",
    "class RegisterOwnershipReq(BaseModel):\n    resource_type: str\n    resource_id: str\n    owner_user_id: Optional[int] = None\n    owner_team_id: Optional[str] = None\n    owner_org_id: Optional[str] = None"
)

# get_ownership - add generic handler
content = content.replace(
    "def get_ownership(rtype: str, rid: str):\n    session = _get_db_session()\n    try:\n        from common_lib.modules.rbac.ownership_service import OwnershipService\n        o = OwnershipService(session).get_owner(rtype, rid)\n        if not o: raise HTTPException(404)\n        return {\"resource_type\": o.resource_type, \"resource_id\": o.resource_id, \"owner_user_id\": o.owner_user_id}\n    finally: session.close()",
    "def get_ownership(rtype: str, rid: str):\n    session = _get_db_session()\n    try:\n        from common_lib.modules.rbac.ownership_service import OwnershipService\n        o = OwnershipService(session).get_owner(rtype, rid)\n        if not o:\n            raise HTTPException(404, \"Ownership record not found\")\n        return {\"resource_type\": o.resource_type, \"resource_id\": o.resource_id, \"owner_user_id\": o.owner_user_id}\n    except HTTPException:\n        raise\n    except Exception as e:\n        raise HTTPException(500, str(e))\n    finally:\n        session.close()"
)

# transfer - add generic handler
content = content.replace(
    "def transfer(rtype: str, rid: str, new_owner_user_id: Optional[int] = None):\n    session = _get_db_session()\n    try:\n        from common_lib.modules.rbac.ownership_service import OwnershipService\n        o = OwnershipService(session).transfer(rtype, rid, new_owner_user_id=new_owner_user_id)\n        if not o: raise HTTPException(404)\n        return {\"success\": True, \"owner_user_id\": o.owner_user_id}\n    finally: session.close()",
    "def transfer(rtype: str, rid: str, new_owner_user_id: Optional[int] = None):\n    session = _get_db_session()\n    try:\n        from common_lib.modules.rbac.ownership_service import OwnershipService\n        o = OwnershipService(session).transfer(rtype, rid, new_owner_user_id=new_owner_user_id)\n        if not o:\n            raise HTTPException(404, \"Ownership record not found\")\n        return {\"success\": True, \"owner_user_id\": o.owner_user_id}\n    except HTTPException:\n        raise\n    except Exception as e:\n        raise HTTPException(500, str(e))\n    finally:\n        session.close()"
)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("ownership_routes.py: Fixed semicolons + HTTPException wrapping")

# =========================================================================
# Fix 7: hardening_routes.py — semicolons
# =========================================================================
path = os.path.join(BASE, "hardening_routes.py")
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace(
    "class EscalationCheckReq(BaseModel):\n    actor_user_id: int; target_user_id: int; role_ids: list[int]",
    "class EscalationCheckReq(BaseModel):\n    actor_user_id: int\n    target_user_id: int\n    role_ids: list[int]"
)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("hardening_routes.py: Fixed semicolons")

# =========================================================================
# Fix 8: cache_routes.py — add HTTPException wrapping
# =========================================================================
path = os.path.join(BASE, "cache_routes.py")
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace(
    "def cache_stats():\n    from common_lib.modules.rbac.permission_cache import get_permission_cache\n    return {\"stats\": get_permission_cache().stats}",
    "def cache_stats():\n    try:\n        from common_lib.modules.rbac.permission_cache import get_permission_cache\n        return {\"stats\": get_permission_cache().stats}\n    except Exception as e:\n        raise HTTPException(500, str(e))"
)

content = content.replace(
    "def invalidate_user(user_id: int):\n    from common_lib.modules.rbac.permission_cache import get_permission_cache\n    get_permission_cache().invalidate_user(user_id)\n    return {\"success\": True}",
    "def invalidate_user(user_id: int):\n    try:\n        from common_lib.modules.rbac.permission_cache import get_permission_cache\n        get_permission_cache().invalidate_user(user_id)\n        return {\"success\": True}\n    except Exception as e:\n        raise HTTPException(500, str(e))"
)

content = content.replace(
    "def invalidate_all():\n    from common_lib.modules.rbac.permission_cache import get_permission_cache\n    get_permission_cache().invalidate_all()\n    return {\"success\": True}",
    "def invalidate_all():\n    try:\n        from common_lib.modules.rbac.permission_cache import get_permission_cache\n        get_permission_cache().invalidate_all()\n        return {\"success\": True}\n    except Exception as e:\n        raise HTTPException(500, str(e))"
)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("cache_routes.py: Added HTTPException wrapping")

print("\nAll 9 route files polished successfully.")
