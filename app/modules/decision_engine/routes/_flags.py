"""Feature-flag guards for the Decision Fabric transport surface (G9 / rule 13).

Why this module exists
----------------------
The Decision Fabric is served by **two** routers — the §56/§57/DF-056 surface
in ``app.modules.decision.routes`` and the engine surface in
``app.modules.decision_engine.routes`` — and until now each of the five route
files that needed a guard carried its own byte-identical copy of
``_require_fabric()``. Five copies is five chances to forget the guard in the
next file, which is exactly the inconsistency this module removes: there is now
one implementation, imported by every guarded route on both routers.

The guard itself lives here, in the transport layer, not in ``common_lib``,
because it raises ``HTTPException`` (G1: ``common_lib`` has no knowledge of
HTTP). The *decision* about which routes need a guard lives in
``common_lib.modules.decision_engine.flags`` (:data:`ALWAYS_AVAILABLE`), which
is where the policy belongs.

Contracts this preserves
------------------------
* **Fail-closed.** ``is_decision_flag_enabled`` resolves OFF when the flag
  registry is unreachable, so an outage of the registry disables the fabric
  rather than exposing it. Same semantics as before this refactor.
* **503 + unchanged ``detail`` text.** The status code and the message string
  are exactly what the previous per-file copies produced. Both the frontend
  client (``services/decisionApi.ts`` turns any 503 into a ``FeatureFlagError``)
  and the backend test suite key off them, so changing either would be a
  client-visible break (G4).
* **Call it first.** Every guard call sits before the handler imports or calls
  a service, so a disabled fabric costs a flag lookup and nothing else. Keep it
  that way when adding routes — a guard placed after the work is not a gate.
"""

from __future__ import annotations

from fastapi import HTTPException

from common_lib.modules.decision_engine.flags import (
    DECISION_COORDINATION_ENABLED,
    NEXUS_DECISION_FABRIC_ENABLED,
    is_decision_flag_enabled,
)

__all__ = [
    "COORDINATION_FLAG",
    "require_coordination",
    "require_fabric",
]

#: Re-exported under its historical name so the ``app.modules.decision``
#: route module keeps working unchanged. The value is the same string the
#: flag registry knows.
COORDINATION_FLAG = DECISION_COORDINATION_ENABLED


def require_fabric(tenant_id: str | None = None) -> None:
    """Fail-closed master guard: 503 until NEXUS_DECISION_FABRIC_ENABLED is on.

    Args:
        tenant_id: Optional tenant for per-tenant flag resolution. Omitted by
            every current caller, which means the global override decides.

    Raises:
        HTTPException: 503 when the master flag resolves OFF. Never raised
            when it resolves ON.
    """
    if not is_decision_flag_enabled(NEXUS_DECISION_FABRIC_ENABLED, tenant_id):
        raise HTTPException(
            status_code=503,
            detail="Decision Fabric is disabled (NEXUS_DECISION_FABRIC_ENABLED=off)",
        )


def require_coordination(tenant_id: str | None = None) -> None:
    """Coordination guard: the master flag **and** the coordination flag.

    Coordination is a strictly larger surface than the fabric (it can fan work
    out to other agents), so it gets its own default-OFF switch on top of the
    master. It is layered rather than independent: turning the fabric off must
    also turn coordination off, whatever the coordination flag says.

    Raises:
        HTTPException: 503 from either guard, master first.
    """
    require_fabric(tenant_id)
    if not is_decision_flag_enabled(COORDINATION_FLAG, tenant_id):
        raise HTTPException(
            status_code=503,
            detail="Decision coordination is disabled (NEXUS_FF_DECISION_COORDINATION_ENABLED=off)",
        )
