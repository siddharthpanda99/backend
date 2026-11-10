"""
End-to-End Tests for Numbered System Workflows & Common Subflows.

Systematically verifies that:
1. All domain subflows (Decision, Knowledge/GCI, Governance/ZTEL/ACC, Execution/ECL/CLO)
   execute with real live @nodes and zero tool failures.
2. Composed Numbered System Workflows (07-ztel, 23-acc, 05-eval, 10-mote, 85-wrm)
   resolve their subflows, execute through the DAG, and complete end-to-end.
"""

from __future__ import annotations

import ctypes
import gc
from typing import Any

import pytest

from common_lib.modules.data_storage.database.connection import init_db
from common_lib.modules.workflows.service import WorkflowService
from common_lib.modules.workflows.standard.registry.workflow_registry import (
    WorkflowRegistry,
)


@pytest.fixture(scope="module", autouse=True)
def setup_environment():
    """Ensure database connection and schema tables exist."""
    init_db()


@pytest.fixture(autouse=True)
def cleanup_memory_after_each_test():
    """Run garbage collection and malloc_trim before and after each test case to prevent memory build-up."""
    gc.collect()
    try:
        ctypes.CDLL("libc.so.6").malloc_trim(0)
    except Exception:
        pass
    yield
    gc.collect()
    try:
        ctypes.CDLL("libc.so.6").malloc_trim(0)
    except Exception:
        pass


async def _assert_workflow_stream(
    svc: WorkflowService,
    wf: dict[str, Any],
    inputs: dict[str, Any],
    run_id: str,
    name: str,
) -> None:
    """Helper to stream workflow execution and assert completion with zero tool failures."""
    stream = await svc.run_workflow_stream(
        nodes=wf["nodes"],
        edges=wf.get("edges", []),
        inputs=inputs,
        workflow_id=run_id,
        name=name,
    )

    tool_failures: list[dict[str, Any]] = []
    completed = False
    failed = False

    async for event in stream:
        etype = event.get("event_type")
        if etype == "tool.execution.failed":
            tool_failures.append({
                "tool_id": event.get("tool_id"),
                "error": event.get("error"),
            })
        elif etype == "workflow.completed":
            completed = True
        elif etype == "workflow.failed":
            failed = True

    assert not failed, f"Workflow '{run_id}' failed: {tool_failures}"
    assert len(tool_failures) == 0, f"Workflow '{run_id}' had tool failures: {tool_failures}"
    assert completed, f"Workflow '{run_id}' did not emit workflow.completed"


# ─────────────────────────────────────────────────────────────────────────────
# 1. Decision & Optimization Subflows (Parameterized)
# ─────────────────────────────────────────────────────────────────────────────


DECISION_SUBFLOWS = [
    "filter_by_constraints",
    "evaluate_weighted_score",
    "pareto_frontier",
    "record_decision_provenance",
    "filter_and_score",
    "unmeasured_dimensions",
    "schedule_custom",
    "schedule_fastest",
    "scoring_fingerprint",
    "overrides_applied",
]


@pytest.mark.asyncio
@pytest.mark.parametrize("subflow_id", DECISION_SUBFLOWS)
async def test_subflow_decision(subflow_id: str):
    """Test individual Decision & Optimization subflows."""
    registry = WorkflowRegistry()
    svc = WorkflowService()

    base_inputs = {
        "options": [
            {"id": "opt_1", "latency": 50, "accuracy": 0.95, "cost": 0.05},
            {"id": "opt_2", "latency": 100, "accuracy": 0.99, "cost": 0.10},
        ],
        "candidates": [
            {"id": "opt_1", "latency": 50, "accuracy": 0.95, "cost": 0.05},
            {"id": "opt_2", "latency": 100, "accuracy": 0.99, "cost": 0.10},
        ],
        "constraints": [
            {"dimension": "latency", "operator": "lte", "threshold": 120, "kind": "hard"}
        ],
        "constraint_mode": "all",
        "weights": {"latency": 0.4, "accuracy": 0.4, "cost": 0.2},
        "directions": {
            "latency": "lower_is_better",
            "accuracy": "higher_is_better",
            "cost": "lower_is_better",
        },
        "dimensions": ["latency", "accuracy", "cost"],
        "threshold": 0.0,
        "top_k": 5,
        "strict": True,
        "decision_id": "dec_opt_test",
        "decision_type": "optimization",
        "inputs": {"test": True},
        "outputs": {"winner": "opt_1"},
        "rationale": "optimal cost-latency tradeoff",
        "weights_used": {"latency": 0.4, "accuracy": 0.4, "cost": 0.2},
        "directions_used": {
            "latency": "lower_is_better",
            "accuracy": "higher_is_better",
            "cost": "lower_is_better",
        },
        "scores": {"latency": 0.9, "accuracy": 0.95},
        "required_dimensions": ["latency", "accuracy", "cost", "resilience"],
        "tasks": [
            {"id": "t1", "estimated_latency_ms": 40, "cpu_cost": 0.01},
            {"id": "t2", "estimated_latency_ms": 70, "cpu_cost": 0.02},
        ],
        "resource_caps": {"max_latency_ms": 200, "max_cpu_cost": 0.1},
        "overrides": [{"key": "priority", "value": "high"}],
    }

    wf = registry.get_workflow(subflow_id)
    assert wf is not None, f"Subflow '{subflow_id}' not found in registry"
    await _assert_workflow_stream(
        svc,
        wf,
        base_inputs,
        run_id=f"test_sub_{subflow_id}",
        name=f"Subflow Test {subflow_id}",
    )


