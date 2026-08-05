"""FastAPI routes for RBAC Integrations — SCIM, SSO, Directory, API Auth."""

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/integrations", tags=["rbac-integrations"])


def _get_db_session():
    from sqlmodel import Session
    from common_lib.modules.integration.adapters.database_adapter import get_db_port
    engine = get_db_port().get_engine()
    return Session(engine)


@router.post("/scim/provision")
def scim_provision_user(provider_id: str, username: str, email: str = "", groups: list = None):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.integrations.service import SCIMService
        svc = SCIMService(session)
        user_data = {"userName": username, "emails": [{"value": email}] if email else [], "groups": groups or [], "active": True}
        result = svc.provision_user(provider_id, user_data)
        if "error" in result:
            raise HTTPException(400, result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        session.close()


@router.post("/scim/sync-groups")
def scim_sync_groups(provider_id: str, groups: list):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.integrations.service import SCIMService
        svc = SCIMService(session)
        result = svc.sync_groups(provider_id, groups)
        if "error" in result:
            raise HTTPException(400, result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        session.close()


@router.post("/sso/configure")
def sso_configure(provider_type: str, issuer_url: str, client_id: str, client_secret: str, jit_provisioning: bool = False):
    try:
        from common_lib.modules.rbac.integrations.service import SSOService, SSOConfig
        svc = SSOService()
        config = SSOConfig(provider=provider_type, issuer_url=issuer_url, client_id=client_id, client_secret=client_secret, jit_provisioning=jit_provisioning)
        if provider_type == "saml":
            pid = svc.configure_saml(config)
        elif provider_type == "oidc":
            pid = svc.configure_oidc(config)
        else:
            raise HTTPException(400, f"Unsupported provider: {provider_type}")
        return {"provider_id": pid, "provider_type": provider_type}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/sso/providers")
def sso_list_providers():
    from common_lib.modules.rbac.integrations.service import SSOService
    svc = SSOService()
    return {"providers": svc.list_providers()}


@router.post("/directory/sync")
def directory_trigger_sync(dir_id: str):
    from common_lib.modules.rbac.integrations.service import DirectorySyncService
    svc = DirectorySyncService()
    result = svc.trigger_sync(dir_id)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.post("/api/validate-token")
def api_validate_token(token: str):
    from common_lib.modules.rbac.integrations.service import APIAuthService
    svc = APIAuthService()
    result = svc.validate_api_token(token)
    if result:
        return {"valid": True, "metadata": result}
    return {"valid": False, "metadata": None}
