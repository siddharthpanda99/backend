"""app/core/flag_change_listener.py
═══════════════════════════════════════════════════════
The listener that makes a feature-flag toggle take effect on a **running** server.

Why a listener rather than a one-shot
═════════════════════════════════════════
``register_routers`` prunes and mounts once, inside the lifespan. A flag flipped at
runtime therefore changed the flag store and the node catalog (which filters at call
time) but *not* the HTTP route table, so the module kept 404ing while ``describe_pruning()``
reported it enabled. This module closes that loop: after a write, it re-evaluates the
registry and mounts what became enabled, live.

Which write path it hooks
═══════════════════════════
``FeatureFlagStore.set_enabled`` / ``set_module_enabled`` are the *only* writers of the
platform flag store (grep-confirmed: no other module calls them). There is no existing
``POST /flags/{name}`` for **platform** flags — the one in
``app/modules/decision_engine`` addresses a different namespace (decision-fabric flags,
with its own anti-brick master-flag rule) and is deliberately not reused or altered.

So this exposes the missing surface rather than inventing a second one. It is a plain
router under ``/api/v1/system/feature-flags``:

* ``GET  /api/v1/system/feature-flags``          — flag state + live mount report
* ``GET  /api/v1/system/feature-flags/mounts``   — what is actually mounted right now
* ``POST /api/v1/system/feature-flags/{flag}``   — write, then reconcile, honestly

Honesty contract on the POST
════════════════════════════
200 means the write happened *and* its route consequences were applied. A **disable**
cannot be applied live, so it returns **409** naming the prefixes still live and telling
the operator a restart is required. It never returns 200 for a disable it could not
perform, and it never blanks handlers or mutates ``app.routes`` to fake one — see
``app/core/router_hot_mount.py`` for why that is the worse failure.

It is a router registered through the same declarative registry as everything else, and it
declares no ``module``/``feature_flag``, so it is always mounted — including when
every other module is pruned. An admin cannot lock themselves out of the switch that
un-prunes the rest, which is the same anti-brick argument that keeps the decision-fabric
flag surface ungated.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from starlette.requests import Request
from pydantic import BaseModel, Field

from app.core.router_hot_mount import (
    mount_context,
    mounted_prefixes,
    reconcile_router_mounts,
)
from app.core.settings import get_settings

logger = logging.getLogger(__name__)

#: Path prefix of this router *relative* to whatever the registry mounts it under.
#: ``register_routers`` mounts it at ``/system``, so the real paths are
#: ``/api/v1/system/feature-flags...``.
PREFIX = "/feature-flags"

router = APIRouter(prefix=PREFIX)


class FlagWriteRequest(BaseModel):
    """Body for ``POST /api/v1/system/feature-flags/{flag_name}``."""

    enabled: bool = Field(..., description="Desired state for this flag")
    scope: str = Field(
        default="flag",
        description="'flag' writes the exact path; 'module' writes the path and every registered child",
    )
    persist: bool = Field(
        default=True,
        description="Also write to resources/memory_config.ini (survives restart)",
    )


class MountReportResponse(BaseModel):
    """What the reconcile pass actually did to the live route table."""

    mounted: List[str] = Field(default_factory=list)
    refused: List[Dict[str, Any]] = Field(default_factory=list)
    already_mounted: List[str] = Field(default_factory=list)
    restart_required: List[str] = Field(
        default_factory=list,
        description="Prefixes whose flag is OFF but whose routes are still live; a restart is required",
    )
    node_catalog_divergence: List[str] = Field(
        default_factory=list,
        description=(
            "Prefixes whose flag is OFF. Their @node tools are already filtered out "
            "(discover_nodes filters at call time) while their HTTP routes stay live "
            "until restart — the window in which a tool vanishes before its route does"
        ),
    )
    openapi_invalidated: bool = False


class FlagWriteResponse(BaseModel):
    """Result of a write + reconcile."""

    flag_name: str
    enabled: bool
    applied_live: bool
    restart_required: bool
    message: str
    mounts: MountReportResponse


def _resolve_app_context(request: Request) -> tuple[str, List[Any]]:
    """Return ``(api_prefix, global_deps)`` exactly as the app mounted its routers.

    Prefers the pair captured by ``register_routers`` and only falls back to the
    recorded one if absent. Reconstructing the auth dependency list here would risk
    mounting a live router with weaker auth than startup gave it.
    """
    app = request.app
    captured = mount_context(app)
    if captured is not None:
        return captured

    settings = get_settings()
    logger.warning(
        "flag_change_listener: no mount context recorded on the app — falling back to "
        "settings-derived api_prefix with EMPTY auth deps. Hot-mounted routers will "
        "have no global auth dependency."
    )
    return settings.API_V1_STR, []


@router.get("", response_model=Dict[str, Any], tags=["Feature Flags"])
@router.get(
    "/", response_model=Dict[str, Any], tags=["Feature Flags"], include_in_schema=False
)
async def get_feature_flags() -> Dict[str, Any]:
    """Current platform flag state plus the live mount report.

    Wraps ``common.describe_module_pruning`` and adds what that node cannot know:
    which prefixes are *actually* mounted on this process, and where the flag state and
    the route table currently disagree.
    """
    from common_lib.modules.common.module_pruning import describe_pruning

    return describe_pruning()


@router.get("/mounts", response_model=MountReportResponse, tags=["Feature Flags"])
async def get_mounts(request: Request) -> MountReportResponse:
    """What is actually mounted on this process right now.

    Read-only. Computes the divergence without changing anything, so an operator can
    see the pending-restart window before they toggle anything.
    """
    api_prefix, global_deps = _resolve_app_context(request)
    report = reconcile_router_mounts(request.app, api_prefix, global_deps, live=True)
    return MountReportResponse(
        mounted=[o["prefix"] for o in report["mounted"]],
        refused=[dict(o) for o in report["refused"]],
        already_mounted=[o["prefix"] for o in report["already_mounted"]],
        restart_required=report["restart_required"],
        node_catalog_divergence=report["node_catalog_divergence"],
        openapi_invalidated=report["openapi_invalidated"],
    )


@router.post("/{flag_name}", response_model=FlagWriteResponse, tags=["Feature Flags"])
async def set_feature_flag(
    flag_name: str, payload: FlagWriteRequest, request: Request
) -> FlagWriteResponse:
    """Write a platform feature flag, then make the route table agree with it.

    * **enable** → 200. The module's routers are mounted on the live app and the cached
      OpenAPI document is discarded so ``/docs`` shows them.
    * **disable** → 409. The flag is written (it will take effect at next restart) but the
      live routes cannot be removed, so the response says so explicitly instead of
      claiming a success it did not achieve.
    """
    from common_lib.modules.common.feature_flags import (
        FeatureFlagStore,
        get_registered_flags,
    )

    store = FeatureFlagStore()
    if flag_name not in get_registered_flags():
        raise HTTPException(
            status_code=404,
            detail=(
                f"Unknown feature flag {flag_name!r}. Only a registered flag can be "
                "written — an unregistered path is always treated as enabled, so "
                "writing one would report a change that does nothing."
            ),
        )

    if payload.scope == "module":
        store.set_module_enabled(flag_name, payload.enabled, persist=payload.persist)
    else:
        store.set_enabled(flag_name, payload.enabled, persist=payload.persist)

    api_prefix, global_deps = _resolve_app_context(request)
    report = reconcile_router_mounts(request.app, api_prefix, global_deps, live=True)

    response = MountReportResponse(
        mounted=[o["prefix"] for o in report["mounted"]],
        refused=[dict(o) for o in report["refused"]],
        already_mounted=[o["prefix"] for o in report["already_mounted"]],
        restart_required=report["restart_required"],
        node_catalog_divergence=report["node_catalog_divergence"],
        openapi_invalidated=report["openapi_invalidated"],
    )

    applied_live = bool(response.mounted)

    if not payload.enabled and response.restart_required:
        message = (
            f"Flag {flag_name!r} is now OFF and will stay off after restart, but "
            f"{len(response.restart_required)} route prefix(es) are still live on this "
            "process: " + ", ".join(response.restart_required) + ". FastAPI cannot "
            "un-include a router from a running app, so this toggle needs a restart. "
            "No handler was blanked and app.routes was not mutated — the routes are "
            "genuinely still serving."
        )
        raise HTTPException(
            status_code=409,
            detail={"message": message, "mounts": response.model_dump()},
        )

    if payload.enabled and response.refused:
        refused_names = ", ".join(str(r.get("prefix")) for r in response.refused)
        return FlagWriteResponse(
            flag_name=flag_name,
            enabled=True,
            applied_live=False,
            restart_required=False,
            message=(
                f"Flag {flag_name!r} is ON, but these routers were refused a live mount "
                f"({refused_names}) because they declare startup handlers. They will "
                "mount on the next restart."
            ),
            mounts=response,
        )

    if payload.enabled and not applied_live:
        return FlagWriteResponse(
            flag_name=flag_name,
            enabled=True,
            applied_live=False,
            restart_required=False,
            message=(
                f"Flag {flag_name!r} is ON. No prunable router maps to it, so there "
                "was nothing to mount."
            ),
            mounts=response,
        )

    return FlagWriteResponse(
        flag_name=flag_name,
        enabled=True,
        applied_live=True,
        restart_required=False,
        message=(
            f"Flag {flag_name!r} enabled live. Mounted: "
            + (", ".join(response.mounted) if response.mounted else "(nothing)")
            + ". OpenAPI cache invalidated."
            if response.openapi_invalidated
            else f"Flag {flag_name!r} enabled live."
        ),
        mounts=response,
    )


@router.get(
    "/{flag_name}/mounted", response_model=Dict[str, Any], tags=["Feature Flags"]
)
async def is_flag_mounted(flag_name: str, request: Request) -> Dict[str, Any]:
    """Is this flag's module currently mounted on this process?

    Exists so a caller (or a test) can assert the *route table* rather than trusting
    the flag store — the distinction that hid the original bug.
    """
    from app.core.routers import is_router_enabled, router_prune_candidates
    from app.core.router_hot_mount import registered_definitions

    api_prefix, _ = _resolve_app_context(request)
    mounted = mounted_prefixes(request.app)

    prefixes = [
        f"{api_prefix}{e.get('prefix', '')}"
        for e in registered_definitions(request.app)
        if flag_name in router_prune_candidates(e)
    ]

    return {
        "flag_name": flag_name,
        "flag_enabled": is_router_enabled({"feature_flag": flag_name}),
        "candidate_prefixes": prefixes,
        "currently_mounted": [p for p in prefixes if p in mounted],
    }


__all__ = ["PREFIX", "router"]
