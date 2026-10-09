"""
End-to-End Tests for Multi-Pillar Composable Workflows & Agentic Subflows.

Validates that complex business, security, and context operations across:
1. Multi-Objective Decision Optimization (filter_and_score, pareto_frontier, recommend_pareto_choice)
2. Zero-Trust Execution & Governance (ztel_verify, acc_apply_constraint, agent_evaluate_risk_rationale)
3. Global Context Infrastructure (merge_context, agentic_conflict_detect, agentic_synthesize_brief)

Can be composed into reusable YAML-based subflows and master pipelines that execute
end-to-end through WorkflowService and the ExecutionEngine with hybrid deterministic
and agentic instruction node execution.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

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


def test_multi_pillar_workflow_registry_discovery():
    """Verify all subflows and master pipelines across the 3 pillars load into WorkflowRegistry."""
    registry = WorkflowRegistry()

    expected_subflows = [
        "filter_and_score",
        "pareto_frontier",
        "ztel_verify",
        "acc_authorize",
        "gci_merge_context",
        "gci_conflict_detect",
    ]
    for subflow_id in expected_subflows:
        wf = registry.get_workflow(subflow_id)
        assert wf is not None, f"Subflow '{subflow_id}' was not discovered by WorkflowRegistry"
        assert wf.get("category") == "subflow"

        node_types = [n.get("type") for n in wf.get("nodes", [])]
        assert "workflow.input" in node_types, f"Subflow '{subflow_id}' missing workflow.input"
        assert "workflow.output" in node_types, f"Subflow '{subflow_id}' missing workflow.output"

    expected_masters = [
        ("decision_multi_objective_pipeline", "decision"),
        ("governance_zero_trust_pipeline", "governance"),
        ("gci_knowledge_context_pipeline", "context"),
    ]
    for master_id, expected_category in expected_masters:
        master = registry.get_workflow(master_id)
        assert master is not None, f"Master workflow '{master_id}' was not discovered"
        assert master.get("category") == expected_category
        assert len(master.get("nodes", [])) >= 3
        assert len(master.get("edges", [])) >= 2


def test_multi_pillar_subflow_inlining():
    """Verify SubflowExecutor flattens all 3 master pipelines with proper namespacing and property forwarding."""
    registry = WorkflowRegistry()

    pipeline_configs = [
        (
            "decision_multi_objective_pipeline",
            ["stage_filter_score", "stage_pareto_frontier"],
            [
                "sub_stage_filter_score_filter_score_node",
                "sub_stage_pareto_frontier_pareto_solve",
                "stage_agent_recommendation",
            ],
            ["decision_engine.filter_and_score", "decision_engine.pareto_frontier", "decision_engine.recommend_pareto_choice"],
        ),
        (
            "governance_zero_trust_pipeline",
            ["stage_ztel_verification", "stage_acc_authorization"],
            [
                "sub_stage_ztel_verification_ztel_check",
                "sub_stage_acc_authorization_acc_check",
                "stage_agent_audit_rationale",
            ],
            ["governance.ztel_verify", "governance.acc_apply_constraint", "governance.agent_evaluate_risk_rationale"],
        ),
        (
            "gci_knowledge_context_pipeline",
            ["stage_gci_merge", "stage_gci_conflict"],
            [
                "sub_stage_gci_merge_merge_node",
                "sub_stage_gci_conflict_conflict_node",
                "stage_agent_briefing",
            ],
            ["knowledge_engine.merge_context", "knowledge_engine.agentic_conflict_detect", "knowledge_engine.agentic_synthesize_brief"],
        ),
    ]

    for master_id, replaced_refs, expected_nodes, expected_types in pipeline_configs:
        master = registry.get_workflow(master_id)
        assert master is not None

        inlined = inline_workflow_refs(master)
        inlined_nodes = inlined.get("nodes", [])
        inlined_node_ids = {n.get("id") for n in inlined_nodes}
        inlined_types = {n.get("type") for n in inlined_nodes}

        # Parent workflow_ref nodes should have been replaced
        for ref_id in replaced_refs:
            assert ref_id not in inlined_node_ids, f"Ref node '{ref_id}' was not replaced in '{master_id}'"

        # Namespaced subflow nodes must be present
        for exp_id in expected_nodes:
            assert exp_id in inlined_node_ids, f"Expected node '{exp_id}' missing in inlined '{master_id}'"

        # Sentinel interface nodes must be eliminated
        for n in inlined_nodes:
            assert n.get("type") not in ("workflow.input", "workflow.output"), (
                f"Sentinel node {n.get('id')} was not dissolved during inlining"
            )

        # Expected node types must match
        for exp_type in expected_types:
            assert exp_type in inlined_types, f"Expected node type '{exp_type}' missing in '{master_id}'"


@pytest.mark.asyncio
async def test_decision_optimization_composed_pipeline_e2e():
    """
    Execute the Multi-Objective Decision Optimization Master Pipeline end-to-end.
    Combines:
    - Stage 1: filter_and_score subflow (deterministic constraint gating & normalization)
    - Stage 2: pareto_frontier subflow (deterministic non-dominance solver)
    - Stage 3: recommend_pareto_choice agentic instruction node (autonomous AI strategic advisor)
    """
    registry = WorkflowRegistry()
    master = registry.get_workflow("decision_multi_objective_pipeline")
    assert master is not None

    svc = WorkflowService()

    raw_candidates = [
        {"id": "model_ultra_fast", "latency_ms": 35, "cost_per_1k": 0.015, "accuracy": 0.92},
        {"id": "model_balanced", "latency_ms": 75, "cost_per_1k": 0.025, "accuracy": 0.96},
        {"id": "model_accuracy_king", "latency_ms": 110, "cost_per_1k": 0.040, "accuracy": 0.99},
        {"id": "model_too_slow", "latency_ms": 280, "cost_per_1k": 0.010, "accuracy": 0.95},  # filtered by latency <= 150
        {"id": "model_too_expensive", "latency_ms": 50, "cost_per_1k": 0.080, "accuracy": 0.97},  # filtered by cost <= 0.05
    ]

    inputs = {
        "raw_options": raw_candidates,
        "constraints": {"latency_ms": "<= 150", "cost_per_1k": "<= 0.05"},
        "weights": {"latency_ms": 0.35, "cost_per_1k": 0.35, "accuracy": 0.30},
        "dimensions": ["latency_ms", "cost_per_1k", "accuracy"],
        "directions": {
            "latency_ms": "lower_is_better",
            "cost_per_1k": "lower_is_better",
            "accuracy": "higher_is_better",
        },
        "business_objective": "High-throughput production serving under strict SLA and cost budget",
    }

    stream = await svc.run_workflow_stream(
        nodes=master["nodes"],
        edges=master.get("edges", []),
        inputs=inputs,
        workflow_id="test_decision_composed_e2e_run",
        name="Decision Composed Master Pipeline Run",
    )

    events: list[dict[str, Any]] = []
    async for event in stream:
        events.append(event)

    event_types = [e.get("event_type") for e in events]
    assert "workflow.started" in event_types, "workflow.started event missing"
    assert "workflow.completed" in event_types, "workflow.completed event missing"
    assert "workflow.failed" not in event_types, f"Workflow failed with events: {events}"

    # Verify each pipeline stage was entered and completed
    states_entered = [e.get("state_id") for e in events if e.get("event_type") == "state.entered"]
    assert "sub_stage_filter_score_filter_score_node" in states_entered
    assert "sub_stage_pareto_frontier_pareto_solve" in states_entered
    assert "stage_agent_recommendation" in states_entered

    tool_completions = [e for e in events if e.get("event_type") == "tool.execution.completed"]
    assert len(tool_completions) >= 3, f"Expected at least 3 completed tool executions, got {len(tool_completions)}"


@pytest.mark.asyncio
async def test_zero_trust_governance_composed_pipeline_e2e():
    """
    Execute the Zero-Trust Governance & Action Capability Master Pipeline end-to-end.
    Combines:
    - Stage 1: ztel_verify subflow (zero-trust identity, tenant match, trust score)
    - Stage 2: acc_authorize subflow (capability risk bounds and policy checks)
    - Stage 3: agent_evaluate_risk_rationale agentic instruction node (tamper-evident audit rationale)
    """
    registry = WorkflowRegistry()
    master = registry.get_workflow("governance_zero_trust_pipeline")
    assert master is not None

    svc = WorkflowService()

    inputs = {
        "subject": {
            "agent_id": "audited_worker_agent_01",
            "tenant_id": "tenant_enterprise_prod",
            "base_trust_score": 0.95,
            "attributes": {"region": "us-east-1", "environment": "production"},
        },
        "action_details": {
            "name": "storage.create_encrypted_snapshot",
            "risk_level": "medium",
            "mutating": True,
        },
        "resource": {
            "resource_id": "res_secure_vault_101",
            "tenant_id": "tenant_enterprise_prod",
            "sensitivity": "confidential",
        },
        "max_risk_tolerance": "high",
        "compliance_framework": "SOC2",
        "environment": "production",
    }

    stream = await svc.run_workflow_stream(
        nodes=master["nodes"],
        edges=master.get("edges", []),
        inputs=inputs,
        workflow_id="test_governance_composed_e2e_run",
        name="Zero-Trust Governance Pipeline Run",
    )

    events: list[dict[str, Any]] = []
    async for event in stream:
        events.append(event)

    event_types = [e.get("event_type") for e in events]
    assert "workflow.started" in event_types, "workflow.started event missing"
    assert "workflow.completed" in event_types, "workflow.completed event missing"
    assert "workflow.failed" not in event_types, f"Workflow failed with events: {events}"

    states_entered = [e.get("state_id") for e in events if e.get("event_type") == "state.entered"]
    assert "sub_stage_ztel_verification_ztel_check" in states_entered
    assert "sub_stage_acc_authorization_acc_check" in states_entered
    assert "stage_agent_audit_rationale" in states_entered

    tool_completions = [e for e in events if e.get("event_type") == "tool.execution.completed"]
    assert len(tool_completions) >= 3


@pytest.mark.asyncio
async def test_gci_knowledge_context_composed_pipeline_e2e():
    """
    Execute the Global Context Infrastructure & Cognitive Conflict Master Pipeline end-to-end.
    Combines:
    - Stage 1: gci_merge_context subflow (source precedence ordering, deduplication, token budgeting)
    - Stage 2: gci_conflict_detect subflow (agentic contradiction detection across assertions)
    - Stage 3: agentic_synthesize_brief instruction node (executive briefing & factual coherence synthesis)
    """
    registry = WorkflowRegistry()
    master = registry.get_workflow("gci_knowledge_context_pipeline")
    assert master is not None

    svc = WorkflowService()

    envelopes = [
        {
            "source": "system",
            "content": "Kubernetes cluster production-01 status: HEALTHY. Node count: 16. API gateway response latency: 12ms.",
        },
        {
            "source": "environment",
            "content": "Ambient region: us-east-1. Availability zones: [us-east-1a, us-east-1b, us-east-1c]. Thermal throttle: NONE.",
        },
        {
            "source": "knowledge_engine",
            "content": "Architecture baseline: DB primary replica count target is 3. Target availability SLA: 99.99%.",
        },
        {
            "source": "memory",
            "content": "Historical memory log: Cluster automated scale-up was triggered 4 hours ago. Worker node count reached 16.",
        },
    ]

    claims = [
        {
            "subject": "cluster_node_count",
            "statement": "Real-time telemetry reports 16 active worker nodes.",
            "value": 16,
            "source": "system",
        },
        {
            "subject": "cluster_node_count",
            "statement": "Stale cache memory reports 14 active nodes.",
            "value": 14,
            "source": "memory",
        },
        {
            "subject": "sla_target",
            "statement": "Contractual SLA target is 99.99%.",
            "value": 99.99,
            "source": "knowledge_engine",
        },
    ]

    inputs = {
        "envelopes": envelopes,
        "precedence": ["system", "environment", "knowledge_engine", "memory"],
        "token_budget": 3000,
        "claims": claims,
        "mission_objective": "Production Infrastructure Coherence & Integrity Verification",
    }

    stream = await svc.run_workflow_stream(
        nodes=master["nodes"],
        edges=master.get("edges", []),
        inputs=inputs,
        workflow_id="test_gci_composed_e2e_run",
        name="GCI Knowledge Context Pipeline Run",
    )

    events: list[dict[str, Any]] = []
    async for event in stream:
        events.append(event)

    event_types = [e.get("event_type") for e in events]
    assert "workflow.started" in event_types, "workflow.started event missing"
    assert "workflow.completed" in event_types, "workflow.completed event missing"
    assert "workflow.failed" not in event_types, f"Workflow failed with events: {events}"

    states_entered = [e.get("state_id") for e in events if e.get("event_type") == "state.entered"]
    assert "sub_stage_gci_merge_merge_node" in states_entered
    assert "sub_stage_gci_conflict_conflict_node" in states_entered
    assert "stage_agent_briefing" in states_entered

    tool_completions = [e for e in events if e.get("event_type") == "tool.execution.completed"]
    assert len(tool_completions) >= 3