# ─────────────────────────────────────────────────────────────────────────────
# 2. Knowledge & Context Subflows (GCI / CCES) (Parameterized)
# ─────────────────────────────────────────────────────────────────────────────


GCI_SUBFLOWS = [
    "gci_merge_context",
    "gci_conflict_detect",
    "gci_publish_context",
    "gci_stamp_provenance",
    "compressed_context",
]


@pytest.mark.asyncio
@pytest.mark.parametrize("subflow_id", GCI_SUBFLOWS)
async def test_subflow_gci(subflow_id: str):
    """Test individual Global Context Infrastructure subflows."""
    registry = WorkflowRegistry()
    svc = WorkflowService()

    gci_inputs = {
        "envelopes": [
            {
                "source": "telemetry",
                "content": "Server cluster alpha reports operational CPU load 42%.",
                "timestamp": "2026-10-10T00:00:00Z",
            },
            {
                "source": "knowledge_engine",
                "content": "SLA boundary defines max acceptable CPU load at 85%.",
                "timestamp": "2026-10-10T00:00:00Z",
            },
        ],
        "precedence": ["system", "telemetry", "knowledge_engine", "memory"],
        "token_budget": 3000,
        "conflict_threshold": 0.7,
        "claims": [
            {"subject": "cluster_alpha", "statement": "CPU load is 42%", "value": 42, "source": "telemetry"},
            {"subject": "cluster_alpha", "statement": "CPU load is 42%", "value": 42, "source": "monitor"},
        ],
        "context": "Cluster status verification",
        "contradictions": [],
        "gaps": [],
        "signals": [{"type": "health", "status": "nominal"}],
        "budget": {"max_tokens": 2000},
        "merged_context": {"text": "Cluster operational."},
        "degraded_sources": [],
        "token_usage": {"prompt": 120, "completion": 45},
        "provenance_data": {"action": "context_assembled", "timestamp": "2026-10-10T00:00:00Z"},
        "query": "operational status of cluster alpha",
    }

    wf = registry.get_workflow(subflow_id)
    assert wf is not None, f"Subflow '{subflow_id}' not found in registry"
    await _assert_workflow_stream(
        svc,
        wf,
        gci_inputs,
        run_id=f"test_sub_{subflow_id}",
        name=f"Subflow Test {subflow_id}",
    )


# ─────────────────────────────────────────────────────────────────────────────
# 3. Governance, ZTEL & ACC Subflows (Parameterized)
# ─────────────────────────────────────────────────────────────────────────────


GOV_SUBFLOWS = [
    "ztel_sub_verify_identity",
    "ztel_sub_check_permission",
    "ztel_sub_evaluate_trust",
    "ztel_sub_evolve_trust",
    "ztel_sub_decide_verification",
    "ztel_sub_build_verification_request",
    "acc_sub_apply_risk_constraint",
    "acc_sub_evaluate_capability",
    "acc_sub_evaluate_conditional",
    "acc_sub_record_capability_decision",
    "acc_sub_resolve_capability_request",
    "acc_decide",
]


@pytest.mark.asyncio
@pytest.mark.parametrize("subflow_id", GOV_SUBFLOWS)
async def test_subflow_governance(subflow_id: str):
    """Test individual Governance, Zero-Trust (ZTEL) & Capability (ACC) subflows."""
    registry = WorkflowRegistry()
    svc = WorkflowService()

    gov_inputs = {
        "subject": {
            "agent_id": "operator_agent_77",
            "tenant_id": "tenant_prod_01",
            "base_trust_score": 0.95,
        },
        "actor": {
            "agent_id": "operator_agent_77",
            "tenant_id": "tenant_prod_01",
        },
        "action": {
            "name": "storage.read_snapshot",
            "risk_level": "low",
        },
        "resource": {
            "resource_id": "res_storage_101",
            "tenant_id": "tenant_prod_01",
        },
        "capability": "storage.read_snapshot",
        "identity_evidence": {
            "valid": True,
            "signature": "sig_valid_0x123",
            "tenant_id": "tenant_prod_01",
        },
        "required_trust_tier": "tier_1",
        "policy": {
            "allowed_actions": ["storage.read_snapshot"],
            "max_risk": "medium",
        },
        "risk_constraint": {
            "max_risk": "medium",
        },
        "evaluation_criteria": {"require_encryption": True},
        "conditional_policy": {
            "conditions": [{"attribute": "environment", "equals": "production"}]
        },
        "trust_evolution_event": {
            "type": "successful_task",
            "delta": 0.05,
        },
        "verification_result": {
            "verified": True,
            "confidence": 0.98,
        },
        "request": {
            "action": "storage.read_snapshot",
            "subject_id": "operator_agent_77",
        },
        "decision": {
            "permitted": True,
            "rationale": "Zero trust identity and capability matched",
        },
        "resolve_result": {
            "permitted": True,
            "action": "storage.read_snapshot",
        },
    }

    wf = registry.get_workflow(subflow_id)
    assert wf is not None, f"Subflow '{subflow_id}' not found in registry"
    await _assert_workflow_stream(
        svc,
        wf,
        gov_inputs,
        run_id=f"test_sub_{subflow_id}",
        name=f"Subflow Test {subflow_id}",
    )


