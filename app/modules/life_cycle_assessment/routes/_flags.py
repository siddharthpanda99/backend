"""Feature-flag guards for the LCA transport surface (G9 / rule 13).

* **Fail-closed.** The underlying flag resolver returns ``False`` when the flag
  machinery is unreachable, so an outage of the registry disables the surface
  rather than exposing it.
* **503 + stable detail text.** Changing either would be a client-visible break
  (G4).
* **Call it first.** Every guard call sits before the handler imports or calls a
  service — a guard placed after the work is not a gate.
"""

from __future__ import annotations

from fastapi import HTTPException

from common_lib.modules.life_cycle_assessment import flags
from common_lib.modules.life_cycle_assessment.errors import LCAFeatureDisabled


MASTER_FLAG = flags.FLAG_ENABLED


def _require(condition: bool, flag: str) -> None:
    if not condition:
        raise HTTPException(
            status_code=503,
            detail=(
                f"Life Cycle Assessment capability '{flag}' is disabled "
                f"(set {flag}=true to enable)"
            ),
        )


def require_lca(tenant_id: str | None = None) -> None:
    """Master gate — the entire LCA surface."""
    _require(flags.enabled(), flags.FLAG_ENABLED)


def require_inventory(tenant_id: str | None = None) -> None:
    """LCI / calculation gate."""
    require_lca()
    _require(flags.inventory_enabled(), flags.FLAG_INVENTORY)


def require_impact(tenant_id: str | None = None) -> None:
    """LCIA gate."""
    require_lca()
    _require(flags.impact_enabled(), flags.FLAG_IMPACT)


def require_monte_carlo(tenant_id: str | None = None) -> None:
    _require(flags.monte_carlo_enabled(), flags.FLAG_MONTECARLO)


def require_sensitivity(tenant_id: str | None = None) -> None:
    _require(flags.sensitivity_enabled(), flags.FLAG_SENSITIVITY)


def require_persistence(tenant_id: str | None = None) -> None:
    _require(flags.persistence_enabled(), flags.FLAG_PERSISTENCE)


def require_schema(tenant_id: str | None = None) -> None:
    _require(flags.schema_enabled(), flags.FLAG_SCHEMA)


def require_lcc(tenant_id: str | None = None) -> None:
    _require(flags.lcc_enabled(), flags.FLAG_LCC)


def require_slca(tenant_id: str | None = None) -> None:
    _require(flags.slca_enabled(), flags.FLAG_SLCA)


def require_import(tenant_id: str | None = None) -> None:
    _require(flags.import_enabled(), flags.FLAG_IMPORT)


def require_export(tenant_id: str | None = None) -> None:
    _require(flags.export_enabled(), flags.FLAG_EXPORT)


# ──────────────────────────────────────────────────────────────────
# Flag introspection endpoint — deliberately UNGATED
# ──────────────────────────────────────────────────────────────────

def flag_state() -> dict[str, bool]:
    """All LCA flags and their resolved state.

    **Not gated.** An operator asking "what flags are on?" must get an answer
    even when every flag is off. Gating the discovery surface would make the
    question unanswerable.
    """
    return {name: flags.flag_enabled(name) for name in flags.FLAGS}