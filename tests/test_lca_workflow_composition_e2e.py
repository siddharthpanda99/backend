"""
End-to-End Tests for Composable Life Cycle Assessment (LCA) Workflows & Subflows.

Validates that complex scientific/business models can be decomposed into:
1. Reusable YAML-based aspect subflows (with workflow.input and workflow.output contracts)
2. Granular domain-specific calculation and validation @node primitives
3. A Master Composed DAG that inlines subflows and executes end-to-end
   through WorkflowService and the ExecutionEngine.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

import pytest

# Ensure all LCA features are live for this workflow run
os.environ["LIFE_CYCLE_ASSESSMENT__ENABLED"] = "1"
os.environ["LIFE_CYCLE_ASSESSMENT__SCHEMA"] = "1"
os.environ["LIFE_CYCLE_ASSESSMENT__PERSISTENCE"] = "1"
os.environ["LIFE_CYCLE_ASSESSMENT__INVENTORY"] = "1"
os.environ["LIFE_CYCLE_ASSESSMENT__IMPACT_ASSESSMENT"] = "1"
os.environ["LIFE_CYCLE_ASSESSMENT__SENSITIVITY"] = "1"
os.environ["LIFE_CYCLE_ASSESSMENT__MONTE_CARLO"] = "1"

from common_lib.modules.data_storage.database.connection import init_db
from common_lib.modules.workflows.service import WorkflowService
from common_lib.modules.workflows.standard.registry.workflow_registry import (
    WorkflowRegistry,
)
from common_lib.modules.workflows.subflows.executor import (
    SubflowExecutor,
    inline_workflow_refs,
)


@pytest.fixture(scope="module", autouse=True)
def setup_environment():
    """Ensure database connection and schema tables exist."""
    init_db()


def test_lca_workflow_registry_discovery():
    """Verify all LCA aspect subflows and master workflow load into WorkflowRegistry."""
    registry = WorkflowRegistry()
    
    subflows = [
        "lca_parameter_scenario",
        "lca_quality_gate",
        "lca_uncertainty_sensitivity",
    ]
    for subflow_id in subflows:
        wf = registry.get_workflow(subflow_id)
        assert wf is not None, f"Subflow '{subflow_id}' was not discovered by WorkflowRegistry"
        assert wf.get("category") == "subflow"
        # Verify sentinel interface nodes exist
        node_types = [n.get("type") for n in wf.get("nodes", [])]
        assert "workflow.input" in node_types, f"Subflow '{subflow_id}' missing workflow.input"
        assert "workflow.output" in node_types, f"Subflow '{subflow_id}' missing workflow.output"

    master = registry.get_workflow("lca_e2e_pipeline")
    assert master is not None, "Master workflow 'lca_e2e_pipeline' was not discovered"
    assert master.get("category") == "LCA"


def test_lca_subflow_inlining_and_composition():
    """Verify SubflowExecutor inlines subflows and namespaces internal nodes."""
    registry = WorkflowRegistry()
    master = registry.get_workflow("lca_e2e_pipeline")
    assert master is not None

    inlined = inline_workflow_refs(master)
    inlined_nodes = inlined.get("nodes", [])
    inlined_node_ids = {n.get("id") for n in inlined_nodes}

    # Parent workflow_ref nodes should have been replaced
    assert "quality_gate" not in inlined_node_ids
    assert "param_scenario" not in inlined_node_ids

    # Subflow nodes should be present with proper prefix namespacing
    assert "sub_quality_gate_health_probe" in inlined_node_ids
    assert "sub_quality_gate_validate_model" in inlined_node_ids
    assert "sub_param_scenario_set_param" in inlined_node_ids
    assert "sub_param_scenario_resolve_params" in inlined_node_ids

    # Sentinel interface nodes must be eliminated
    for n in inlined_nodes:
        assert n.get("type") not in ("workflow.input", "workflow.output"), (
            f"Sentinel node {n.get('id')} was not dissolved during inlining"
        )

    # Core computation nodes must remain
    assert "calculate" in inlined_node_ids
    assert "analyze_contributions" in inlined_node_ids
    assert "explain" in inlined_node_ids


@pytest.mark.asyncio
async def test_lca_quality_gate_subflow_execution():
    """Execute the quality gate aspect workflow (health + four-level model validation)."""
    registry = WorkflowRegistry()
    wf = registry.get_workflow("lca_quality_gate")
    assert wf is not None

    # Filter out sentinel nodes when testing a subflow directly in isolation
    exec_nodes = [
        n for n in wf["nodes"]
        if n.get("type") not in ("workflow.input", "workflow.output")
    ]
    exec_edges = [
        e for e in wf.get("edges", [])
        if not e.get("from", "").startswith("wf_in_") and not e.get("to", "").startswith("wf_out_")
    ]

    svc = WorkflowService()
    stream = await svc.run_workflow_stream(
        nodes=exec_nodes,
        edges=exec_edges,
        inputs={"db_id": "test_db"},
        workflow_id="test_lca_quality_gate_direct",
        name="Direct LCA Quality Gate Run",
    )

    events: list[dict[str, Any]] = []
    async for event in stream:
        events.append(event)

    event_types = [e.get("event_type") for e in events]
    assert "workflow.started" in event_types
    assert "workflow.completed" in event_types
    assert "workflow.failed" not in event_types


@pytest.mark.asyncio
async def test_lca_e2e_pipeline_composed_execution():
    """
    Execute the master composed LCA pipeline end-to-end.
    Inlines subflows, runs the quality gate and scenario resolution,
    and streams lifecycle events across the unified execution graph.
    """
    registry = WorkflowRegistry()
    master = registry.get_workflow("lca_e2e_pipeline")
    assert master is not None

    svc = WorkflowService()

    # Pass valid input parameters
    inputs = {
        "db_id": "default_lca_db",
        "scenario_id": "test_scenario",
        "payload": {
            "name": "electricity_grid_co2_factor",
            "value": 0.45,
            "scope": "global",
        },
        "calculate_request": {
            "product_system_id": "ps_mock_system",
            "impact_method_id": "cml_baseline_2000",
            "allow_partial": True,
        },
        "product_system_id": "ps_mock_system",
        "result_id": "res_mock_001",
    }

    stream = await svc.run_workflow_stream(
        nodes=master["nodes"],
        edges=master.get("edges", []),
        inputs=inputs,
        workflow_id="test_lca_e2e_composed_run",
        name="LCA E2E Composed Pipeline Run",
    )

    events: list[dict[str, Any]] = []
    async for event in stream:
        events.append(event)

    event_types = [e.get("event_type") for e in events]
    assert "workflow.started" in event_types
    assert "workflow.completed" in event_types

    # Ensure inlined subflow nodes actually entered and ran
    states_entered = [e.get("state_id") for e in events if e.get("event_type") == "state.entered"]
    assert "sub_quality_gate_health_probe" in states_entered
    assert "sub_param_scenario_set_param" in states_entered
    assert "sub_param_scenario_resolve_params" in states_entered
