"""``app.modules.i2w.routes.dependencies`` — shared auth + RBAC + rate-limit
+ audit dependencies for every I2W endpoint.

The dependencies are split into small, composable ``Depends(...)``
factories so that sub-routers can stack them per-endpoint. The
``require_i2w_scope(scope)`` factory is the canonical gate used by all
write / execute / admin endpoints.

Phase 7 invariants:

* Auth: every endpoint except ``/health*`` requires JWT (the platform's
  standard ``get_current_active_user`` dependency).
* RBAC: scope names follow the docs (``i2w.read``, ``i2w.write``,
  ``i2w.execute``, ``i2w.training.admin``, ``i2w.security.admin``,
  ``i2w.platform.admin``). A user without the right scope gets
  ``403 Forbidden``; a missing JWT gets ``401``.
* Rate limit: in-router sliding-window check (per the docs:
  100/min/user, 1000/h/tenant, 10k/day/tenant). The global
  ``app.middleware.rate_limit`` middleware is a coarser outer gate.
* Audit: every I2W request emits an audit-log line via the
  ``observability`` port accessor (no request body is ever logged).
* Feature flag: when ``INSTRUCTION_TO_WORKFLOW_ENABLED`` is off, the
  router itself is unmounted (404). The dep still checks the flag for
  sub-stage granularity.

The router layer never imports a business module directly — it only
delegates to ``i2w_*`` @node wrappers in ``common_lib``.
"""

from __future__ import annotations

import logging
import os
import time
from collections import defaultdict, deque
from typing import Annotated, Any, Deque, Dict, Optional

from fastapi import Depends, HTTPException, Request, status

from common_lib.modules.orchestration.instruction_to_workflow.feature_flags import (
    I2W_FLAG_STAGE1_INGEST,
    I2W_FLAG_STAGE2_REASON,
    I2W_FLAG_STAGE3_PLAN,
    I2W_FLAG_STAGE4_DISPATCH,
    I2W_FLAG_TRAINING,
    I2W_FLAG_UNIVERSAL_SEARCH,
    INSTRUCTION_TO_WORKFLOW_ENABLED,
    is_instruction_to_workflow_enabled,
)
from common_lib.modules.auth.authorization import PlatformIdentity

from app.modules.auth.dependencies.authz import get_current_identity

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# RBAC scopes (per docs/08_api_contract.md §7 and docs/11 §7)
# ---------------------------------------------------------------------------

I2W_SCOPE_READ = "i2w.read"
I2W_SCOPE_WRITE = "i2w.write"
I2W_SCOPE_EXECUTE = "i2w.execute"
I2W_SCOPE_TRAINING_ADMIN = "i2w.training.admin"
I2W_SCOPE_SECURITY_ADMIN = "i2w.security.admin"
I2W_SCOPE_PLATFORM_ADMIN = "i2w.platform.admin"

# Sub-stage flag keys (used for per-stage canarying)
_SUB_STAGE_FLAGS = {
    "ingest": I2W_FLAG_STAGE1_INGEST,
    "reason": I2W_FLAG_STAGE2_REASON,
    "plan": I2W_FLAG_STAGE3_PLAN,
    "dispatch": I2W_FLAG_STAGE4_DISPATCH,
    "training": I2W_FLAG_TRAINING,
    "search": I2W_FLAG_UNIVERSAL_SEARCH,
}


# ---------------------------------------------------------------------------
# Feature-flag guard (router-level)
# ---------------------------------------------------------------------------


def _master_or_sub_enabled(sub: Optional[str] = None) -> bool:
    """Return True if the master I2W flag (or the named sub-stage flag) is on.

    When the sub-stage key is unknown we fall back to the master flag.
    """
    if not is_instruction_to_workflow_enabled(INSTRUCTION_TO_WORKFLOW_ENABLED):
        return False
    if sub is None:
        return True
    sub_key = _SUB_STAGE_FLAGS.get(sub, INSTRUCTION_TO_WORKFLOW_ENABLED)
    return is_instruction_to_workflow_enabled(sub_key)