# ─────────────────────────────────────────────────────────────────────────────
# 4. Execution Lifecycle Subflows (ECL & CLO) (Parameterized)
# ─────────────────────────────────────────────────────────────────────────────


LIFECYCLE_SUBFLOWS = [
    "ecl_sub_settle_postconditions",
    "clo_assess_task",
    "clo_report_efficiency",
    "provenance_ref",
]


@pytest.mark.asyncio
@pytest.mark.parametrize("subflow_id", LIFECYCLE_SUBFLOWS)
async def test_subflow_lifecycle(subflow_id: str):
    """Test individual ECL and CLO lifecycle subflows."""
    registry = WorkflowRegistry()
    svc = WorkflowService()

    ecl_inputs = {
        "postconditions": [
            {"dimension": "status", "operator": "eq", "threshold": "ok", "claim": "status"}
        ],
        "execution_result": {"status": "ok"},
        "contract_response": {"permit": True},
        "task_definition": {
            "task_id": "task_reindex_01",
            "estimated_complexity": "medium",
            "priority": "high",
        },
        "effort_budget": {
            "max_seconds": 60,
            "max_memory_mb": 512,
        },
        "efficiency_metrics": {
            "input_tokens": 150,
            "output_tokens": 40,
            "duration_ms": 320,
        },
        "workflow_name": "clo_workflow",
        "provider": "default_provider",
        "model": "default_model",
        "input_tokens": 100,
        "output_tokens": 50,
        "audit_data": {"action": "lifecycle_settled"},
    }

    wf = registry.get_workflow(subflow_id)
    assert wf is not None, f"Subflow '{subflow_id}' not found in registry"
    await _assert_workflow_stream(
        svc,
        wf,
        ecl_inputs,
        run_id=f"test_sub_{subflow_id}",
        name=f"Subflow Test {subflow_id}",
    )


# ─────────────────────────────────────────────────────────────────────────────
# 5. Numbered Composed System Workflows E2E (Parameterized)
# ─────────────────────────────────────────────────────────────────────────────


COMPOSED_WORKFLOWS = [
    "07-ztel_system_workflow",
    "23-acc_system_workflow",
    "05-eval_system_workflow",
    "10-mote_system_workflow",
    "85-wrm_system_workflow",
]


@pytest.mark.asyncio
@pytest.mark.parametrize("workflow_id", COMPOSED_WORKFLOWS)
async def test_composed_numbered_workflow(workflow_id: str):
    """Test individual composed Numbered System Workflows."""
    registry = WorkflowRegistry()
    svc = WorkflowService()

    payload = {
        "input_data": {
            "options": [
                {"id": "opt_1", "latency": 50, "accuracy": 0.95, "cost": 0.05},
                {"id": "opt_2", "latency": 100, "accuracy": 0.99, "cost": 0.10},
            ],
            "candidates": [
                {"id": "opt_1", "latency": 50, "accuracy": 0.95, "cost": 0.05},
                {"id": "opt_2", "latency": 100, "accuracy": 0.99, "cost": 0.10},
            ],
            "constraints": [
                {"dimension": "latency", "operator": "lte", "threshold": 120, "kind": "hard"}
            ],
            "weights": {"latency": 0.4, "accuracy": 0.4, "cost": 0.2},
            "directions": {
                "latency": "lower_is_better",
                "accuracy": "higher_is_better",
                "cost": "lower_is_better",
            },
            "dimensions": ["latency", "accuracy", "cost"],
            "postconditions": [
                {"dimension": "status", "operator": "eq", "threshold": "ok", "claim": "status"}
            ],
            "execution_result": {"status": "ok"},
            "contract_response": {"permit": True},
            "envelopes": [
                {"subject": "claim1", "statement": "metric A is 10", "value": 10, "source": "A"}
            ],
            "subject": {
                "agent_id": "worker_agent_01",
                "tenant_id": "tenant_prod",
                "base_trust_score": 0.95,
            },
            "action": {"name": "query.execute", "risk_level": "low"},
            "resource": {"resource_id": "res_01", "tenant_id": "tenant_prod"},
        }
    }

    wf = registry.get_workflow(workflow_id)
    assert wf is not None, f"Numbered workflow '{workflow_id}' not found in registry"
    await _assert_workflow_stream(
        svc,
        wf,
        payload,
        run_id=f"test_composed_{workflow_id}",
        name=f"Composed Test {workflow_id}",
    )
