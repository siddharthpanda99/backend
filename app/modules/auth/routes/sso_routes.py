"""Auth SSO — FastAPI routes for single sign-on and OAuth provider linking.

Provides OAuth account linking/unlinking, provider listing, and SSO config.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlmodel import Session
from pydantic import BaseModel

from common_lib.modules.data_storage.database.connection import get_session
from app.modules.auth.dependencies import get_current_active_user
from common_lib.modules.auth.users.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth/sso", tags=["auth-sso"])


class LinkOAuthRequest(BaseModel):
    provider_name: str
    provider_account_id: str
    provider_email: Optional[str] = None
    provider_username: Optional[str] = None


class ConfigureSSORequest(BaseModel):
    sso_only: Optional[bool] = None
    allow_password_login: Optional[bool] = None
    default_role_id: Optional[str] = None
    allowed_domains: Optional[list[str]] = None


@router.get("/providers")
def list_providers(
    session: Session = Depends(get_session),
):
    """List all enabled OAuth/SSO providers."""
    from common_lib.modules.auth.sso.service import SSOService
    svc = SSOService(session)
    return {"providers": svc.list_providers()}


@router.get("/links")
def list_oauth_links(
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session),
):
    """List OAuth accounts linked to the current user."""
    from common_lib.modules.auth.sso.service import SSOService
    svc = SSOService(session)
    return {"links": svc.list_user_oauth_links(str(current_user.id))}


@router.post("/links")
def link_oauth_account(
    data: LinkOAuthRequest,
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session),
):
    """Link an OAuth account to the current user."""
    from common_lib.modules.auth.sso.service import SSOService
    svc = SSOService(session)
    try:
        return svc.link_oauth_account(
            str(current_user.id),
            data.provider_name,
            data.provider_account_id,
            provider_email=data.provider_email,
            provider_username=data.provider_username,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/links/{link_id}")
def unlink_oauth_account(
    link_id: str,
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session),
):
    """Unlink an OAuth account."""
    from common_lib.modules.auth.sso.service import SSOService
    svc = SSOService(session)
    ok = svc.unlink_oauth_account(link_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Link not found")
    return {"success": True}


@router.get("/config/{org_id}")
def get_sso_config(
    org_id: str,
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session),
):
    """Get SSO configuration for an organization."""
    from common_lib.modules.auth.sso.service import SSOService
    svc = SSOService(session)
    config = svc.get_sso_config(org_id)
    if not config:
        raise HTTPException(status_code=404, detail="SSO not configured")
    return config


@router.put("/config/{org_id}")
def configure_sso(
    org_id: str,
    data: ConfigureSSORequest,
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session),
):
    """Configure SSO settings for an organization."""
    from common_lib.modules.auth.sso.service import SSOService
    svc = SSOService(session)
    return svc.configure_sso(
        org_id,
        sso_only=data.sso_only,
        allow_password_login=data.allow_password_login,
        default_role_id=data.default_role_id,
        allowed_domains=data.allowed_domains,
    )
