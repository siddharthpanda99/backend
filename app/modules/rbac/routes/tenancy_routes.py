"""RBAC Tenancy API routes — SSOT 08."""
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


class OrgCreate(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None

@router.post("/orgs")
def create_org(req: OrgCreate):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.tenant_service import OrganizationService
        org = OrganizationService(session).create(name=req.name, slug=req.slug, description=req.description)
        return {"id": org.id, "name": org.name, "slug": org.slug}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        session.close()

@router.get("/orgs")
def list_orgs():
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.tenant_service import OrganizationService
        orgs = OrganizationService(session).list_orgs()
        return {"organizations": [{"id": o.id, "name": o.name, "slug": o.slug} for o in orgs], "total": len(orgs)}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        session.close()

@router.get("/orgs/{org_id}")
def get_org(org_id: int):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.tenant_service import OrganizationService
        org = OrganizationService(session).get_by_id(org_id)
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
def delete_org(org_id: int):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.tenant_service import OrganizationService
        OrganizationService(session).delete(org_id)
        return {"success": True}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        session.close()

@router.post("/orgs/{org_id}/members")
def add_org_member(org_id: int, user_id: int, role: str = "member"):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.tenant_service import OrganizationService
        m = OrganizationService(session).add_member(org_id, user_id, role)
        return {"user_id": m.user_id, "role": m.role}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        session.close()

@router.get("/orgs/{org_id}/members")
def list_org_members(org_id: int):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.tenant_service import OrganizationService
        members = OrganizationService(session).list_members(org_id)
        return {"members": [{"user_id": m.user_id, "role": m.role} for m in members], "total": len(members)}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        session.close()

@router.post("/teams")
def create_team(name: str, slug: str, org_id: int):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.tenant_service import TeamServiceRBAC
        t = TeamServiceRBAC(session).create(name=name, slug=slug, org_id=org_id)
        return {"id": t.id, "name": t.name, "slug": t.slug}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        session.close()

@router.get("/teams")
def list_teams(org_id: Optional[int] = None):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.tenant_service import TeamServiceRBAC
        teams = TeamServiceRBAC(session).list_teams(org_id=org_id)
        return {"teams": [{"id": t.id, "name": t.name} for t in teams], "total": len(teams)}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        session.close()
