from typing import Annotated
from fastapi import Depends, HTTPException, Request, status
from sqlmodel import Session
from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.users.models import User
from common_lib.modules.auth.authorization import (
    AuthzChecker,
    PlatformIdentity,
    identity_service,
    resolve_identity_from_user,
    verify_role_membership,
    build_authz_checker,
    check_permission,
    verify_tenant_isolation,
)
from common_lib.modules.rbac.audit_service import RBACAuditService
from common_lib.modules.rbac.permission_cache import get_permission_cache


async def get_current_active_user(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> User:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
    token = auth_header[7:]
    try:
        from common_lib.modules.auth.security import decode_access_token

        payload = decode_access_token(token)
        user_id = payload.get("sub") or payload.get("user_id")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
            )
        user = session.get(User, user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
            )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user"
            )
        resolve_identity_from_user(
            user_id=str(user.id),
            display_name=user.full_name or user.username or user.email,
            tenant_id=getattr(user, "tenant_id", "default"),
            email=user.email,
        )
        return user
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


async def get_current_identity(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> PlatformIdentity:
    user = await get_current_active_user(request, session)
    identity = identity_service.get_identity(str(user.id))
    if identity is None:
        identity = resolve_identity_from_user(
            user_id=str(user.id),
            display_name=user.full_name or user.username or user.email,
            tenant_id=getattr(user, "tenant_id", "default"),
            email=user.email,
        )
    return identity


class RoleChecker:
    def __init__(self, allowed_roles: list[str]):
        self.allowed_roles = allowed_roles

    async def __call__(
        self, identity: Annotated[PlatformIdentity, Depends(get_current_identity)]
    ) -> None:
        if verify_role_membership(identity, self.allowed_roles):
            return
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Requires one of roles: {self.allowed_roles}",
        )


async def get_tenant_id(
    identity: Annotated[PlatformIdentity, Depends(get_current_identity)],
) -> str:
    return identity.tenant_id


async def get_authz_checker(
    request: Request,
    identity: Annotated[PlatformIdentity, Depends(get_current_identity)],
) -> AuthzChecker:
    checker: AuthzChecker | None = getattr(request.state, "authz", None)
    if checker is None:
        checker = build_authz_checker(
            subject_id=identity.subject_id,
            subject_type=identity.subject_type,
            tenant_id=identity.tenant_id,
        )
        setattr(request.state, "authz", checker)
    return checker


def require_permission(action: str, resource_id: str = "*", resource_type: str = "*"):
    async def dependency(
        checker: Annotated[AuthzChecker, Depends(get_authz_checker)],
        identity: Annotated[PlatformIdentity, Depends(get_current_identity)],
        request: Request,
    ) -> None:
        try:
            check_permission(checker, action, resource_id, resource_type)
            audit = RBACAuditService()
            audit.log_permission_check(
                user_id=int(identity.subject_id),
                resource=resource_type,
                action=action,
                allowed=True,
                endpoint=str(request.url.path),
            )
        except Exception:
            audit = RBACAuditService()
            audit.log_permission_check(
                user_id=int(identity.subject_id),
                resource=resource_type,
                action=action,
                allowed=False,
                resource_id=resource_id,
                endpoint=str(request.url.path),
            )
            raise

    return Depends(dependency)


def require_tenant(
    identity: Annotated[PlatformIdentity, Depends(get_current_identity)],
) -> str:
    return verify_tenant_isolation(identity)
