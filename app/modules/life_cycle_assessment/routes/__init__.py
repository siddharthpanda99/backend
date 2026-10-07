"""Life Cycle Assessment API routes — thin transport layer.

Rule 16: route handlers parse input, call ONE service method, shape output.
No business logic, no direct DB queries.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.modules.life_cycle_assessment.routes._flags import (
    require_lca as _require_lca,
    require_inventory as _require_inventory,
    require_impact as _require_impact,
    require_monte_carlo as _require_monte_carlo,
    require_sensitivity as _require_sensitivity,
    require_persistence as _require_persistence,
    require_schema as _require_schema,
    require_lcc as _require_lcc,
    require_slca as _require_slca,
    require_import as _require_import,
    require_export as _require_export,
    flag_state,
)
from app.modules.life_cycle_assessment.routes._errors import http_error

router = APIRouter(prefix="/life-cycle-assessment", tags=["Life Cycle Assessment"])

# Singleton service — stateless because it opens its own session per call.
from common_lib.modules.life_cycle_assessment import service as service_mod
_lca_service = service_mod.LCAService()


@router.get("/health", summary="Module health and flag state")
def health():
    """Ungated: an operator must be able to ask 'is LCA on?' when it's off."""
    return _lca_service.health()


@router.get("/flags", summary="All LCA feature flags")
def flags():
    """Ungated flag introspection."""
    return flag_state()


# ══════════════════════════════════════════════════════════════════
# Vocabulary
# ══════════════════════════════════════════════════════════════════

@router.get("/vocabulary", summary="Live vocabularies from the database")
def list_vocabulary():
    return _lca_service.list_vocabulary()


@router.post("/vocabulary/{vocabulary}/{value}", summary="Extend a vocabulary")
def extend_vocabulary(
    vocabulary: str,
    value: str,
    label: str = "",
    description: str = "",
    db_id: str | None = None,
):
    _require_persistence()
    try:
        return _lca_service.extend_vocabulary(
            vocabulary, value, label=label, description=description, db_id=db_id
        )
    except Exception as exc:
        raise http_error(exc)


# ══════════════════════════════════════════════════════════════════
# Model: flows / processes / exchanges / product systems
# ══════════════════════════════════════════════════════════════════

@router.post("/flows", summary="Create a flow")
def create_flow(payload: dict[str, Any]):
    _require_persistence()
    try:
        return _lca_service.create_flow(payload)
    except Exception as exc:
        raise http_error(exc)


@router.get("/flows", summary="Search flows")
def search_flows(q: str = "", flow_type: str | None = None, db_id: str | None = None, limit: int = 50):
    try:
        return _lca_service.search_flows(q, flow_type, db_id, limit)
    except Exception as exc:
        raise http_error(exc)


@router.post("/processes", summary="Create a process with its exchanges")
def create_process(payload: dict[str, Any]):
    _require_persistence()
    try:
        return _lca_service.create_process(payload)
    except Exception as exc:
        raise http_error(exc)


@router.post("/exchanges", summary="Create an exchange")
def create_exchange(payload: dict[str, Any]):
    _require_persistence()
    try:
        return _lca_service.create_exchange(payload)
    except Exception as exc:
        raise http_error(exc)


@router.post("/product-systems", summary="Create a product system")
def create_product_system(payload: dict[str, Any]):
    _require_persistence()
    try:
        return _lca_service.create_product_system(payload)
    except Exception as exc:
        raise http_error(exc)


@router.get("/product-systems/{system_id}/links/suggest", summary="Propose links")
def suggest_links(system_id: str):
    try:
        return {"suggestions": _lca_service.suggest_links(system_id)}
    except Exception as exc:
        raise http_error(exc)


@router.post("/product-systems/{system_id}/links", summary="Persist links")
def apply_links(system_id: str, links: list[dict[str, Any]]):
    _require_persistence()
    try:
        return _lca_service.apply_links(system_id, links)
    except Exception as exc:
        raise http_error(exc)


