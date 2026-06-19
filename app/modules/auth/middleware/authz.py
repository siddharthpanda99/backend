import logging
from typing import Any
from fastapi import HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from common_lib.modules.auth.authorization import (
    AuthzChecker,
    SubjectType,
    SPIFFEIdentity,
    identity_service,
    permission_registry_service,
)

logger = logging.getLogger(__name__)

WHITELISTED_PATHS = {
    "/api/v1/auth/login",
    "/api/v1/auth/register",
    "/api/v1/auth/access-token",
    "/api/v1/auth/forgot-password",
    "/api/v1/auth/reset-password",
    "/api/v1/auth/verify-email",
    "/api/v1/auth/resend-verification",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/api/v1/authz/health",
    "/api/v1/authz/permission-rules",
    "/api/v1/authz/permission-rules/",
}


class AuthzMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Any) -> Response:
        if request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path
        if any(path.startswith(w) for w in WHITELISTED_PATHS):
            return await call_next(request)

        subject_id = request.headers.get("X-Subject-Id", "")
        subject_type_str = request.headers.get("X-Subject-Type", "human")
        tenant_id = request.headers.get("X-Tenant-Id", "default")

        try:
            subject_type = SubjectType(subject_type_str)
        except ValueError:
            subject_type = SubjectType.HUMAN

        spiffe = request.headers.get("X-Spiffe-Id")
        if spiffe:
            identity = SPIFFEIdentity.from_string(spiffe)
            if not identity.validate():
                logger.warning("Invalid SPIFFE ID: %s", spiffe)

        if not subject_id:
            bearer = request.headers.get("Authorization", "")
            if bearer.startswith("Bearer "):
                token = bearer[7:]
                from common_lib.modules.auth.authorization import token_service

                tok = token_service.verify_token(token)
                if tok:
                    subject_id = tok.subject_id
                    subject_type = (
                        tok.subject_type
                        if hasattr(tok, "subject_type")
                        else SubjectType.AGENT
                    )

        checker = AuthzChecker(
            subject_id=subject_id or "anonymous",
            subject_type=subject_type,
            tenant_id=tenant_id,
        )
        setattr(request.state, "authz", checker)
        if subject_id:
            identity = identity_service.get_identity(subject_id)
            setattr(request.state, "identity", identity)
        else:
            setattr(request.state, "identity", None)

        # Permission registry check — thin delegation to common_lib
        if subject_id:
            error = permission_registry_service.check_permission_for_request(
                method=request.method,
                path=path,
                subject_id=subject_id,
                tenant_id=tenant_id,
            )
            if error:
                raise HTTPException(status_code=403, detail=error)

        response = await call_next(request)
        return response