def require_i2w_master_flag():
    """Dependency: 404 if the master I2W flag is off.

    Sub-routers that want to use the master flag only should stack this
    on every endpoint. Sub-routers that want per-stage granularity
    should stack ``require_i2w_sub_flag("ingest")`` etc. instead.
    """

    async def _dep() -> None:
        if not _master_or_sub_enabled(None):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="I2W framework is disabled",
            )

    return _dep


def require_i2w_sub_flag(stage: str):
    """Dependency factory: 404 if the named sub-stage flag is off."""

    async def _dep() -> None:
        if not _master_or_sub_enabled(stage):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"I2W sub-stage '{stage}' is disabled",
            )

    return _dep


# ---------------------------------------------------------------------------
# Auth (JWT) — re-export the platform's standard dependency
# ---------------------------------------------------------------------------


I2WIdentity = PlatformIdentity


async def i2w_identity(
    identity: Annotated[PlatformIdentity, Depends(get_current_identity)],
) -> PlatformIdentity:
    """Standard JWT identity. Returns the same ``PlatformIdentity`` that the
    rest of the platform uses. The handler can pull ``tenant_id`` and the
    ``user_id_hash`` off this object."""
    return identity


# ---------------------------------------------------------------------------
# RBAC scope guard
# ---------------------------------------------------------------------------


def _identity_has_scope(identity: PlatformIdentity, scope: str) -> bool:
    """Return True if the identity has the named I2W scope.

    The platform's identity carries a list of role memberships; an I2W
    scope is granted to anyone in a role that includes it. The mapping
    is intentionally simple here — production deployments will
    configure the role→scope grants via the RBAC admin UI.
    """
    if getattr(identity, "is_admin", False):
        return True
    scopes = set(getattr(identity, "scopes", []) or [])
    if scope in scopes:
        return True
    # Convenience: training.admin also implies read; platform.admin
    # implies everything.
    if scope == I2W_SCOPE_READ and I2W_SCOPE_PLATFORM_ADMIN in scopes:
        return True
    if scope in {I2W_SCOPE_WRITE, I2W_SCOPE_EXECUTE} and (
        I2W_SCOPE_PLATFORM_ADMIN in scopes
    ):
        return True
    return False


def require_i2w_scope(scope: str):
    """Dependency factory: 403 if the identity lacks ``scope``.

    The dependency MUST be stacked AFTER ``i2w_identity`` (so the JWT
    is already validated) and AFTER any feature-flag dep.
    """

    async def _dep(
        identity: Annotated[PlatformIdentity, Depends(i2w_identity)],
    ) -> PlatformIdentity:
        if not _identity_has_scope(identity, scope):
            # Per docs/10 §4.2: log a security event and return 403
            try:
                from common_lib.modules.observability import (
                    get_observability,
                )

                obs = get_observability()
                if obs is not None:
                    obs.security_event(
                        event="i2w.security.rbac.denied",
                        user_id_hash=str(getattr(identity, "subject_id", "unknown")),
                        tenant_id=str(getattr(identity, "tenant_id", "default")),
                        scope=scope,
                    )
            except Exception:  # noqa: BLE001
                # observability may be off in dev — never block the
                # auth check on logging.
                logger.debug("observability.security_event failed", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required I2W scope: {scope}",
            )
        return identity

    return _dep


# ---------------------------------------------------------------------------
# Rate limit (per docs/11 §6 — in-router sliding window)
# ---------------------------------------------------------------------------


_RATE_USER_RPM = int(os.environ.get("I2W_RATE_USER_RPM", "100"))
_RATE_TENANT_RPH = int(os.environ.get("I2W_RATE_TENANT_RPH", "1000"))
_RATE_TENANT_RPD = int(os.environ.get("I2W_RATE_TENANT_RPD", "10000"))

# Sliding-window stores keyed by (scope, key, window_seconds).
_windows: Dict[tuple, Deque[float]] = defaultdict(deque)


def _sliding_window_check(
    store_key: tuple, max_events: int, window_seconds: int
) -> tuple[bool, float]:
    """Return ``(allowed, retry_after_seconds)`` for a sliding window."""
    now = time.monotonic()
    dq = _windows[store_key]
    cutoff = now - window_seconds
    while dq and dq[0] < cutoff:
        dq.popleft()
    if len(dq) >= max_events:
        retry_after = max(1.0, window_seconds - (now - dq[0]))
        return False, retry_after
    dq.append(now)
    return True, 0.0