# ══════════════════════════════════════════════════════════════════
# Parameters + scenarios
# ══════════════════════════════════════════════════════════════════

@router.post("/parameters", summary="Create or update a parameter")
def set_parameter(payload: dict[str, Any]):
    _require_persistence()
    try:
        return _lca_service.set_parameter(payload)
    except Exception as exc:
        raise http_error(exc)


@router.get("/parameters", summary="Resolve parameters under a scenario")
def resolve_parameters(scenario_id: str | None = None, process_id: str | None = None):
    try:
        return {"values": _lca_service.resolve_parameters(scenario_id, process_id=process_id)}
    except Exception as exc:
        raise http_error(exc)


@router.post("/scenarios", summary="Create a scenario with overrides")
def create_scenario(payload: dict[str, Any]):
    _require_persistence()
    try:
        return _lca_service.create_scenario(payload)
    except Exception as exc:
        raise http_error(exc)


# ══════════════════════════════════════════════════════════════════
# Calculation
# ══════════════════════════════════════════════════════════════════

@router.post("/calculate", summary="Run LCI/LCIA for a product system")
def calculate(request: dict[str, Any]):
    _require_inventory()
    try:
        return _lca_service.calculate(request)
    except Exception as exc:
        raise http_error(exc)


@router.post("/monte-carlo", summary="Monte Carlo uncertainty analysis")
def monte_carlo(
    product_system_id: str,
    impact_method_id: str | None = None,
    scenario_id: str | None = None,
    n_iterations: int = 1000,
    seed: int = 42,
    location_id: str | None = None,
):
    _require_monte_carlo()
    try:
        return _lca_service.run_monte_carlo(
            product_system_id,
            n_iterations=n_iterations,
            seed=seed,
            impact_method_id=impact_method_id,
            scenario_id=scenario_id,
            location_id=location_id,
        )
    except Exception as exc:
        raise http_error(exc)


@router.post("/sensitivity", summary="Parameter sensitivity analysis")
def sensitivity(
    product_system_id: str,
    method: str = "one_at_a_time",
    parameter_names: list[str] | None = None,
    impact_method_id: str | None = None,
    scenario_id: str | None = None,
    n_samples: int = 200,
    n_points: int = 20,
    seed: int = 42,
):
    _require_sensitivity()
    try:
        return _lca_service.run_sensitivity(
            product_system_id,
            method=method,
            parameter_names=parameter_names,
            n_samples=n_samples,
            n_points=n_points,
            seed=seed,
            impact_method_id=impact_method_id,
            scenario_id=scenario_id,
        )
    except Exception as exc:
        raise http_error(exc)


# ══════════════════════════════════════════════════════════════════
# Analysis
# ══════════════════════════════════════════════════════════════════

@router.post("/contribution", summary="Rank contributors")
def contribution(
    product_system_id: str,
    dimension: str = "process",
    top_n: int = 20,
    min_share: float = 0.0,
    scenario_id: str | None = None,
):
    _require_inventory()
    try:
        return _lca_service.analyze_contributions(
            product_system_id,
            dimension=dimension,
            top_n=top_n,
            min_share=min_share,
            scenario_id=scenario_id,
        )
    except Exception as exc:
        raise http_error(exc)


@router.post("/sankey", summary="Generate Sankey diagram")
def sankey(
    product_system_id: str,
    node_type: str = "process",
    top_n: int = 25,
    min_share: float = 0.005,
    scenario_id: str | None = None,
):
    _require_inventory()
    try:
        return _lca_service.generate_sankey(
            product_system_id,
            node_type=node_type,
            top_n=top_n,
            min_share=min_share,
            scenario_id=scenario_id,
        )
    except Exception as exc:
        raise http_error(exc)


# ══════════════════════════════════════════════════════════════════
# Quality
# ══════════════════════════════════════════════════════════════════

