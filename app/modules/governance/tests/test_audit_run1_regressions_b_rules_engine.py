"""Regression tests for the governance **rules-engine** slice audit.

Scope owned by subagent b4-rules-engine-b:
``common_lib/modules/governance/rules_engine/{nodes,definition,expression,
flow,policy,conditions,intelligence,temporal}/``.

Each test pins one fix or one measured property. No test is deleted and no
assertion is weakened by this file.

Fixes pinned here
-----------------
1. HIGH-1 — the fabric **write** node and the legacy-table **read** nodes used
   two disjoint in-memory registries, so an agent could append a rule version
   and always read back an empty history (silently, with ``enabled: True``).
2. ``@property`` stacked under ``@node`` never reaches the node registry
   (``nodes_registry`` collects only ``inspect.isfunction`` members), so two
   declared node names in this slice were dead declarations.
"""

from __future__ import annotations

import ast
from pathlib import Path

GOV_LIB = Path(
    "/home/siddharth/Documents/Dev/agentic-platform/Backend Monorepo/Python Libs"
    "/common_lib/src/common_lib/modules/governance"
)
RULES_ENGINE = GOV_LIB / "rules_engine"
LEGACY_NODES = GOV_LIB / "nodes" / "legacy_tables.py"
NODES_REGISTRY_INIT = Path(
    "/home/siddharth/Documents/Dev/agentic-platform/Backend Monorepo/Python Libs"
    "/common_lib/src/common_lib/modules/nodes_registry/__init__.py"
)


# ═══════════════════════════════════════════════════════════════════════════
# Fix 1 — HIGH-1: the fabric write node and the legacy read nodes shared
#          no registry, so a version appended by an agent read back empty.
# ═══════════════════════════════════════════════════════════════════════════


def test_fabric_write_node_and_history_node_share_one_registry(monkeypatch) -> None:
    """HIGH-1 regression: `fabric_rule_append` -> `gov_rules_version_history`.

    `fabric_rule_append` appends into the process-wide chain held by
    `rules_engine/nodes/fabric.py::_CHAIN`. The history node used to build a
    *fresh* `RuleVersionChain()`, which owns a private, empty `RulesRegistry`
    (`registry.py:26`). So an agent that appended version 1 and then asked for
    the history got `{"enabled": True, "history": []}` — indistinguishable from
    "this rule has no versions". Proved to return the appended rule below.
    """
    from common_lib.modules.governance.nodes import legacy_tables
    from common_lib.modules.governance.rules_engine.nodes.fabric import (
        fabric_rule_append,
    )

    monkeypatch.setenv(legacy_tables.ENV_FLAG, "1")
    rule_id = "audit_b4_probe_roundtrip"
    fabric_rule_append(
        {"rule_id": rule_id, "when": {"x": 1}, "then": {"set": {"y": 2}}}
    )
    fabric_rule_append(
        {"rule_id": rule_id, "when": {"x": 2}, "then": {"set": {"y": 3}}}
    )

    history = legacy_tables.gov_rules_version_history(rule_id)

    assert history["enabled"] is True
    # The whole point: the read side now observes the write side.
    assert [v["version"] for v in history["history"]] == [1, 2], (
        "the version-history node read a different in-memory registry than "
        "fabric_rule_append wrote to — write/read are disjoint"
    )
    assert history["history"][-1]["when"] == {"x": 2}


def test_history_node_reports_which_registry_it_read(monkeypatch) -> None:
    """A throwaway registry would always read empty — say so, do not hide it.

    `gov_rules_all_latest` and `gov_rules_version_history` both report a
    `scope`. `version_history` previously reported none, so an empty result
    looked like an authoritative answer.
    """
    from common_lib.modules.governance.nodes import legacy_tables

    monkeypatch.setenv(legacy_tables.ENV_FLAG, "1")
    result = legacy_tables.gov_rules_version_history("no_such_rule_at_all")
    assert result["enabled"] is True
    assert "scope" in result, "an empty history must be attributable to a registry"
    assert result["scope"] in {"fabric", "singleton", "transient"}
    assert result["history"] == []


def test_all_latest_sees_rules_appended_through_the_fabric_node(monkeypatch) -> None:
    """`gov_rules_all_latest` exposed `RulesRegistry.all_latest`, which the
    evaluation path uses. It must observe the same registry `fabric_rule_append`
    writes, otherwise it always reports zero rules."""
    from common_lib.modules.governance.nodes import legacy_tables
    from common_lib.modules.governance.rules_engine.nodes.fabric import (
        fabric_rule_append,
    )

    monkeypatch.setenv(legacy_tables.ENV_FLAG, "1")
    rule_id = "audit_b4_probe_all_latest"
    fabric_rule_append(
        {"rule_id": rule_id, "when": {"a": 1}, "then": {"set": {"b": 2}}}
    )

    result = legacy_tables.gov_rules_all_latest()

    assert result["enabled"] is True
    assert rule_id in [r["rule_id"] for r in result["rules"]], (
        "all_latest did not observe the fabric registry"
    )


def test_flag_off_still_never_touches_the_read_path(monkeypatch) -> None:
    """G9: the fix must not have widened the gate. Flag off => structured refusal."""
    from common_lib.modules.governance.nodes import legacy_tables

    monkeypatch.delenv(legacy_tables.ENV_FLAG, raising=False)
    for fn, kwargs in (
        (legacy_tables.gov_rules_version_history, {"rule_id": "x"}),
        (legacy_tables.gov_rules_all_latest, {}),
        (legacy_tables.gov_rules_evaluator_registry, {}),
    ):
        out = fn(**kwargs)
        assert out["enabled"] is False
        assert "history" not in out and "rules" not in out