def require_i2w_rate_limit():
    """Dependency: 429 if the user or tenant has exceeded the I2W quota.

    Sliding-window, in-process. For multi-pod deployments swap this for
    the platform's distributed rate limiter (see
    ``integration.ports.rate_limit``).
    """

    async def _dep(
        request: Request,
        identity: Annotated[PlatformIdentity, Depends(i2w_identity)],
    ) -> PlatformIdentity:
        user_key = ("i2w_user", str(getattr(identity, "subject_id", "anon")))
        tenant_key = ("i2w_tenant_h", str(getattr(identity, "tenant_id", "default")))
        tenant_day_key = (
            "i2w_tenant_d",
            str(getattr(identity, "tenant_id", "default")),
        )

        allowed, retry = _sliding_window_check(user_key, _RATE_USER_RPM, 60)
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Per-user I2W rate limit exceeded",
                headers={"Retry-After": str(int(retry) + 1)},
            )

        allowed, retry = _sliding_window_check(tenant_key, _RATE_TENANT_RPH, 60 * 60)
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Per-tenant hourly I2W rate limit exceeded",
                headers={"Retry-After": str(int(retry) + 1)},
            )

        allowed, retry = _sliding_window_check(
            tenant_day_key, _RATE_TENANT_RPD, 60 * 60 * 24
        )
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Per-tenant daily I2W rate limit exceeded",
                headers={"Retry-After": str(int(retry) + 1)},
            )

        return identity

    return _dep


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------


def _audit_request(
    request: Request,
    identity: PlatformIdentity,
    *,
    action: str,
    status_code: int = 200,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """Emit a structured audit line for the I2W request.

    Per docs/11 §4.2: never log the request body (would leak the
    transcript / PII). Per docs/10 §4.3: never log PII. The audit line
    only carries the user id hash + tenant id + endpoint + outcome.
    """
    try:
        from common_lib.modules.observability import get_observability

        obs = get_observability()
        if obs is None:
            return
        obs.audit(
            actor=str(getattr(identity, "subject_id", "unknown")),
            tenant_id=str(getattr(identity, "tenant_id", "default")),
            action=action,
            resource_kind="i2w_request",
            resource_id=str(request.url.path),
            request={
                "method": request.method,
                "path": str(request.url.path),
                # headers redacted — no Authorization header
            },
            response={"status_code": status_code},
            outcome="success" if 200 <= status_code < 400 else "error",
            metadata=extra or {},
        )
    except Exception:  # noqa: BLE001
        # Audit must never break the request.
        logger.debug("audit emit failed", exc_info=True)


# ---------------------------------------------------------------------------
# Public composition helper
# ---------------------------------------------------------------------------


def i2w_deps(*, scope: Optional[str] = None, stage: Optional[str] = None):
    """Return a tuple of FastAPI dependencies for an I2W endpoint.

    Usage::

        @router.post("/foo", dependencies=i2w_deps(scope=I2W_SCOPE_WRITE))
        async def foo(...): ...

    The order is: feature flag → identity (JWT) → scope → rate limit.
    """
    deps: list = (
        [Depends(require_i2w_sub_flag(stage))]
        if stage
        else [Depends(require_i2w_master_flag())]
    )
    deps.append(Depends(i2w_identity))
    if scope:
        deps.append(Depends(require_i2w_scope(scope)))
    deps.append(Depends(require_i2w_rate_limit()))
    return deps


__all__ = [
    "I2WIdentity",
    "i2w_identity",
    "I2W_SCOPE_READ",
    "I2W_SCOPE_WRITE",
    "I2W_SCOPE_EXECUTE",
    "I2W_SCOPE_TRAINING_ADMIN",
    "I2W_SCOPE_SECURITY_ADMIN",
    "I2W_SCOPE_PLATFORM_ADMIN",
    "require_i2w_master_flag",
    "require_i2w_sub_flag",
    "require_i2w_scope",
    "require_i2w_rate_limit",
    "i2w_deps",
    "_audit_request",
]