@router.post("/validate", summary="Validate model (four levels)")
def validate(
    db_id: str | None = None,
    product_system_id: str | None = None,
    levels: list[str] | None = None,
):
    _require_persistence()
    try:
        return _lca_service.validate_model(
            db_id=db_id, product_system_id=product_system_id, levels=levels
        )
    except Exception as exc:
        raise http_error(exc)


@router.get("/reproduce/{calculation_id}", summary="Check reproducibility of a stored calculation")
def reproduce(calculation_id: str):
    _require_persistence()
    try:
        return _lca_service.reproduce_calculation(calculation_id)
    except Exception as exc:
        raise http_error(exc)


@router.get("/explain/{result_id}", summary="Explain a stored result from its provenance")
def explain(result_id: str):
    _require_persistence()
    try:
        return _lca_service.explain_result(result_id)
    except Exception as exc:
        raise http_error(exc)


# ══════════════════════════════════════════════════════════════════
# Extensions
# ══════════════════════════════════════════════════════════════════

@router.post("/cost", summary="Aggregate life cycle costs")
def aggregate_costs(
    costs: list[dict[str, Any]],
    currency_id: str | None = None,
    discount_rate: float | None = None,
    discount_years: float | None = None,
    process_scaling: dict[str, float] | None = None,
    allow_mixed_currency: bool = False,
):
    _require_lcc()
    try:
        return _lca_service.aggregate_costs(
            costs,
            currency_id=currency_id,
            discount_rate=discount_rate,
            discount_years=discount_years,
            process_scaling=process_scaling,
            allow_mixed_currency=allow_mixed_currency,
        )
    except Exception as exc:
        raise http_error(exc)


@router.post("/social", summary="Aggregate social indicators")
def aggregate_social(indicators: list[dict[str, Any]], process_scaling: dict[str, float] | None = None):
    _require_slca()
    try:
        return _lca_service.aggregate_social(indicators, process_scaling=process_scaling)
    except Exception as exc:
        raise http_error(exc)


@router.post("/epd", summary="Decompose impact result into EPD modules")
def build_epd_report(
    result: dict[str, Any],
    module_map: dict[str, list[str]] | None = None,
    biogenic_flow_ids: list[str] | None = None,
    epd: dict[str, Any] | None = None,
):
    _require_persistence()
    try:
        return _lca_service.build_epd_report(result, module_map, biogenic_flow_ids, epd)
    except Exception as exc:
        raise http_error(exc)


# ══════════════════════════════════════════════════════════════════
# Interchange
# ══════════════════════════════════════════════════════════════════

@router.post("/import", summary="Parse external dataset into canonical model")
def import_dataset(format: str, payload: str, dry_run: bool = True):
    _require_import()
    try:
        return _lca_service.import_dataset(format, payload, dry_run)
    except Exception as exc:
        raise http_error(exc)


@router.post("/export", summary="Serialize canonical document to interchange format")
def export_dataset(format: str, document: dict[str, Any] | None = None):
    _require_export()
    try:
        return _lca_service.export_dataset(format, document)
    except Exception as exc:
        raise http_error(exc)


@router.post("/mappings/suggest", summary="Suggest mappings for an external flow")
def suggest_mappings(
    source_name: str,
    source_unit: str | None = None,
    cas_number: str | None = None,
    chemical_formula: str | None = None,
    synonyms: list[str] | None = None,
    target_type: str = "flow",
):
    _require_persistence()
    try:
        return _lca_service.suggest_mappings(
            source_name, source_unit, cas_number, chemical_formula, synonyms, target_type
        )
    except Exception as exc:
        raise http_error(exc)


# ══════════════════════════════════════════════════════════════════
# Schema management
# ══════════════════════════════════════════════════════════════════

@router.post("/schema", summary="Create this module's tables")
def ensure_schema(force: bool = False):
    _require_schema()
    try:
        created = _lca_service.ensure_schema(force=force)
        return {"created": created}
    except Exception as exc:
        raise http_error(exc)