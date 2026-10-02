"""Request-scoped caller identity for the MCP tool surface.

Why this module exists
----------------------
``app/mcp/**`` had **no request context at all**: no ``ContextVar``, and
``server.py`` performed no token verification. ``user_get_current`` was
written in response to that void and answered every caller with a hardcoded
``{"id": "system", "role": "admin", "permissions": ["*"]}`` behind a comment
conceding it was a mock. The missing context is the actual defect; this module
supplies it.

What the transport actually offers (verified, not assumed)
----------------------------------------------------------
There are three ways an MCP tool call reaches this server, and they are NOT
equally authenticated:

1. ``POST /api/v1/mcp/tools/call`` (``app/mcp/routes.py``). The router is
   declared ``"auth": True`` in ``ROUTER_DEFINITIONS``, which makes
   ``mount_router_entry`` apply ``global_deps`` -- and ``global_deps`` is
   ``[Depends(get_current_active_user)]`` when ``DEV_MODE`` is off. So the HTTP
   transport *does* verify a bearer token. But the resulting ``User`` object
   was never reachable from inside a tool: FastMCP hands the tool only its
   declared arguments. That gap is what made the fabricated identity
   necessary-looking.

2. ``/mcp/transport`` SSE (``app/main.py:1629``). Mounted with
   ``app.mount(...)``, which is a raw ASGI mount and **bypasses the router
   dependency mechanism entirely**. No ``get_current_active_user`` runs. There
   is no credential to verify. (Reported, not edited: ``app/main.py`` is
   off-limits to this change.)

3. stdio (``app/mcp/standalone_node_server.py``). A local subprocess;
   registration is inherently trusted. Note it registers only the ``@node``
   bridge, so ``user_get_current`` is not reachable this way at all.

Design rules
------------
1. **Fail closed.** No bound context means *anonymous*, not admin. The
   ContextVar default is "no credential", and every getter resolves that to a
   real anonymous ``Principal`` -- never a placeholder identity.
2. **A service identity is requested, never inferred.**
   ``resolve_mcp_principal`` passes ``allow_service_identity=False`` so an
   unauthenticated MCP caller cannot silently inherit ambient service
   privilege. A tool that genuinely needs the service principal must ask for it
   explicitly (``include_service_identity=True``), which is a visible,
   auditable caller decision.
3. **One verification implementation.** Token verification is delegated to
   ``common_lib.modules.auth.identity_context.resolve_principal``, the same
   code path ``get_current_active_user`` uses for HTTP. This module never
   decodes a token itself, so there is no second, weaker verifier.
4. **Default-ON.** There is no flag that re-enables the permissive behaviour.
"""

from __future__ import annotations

import logging
from contextvars import ContextVar, Token
from typing import Optional

from common_lib.modules.auth.identity_context import (
    ANONYMOUS,
    Principal,
    resolve_principal,
    service_identity,
)

logger = logging.getLogger("app.mcp.identity")

# The bound principal for the current request. `None` means "no MCP request
# context is active" — the transport presented no verifiable credential. It is
# deliberately NOT defaulted to an admin; the getter below turns it into an
# explicit anonymous principal.
_principal_var: ContextVar[Optional[Principal]] = ContextVar(
    "mcp_current_principal", default=None
)


def bind_principal(principal: Principal) -> Token:
    """Bind ``principal`` as the caller for the current request scope.

    Returns the reset token; callers MUST pass it to :func:`reset_principal`
    in a ``finally`` so a pooled worker thread never leaks one request's
    identity into the next request it serves.
    """
    return _principal_var.set(principal)


def reset_principal(token: Token) -> None:
    """Restore the previous request scope. Never raises."""
    try:
        _principal_var.reset(token)
    except Exception:  # pragma: no cover - defensive
        logger.debug("MCP principal reset failed (token from another context)")


def anonymous_principal(reason: str = "no MCP request context is active") -> Principal:
    """The explicit anonymous principal: unprivileged, unauthenticated."""
    return Principal(
        id=ANONYMOUS,
        role=ANONYMOUS,
        permissions=(),
        is_authenticated=False,
        is_service=False,
        source="none",
        reason=reason,
    )


def current_principal() -> Principal:
    """Return the caller bound to this request scope, or anonymous.

    This is the function MCP tools call. It cannot return an admin: it either
    returns a principal that was established from a verified credential, or
    the anonymous principal.
    """
    principal = _principal_var.get()
    if principal is None:
        return anonymous_principal()
    return principal


def resolve_mcp_principal(authorization_header: Optional[str]) -> Principal:
    """Verify an ``Authorization`` header and return the calling principal.

    Fails closed: an absent, malformed, expired or badly-signed token all
    yield the anonymous principal. ``allow_service_identity=False`` is
    deliberate -- an unauthenticated MCP caller must not be able to pick up
    ambient service privilege by omission.
    """
    header = (authorization_header or "").strip()
    if not header:
        return anonymous_principal(reason="no Authorization header presented")
    try:
        return resolve_principal(header, allow_service_identity=False)
    except (
        Exception
    ) as exc:  # pragma: no cover - resolve_principal already fails closed
        logger.warning("MCP principal resolution raised unexpectedly: %s", exc)
        return anonymous_principal(reason="credential could not be verified")


def request_service_identity() -> Optional[Principal]:
    """Return the configured service identity, or None if not enabled.

    Only ever called from an EXPLICIT caller request. Nothing in the request
    path calls this implicitly.
    """
    principal = service_identity()
    return principal if principal.is_authenticated else None


__all__ = [
    "bind_principal",
    "reset_principal",
    "current_principal",
    "anonymous_principal",
    "resolve_mcp_principal",
    "request_service_identity",
    "Principal",
]