def test_version_chain_exposes_its_registry() -> None:
    """`RuleVersionChain.registry` is the additive accessor the fix depends on.

    Without it a reader cannot reach the chain's registry at all, and is forced
    to build a fresh (always-empty) chain.
    """
    from common_lib.modules.governance.rules_engine.registry import (
        RuleDefinition,
        RulesRegistry,
    )
    from common_lib.modules.governance.rules_engine.versioning import (
        RuleVersionChain,
    )

    reg = RulesRegistry()
    reg.register(RuleDefinition(rule_id="p", when={}, then={"set": {}}))
    chain = RuleVersionChain(registry=reg)

    assert chain.registry is reg
    # A chain built with no argument still owns a private, empty registry —
    # this is precisely the trap the fix routes around.
    assert RuleVersionChain().registry is not chain.registry


# ═══════════════════════════════════════════════════════════════════════════
# Fix 2 — `@property` under `@node` is unreachable by construction.
# ═══════════════════════════════════════════════════════════════════════════


def _stacked_property_nodes() -> list[str]:
    """Any `@property` + `@node` pair on one method, in this slice.

    Scoped to the eight subdirectories this agent owns. The sibling owning
    `rules_engine/{core,execution,resilience,data,lifecycle,foundation,
    observability}/` still has 3 of these (measured 2026-09-30) and is
    reported, not asserted here — a slice boundary is not a defect list.
    """
    owned = (
        "nodes",
        "definition",
        "expression",
        "flow",
        "policy",
        "conditions",
        "intelligence",
        "temporal",
    )
    found = []
    for sub in owned:
        for f in (RULES_ENGINE / sub).rglob("*.py"):
            if "__pycache__" in f.parts or "tests" in f.parts:
                continue
            tree = ast.parse(f.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                names = {ast.unparse(d) for d in node.decorator_list}
                if "property" in names and any("node" in n for n in names):
                    found.append(f"{f.relative_to(RULES_ENGINE)}:{node.lineno}")
    return found


def test_no_node_decorated_property_remains_in_the_slice() -> None:
    """A `@node` under `@property` can never be discovered.

    `nodes_registry/__init__.py:315` collects class members with
    `inspect.getmembers(cls, predicate=inspect.isfunction)`, which excludes
    `property` objects. Two names in this slice
    (`rules_engine.ExecutionContext.input_data`,
    `rules_engine.ConditionOperator.is_temporal`) were declared and silently
    dropped. Pin the *class* of defect so it cannot come back.

    Pinned by AST rather than by registry introspection so the test stays fast
    and does not import all of common_lib.
    """
    assert _stacked_property_nodes() == [], (
        "@property + @node is unreachable: nodes_registry only collects "
        "inspect.isfunction members"
    )


def test_the_registry_really_does_skip_properties() -> None:
    """Root-cause guard: prove the discovery predicate that drops them.

    If a future change to `nodes_registry` starts collecting properties, the
    exclusion above becomes over-strict and this test tells us to revisit it.
    """
    import inspect

    src = NODES_REGISTRY_INIT.read_text(encoding="utf-8")
    assert "predicate=inspect.isfunction" in src
    assert not list(inspect.getmembers(property, predicate=inspect.isfunction))


def test_the_two_former_property_nodes_still_work_as_properties() -> None:
    """Removing the dead `@node` must not remove the property.

    The @node was unreachable, but the @property was load-bearing Python.
    """
    from common_lib.modules.governance.rules_engine.conditions.evaluator import (
        ConditionOperator,
    )
    from common_lib.modules.governance.rules_engine.definition.types import (
        ExecutionContext,
    )

    assert isinstance(ConditionOperator.__dict__["is_temporal"], property)
    assert isinstance(ExecutionContext.__dict__["input_data"], property)
    assert ConditionOperator.TEMPORAL.is_temporal is True
    assert ConditionOperator.EQ.is_temporal is False
    ctx = ExecutionContext({"k": 1})
    assert ctx.input_data == {"k": 1}
    assert ctx.get("k") == 1


def test_agent_can_still_read_the_execution_context_over_a_node() -> None:
    """The drop was safe only because a real node covers the same data.

    `ExecutionContext.input_data` is unreachable as a node, so the read must be
    published by `ExecutionContext.get`. This pins that the replacement exists.
    """
    from common_lib.modules.governance.rules_engine.definition.types import (
        ExecutionContext,
    )

    meta = getattr(ExecutionContext.get, "_node_metadata", None)
    assert meta is not None, "ExecutionContext.get must remain @node-decorated"
    assert meta.get("name") == "rules_engine.ExecutionContext.get"


# ═══════════════════════════════════════════════════════════════════════════
# G5 — absolute imports only (this slice).
# ═══════════════════════════════════════════════════════════════════════════


def test_slice_has_no_relative_imports() -> None:
    offenders = []
    for f in list(RULES_ENGINE.rglob("*.py")):
        if "__pycache__" in f.parts or "tests" in f.parts:
            continue
        tree = ast.parse(f.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level:
                offenders.append(f"{f.relative_to(RULES_ENGINE)}:{node.lineno}")
    assert offenders == [], f"relative imports in slice: {offenders}"
