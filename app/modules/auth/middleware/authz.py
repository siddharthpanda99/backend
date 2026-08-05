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


def _is_trusted_proxy(request: Request, trusted_secret: str) -> bool:
    """Return True when the request comes from a verified, trusted reverse proxy.

    The proxy must present the shared secret in X-Proxy-Secret.
    When trusted_secret is empty, proxy-header identity is disabled.
    """
    if not trusted_secret:
        return False
    return request.headers.get("X-Proxy-Secret", "") == trusted_secret


class AuthzMiddleware(BaseHTTPMiddleware):
    """Extract and validate request identity on every non-whitelisted request.

    Trust boundary (P0-4 fix)
    -------------------------
    Identity is resolved in this priority order:

    1. Validated JWT from ``Authorization: Bearer <token>`` header.
       This is the primary identity source for all authenticated clients.

    2. X-Subject-Id / X-Subject-Type / X-Tenant-Id headers, accepted ONLY when:
       a. DEV_MODE=True  (local development — any caller may set these), OR
       b. The request carries a valid X-Proxy-Secret matching TRUSTED_PROXY_SECRET
          (authenticated reverse-proxy path, e.g. internal service mesh).

    Identity headers from untrusted callers are silently ignored so that an
    unauthenticated request still routes as ``anonymous``, preserving the
    existing behaviour for public endpoints while preventing spoofing.
    """

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        if request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path
        if any(path.startswith(w) for w in WHITELISTED_PATHS):
            return await call_next(request)

        # Lazily import settings to avoid circular imports at module load time.
        from app.core.settings import get_settings
        _settings = get_settings()

        subject_id: str = ""
        subject_type: SubjectType = SubjectType.HUMAN
        tenant_id: str = "default"

        # --- Step 1: Primary identity from validated JWT ---
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
                # Prefer tenant embedded in the JWT; fall back to header only from trusted source
                if hasattr(tok, "tenant_id") and tok.tenant_id:
                    tenant_id = tok.tenant_id

        # --- Step 2: Accept identity headers from DEV_MODE or trusted proxy only ---
        # P0-4 FIX: Previously these headers were accepted from any caller, enabling
        # identity spoofing. They are now restricted to trusted sources.
        allow_proxy_headers = _settings.DEV_MODE or _is_trusted_proxy(
            request, _settings.TRUSTED_PROXY_SECRET
        )

        if allow_proxy_headers:
            header_subject = request.headers.get("X-Subject-Id", "")
            if header_subject:
                # Header identity overrides JWT only when explicitly trusted.
                subject_id = header_subject
                try:
                    subject_type = SubjectType(
                        request.headers.get("X-Subject-Type", "human")
                    )
                except ValueError:
                    subject_type = SubjectType.HUMAN
            header_tenant = request.headers.get("X-Tenant-Id", "")
            if header_tenant:
                tenant_id = header_tenant
        elif request.headers.get("X-Subject-Id"):
            logger.warning(
                "Untrusted X-Subject-Id header ignored from %s %s — "
                "not in DEV_MODE and no valid X-Proxy-Secret",
                request.method,
                path,
            )

        # --- SPIFFE validation (informational — does not grant identity) ---
        spiffe = request.headers.get("X-Spiffe-Id")
        if spiffe:
            identity = SPIFFEIdentity.from_string(spiffe)
            if not identity.validate():
                logger.warning("Invalid SPIFFE ID: %s", spiffe)

        if _settings.DISABLE_AUTH and not subject_id:
            subject_id = "1"
            tenant_id = "default"
            subject_type = SubjectType.HUMAN

        # --- Attach authz context to request state ---
        checker = AuthzChecker(
            subject_id=subject_id or "anonymous",
            subject_type=subject_type,
            tenant_id=tenant_id,
        )
        setattr(request.state, "authz", checker)
        # Convenience field used by thin routes (creators, app builder, etc.)
        setattr(request.state, "user_id", subject_id or None)
        setattr(request.state, "tenant_id", tenant_id)
        if subject_id:
            resolved_identity = identity_service.get_identity(subject_id)
            setattr(request.state, "identity", resolved_identity)
        else:
            setattr(request.state, "identity", None)

        # --- Permission registry check — thin delegation to common_lib ---
        if subject_id and not _settings.DISABLE_AUTH:
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

