"""Regression tests for the governance module audit (run 1, subagent `governance`).

Each test pins one fix or one measured property from
``docs/duplication-audit/MODULE-AUDIT-governance.md``. No test is deleted and
no assertion is weakened by this file.
"""

from __future__ import annotations

import ast
import os
from functools import lru_cache
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

GOV_LIB = Path(
    "/home/siddharth/Documents/Dev/agentic-platform/Backend Monorepo/Python Libs"
    "/common_lib/src/common_lib/modules/governance"
)
RULES_DB_MODELS = GOV_LIB / "rules_engine" / "db_models.py"
LEGACY_NODES = GOV_LIB / "nodes" / "legacy_tables.py"
CONFTEST = Path(__file__).parent / "conftest.py"


# ═══════════════════════════════════════════════════════════════════════════
# Fix 1 — the rules-engine string primary keys had no generator
# ═══════════════════════════════════════════════════════════════════════════


def test_rules_engine_string_pks_have_a_generator() -> None:
    """HIGH-1 regression: `id VARCHAR NOT NULL` with no Python-side default.

    Every INSERT that did not carry an explicit id raised
    `NotNullViolationError` (Postgres) / `IntegrityError` (SQLite), so
    `POST /api/v1/governance/rules-engine/{rulesets,rules}` returned 500 in
    production, not only in tests.
    """
    tree = ast.parse(RULES_DB_MODELS.read_text(encoding="utf-8"))
    str_pk_tables = {
        "rule_library_blocks",
        "rule_sets",
        "rules",
        "rule_policies",
    }
    checked = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        tablename = None
        for stmt in node.body:
            if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
                t = stmt.targets[0]
                if isinstance(t, ast.Name) and t.id == "__tablename__":
                    tablename = ast.literal_eval(stmt.value)
        if tablename not in str_pk_tables:
            continue
        checked += 1
        for stmt in node.body:
            if not isinstance(stmt, ast.AnnAssign) or not stmt.target:
                continue
            target = stmt.target
            if not (isinstance(target, ast.Name) and target.id == "id"):
                continue
            assert stmt.value is not None, (
                f"{tablename}.id has no default and no default_factory — "
                "every INSERT without an explicit id will violate NOT NULL"
            )
            # The default must be a factory, not a shared constant.
            assert isinstance(stmt.value, ast.Call), (
                f"{tablename}.id default must be a default_factory call"
            )
            # `stmt.value.func` is the OUTER call — i.e. `Field` — so asserting
            # on it can never match. The generator is the value of the
            # `default_factory` keyword.
            factory_kw = next(
                (kw for kw in stmt.value.keywords if kw.arg == "default_factory"),
                None,
            )
            assert factory_kw is not None, (
                f"{tablename}.id must declare default_factory=_new_id"
            )
            factory = ast.unparse(factory_kw.value)
            assert factory == "_new_id", (
                f"{tablename}.id must use the _new_id generator, got {factory}"
            )
    assert checked == 4, f"expected 4 string-PK rules-engine tables, found {checked}"


def test_new_id_generator_produces_unique_non_empty_strings() -> None:
    from common_lib.modules.governance.rules_engine.db_models import _new_id

    values = {_new_id() for _ in range(200)}
    assert len(values) == 200
    assert all(isinstance(v, str) and v for v in values)


def test_new_id_generator_emits_no_ddl() -> None:
    """G6: the fix must not require a migration.

    A Python-side `default_factory` produces a NOT NULL column with no server
    default — byte-identical DDL to before the fix. If this ever starts
    emitting a server default, a hand-written Alembic migration is required.
    """
    from sqlalchemy.dialects import postgresql
    from sqlalchemy.schema import CreateTable
    from sqlmodel import SQLModel

    import common_lib.modules.governance.rules_engine.db_models  # noqa: F401

    ddl = str(
        CreateTable(SQLModel.metadata.tables["rule_sets"]).compile(
            dialect=postgresql.dialect()
        )
    )
    assert "id VARCHAR NOT NULL" in ddl
    assert "DEFAULT" not in ddl.upper().split("PRIMARY KEY")[0]


# ═══════════════════════════════════════════════════════════════════════════
# Fix 2 — the test conftest never created the rules-engine tables
# ═══════════════════════════════════════════════════════════════════════════


def test_conftest_imports_the_rules_engine_db_models() -> None:
    """The governance conftest must register rule_sets/rules before create_all."""
    src = CONFTEST.read_text(encoding="utf-8")
    assert "rules_engine.db_models" in src, (
        "conftest must import rules_engine.db_models or SQLModel.metadata."
        "create_all() silently omits rule_sets/rules"
    )
    for model in ("RuleSetModel", "RuleModel", "RuleLibraryBlockModel"):
        assert model in src, f"conftest must import {model}"


def test_rules_engine_tables_exist_in_the_test_database(db_session) -> None:
    from sqlalchemy import inspect

    from common_lib.modules.data_storage.database.connection import get_session  # noqa: F401

    names = set(inspect(db_session.get_bind()).get_table_names())
    for table in ("rule_sets", "rules", "rule_library_blocks"):
        assert table in names, f"{table} missing from the test database"


# ═══════════════════════════════════════════════════════════════════════════
# Fix 3 — the 20 new @node wrappers (C1), gated default-OFF (G9)
# ═══════════════════════════════════════════════════════════════════════════


NEW_NODES = [
    "governance.hitl_legacy.create_decision",
    "governance.hitl_legacy.list_decisions",
    "governance.hitl_legacy.get_decision",
    "governance.hitl_legacy.delete_decision",
    "governance.hitl_legacy.decision_stats",
    "governance.hitl_legacy.create_task",
    "governance.hitl_legacy.list_tasks",
    "governance.hitl_legacy.get_task",
    "governance.hitl_legacy.update_task",
    "governance.hitl_legacy.delete_task",
    "governance.hitl_legacy.task_stats",
    "governance.hitl_legacy.create_assignment",
    "governance.hitl_legacy.list_assignments",
    "governance.hitl_legacy.get_assignment",
    "governance.hitl_legacy.update_assignment",
    "governance.hitl_legacy.delete_assignment",
    "governance.hitl_legacy.create_audit_log",
    "governance.hitl_legacy.list_audit_logs",
    "governance.hitl_legacy.get_audit_log",
    "governance.hitl_legacy.audit_log_stats",
    "governance.policy.version_history",
    "governance.policy.registry_history",
    "governance.rules.version_history",
    "governance.rules.all_latest",
    "governance.rules.evaluator_registry",
]

G3_FIELDS = (
    "name",
    "description",
    "category",
    "tags",
    "audience",
    "input_schema",
    "output_schema",
    "execution_timeout",
)


def _new_node_calls() -> list[ast.Call]:
    tree = ast.parse(LEGACY_NODES.read_text(encoding="utf-8"))
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            target = dec.func if isinstance(dec, ast.Call) else dec
            if isinstance(target, ast.Name) and target.id == "node":
                out.append(dec if isinstance(dec, ast.Call) else None)
    return [c for c in out if c is not None]


def test_all_25_new_nodes_are_declared() -> None:
    declared = set()
    for call in _new_node_calls():
        for kw in call.keywords:
            if kw.arg == "name":
                declared.add(ast.literal_eval(kw.value))
    missing = [n for n in NEW_NODES if n not in declared]
    assert not missing, f"missing node declarations: {missing}"


@pytest.mark.parametrize("node_name", NEW_NODES)
def test_new_node_has_full_g3_metadata(node_name: str) -> None:
    """G3: every wrapper carries all eight fields, with a real description."""
    for call in _new_node_calls():
        kw = {k.arg: k.value for k in call.keywords}
        if ast.literal_eval(kw.get("name", ast.Constant(""))) != node_name:
            continue
        for field in G3_FIELDS:
            assert field in kw, f"{node_name}: missing G3 field {field!r}"
        description = ast.literal_eval(kw["description"])
        assert len(description) > 60, (
            f"{node_name}: description is too thin to let an agent use it "
            f"without reading source ({len(description)} chars)"
        )
        tags = ast.literal_eval(kw["tags"])
        assert len(tags) >= 3, f"{node_name}: needs >=3 tags, got {tags}"
        audience = ast.literal_eval(kw["audience"])
        assert audience and set(audience) <= {"planner", "executor", "system"}, (
            f"{node_name}: bad audience {audience}"
        )
        timeout = ast.literal_eval(kw["execution_timeout"])
        assert isinstance(timeout, int) and 1 <= timeout <= 300
        return
    pytest.fail(f"no @node call found for {node_name}")


def test_new_nodes_are_not_added_to_the_nodes_package_reexport() -> None:
    """C3: the `nodes/__init__.py` star-import double-registers every node.

    The registry AST-scans the `nodes/` directory, so a name re-exported from
    `__init__` is discovered twice — once as `…nodes.legacy_tables` and once as
    `…nodes` — and `node_bridge` flattens first-wins, so which copy serves MCP
    depends on filesystem walk order. The 20 wrappers are discovered without the
    re-export, so it must stay out.
    """
    init = (GOV_LIB / "nodes" / "__init__.py").read_text(encoding="utf-8")
    assert "legacy_tables import *" not in init, (
        "nodes/__init__.py must not star-import legacy_tables — it creates 25 "
        "duplicate @node registrations"
    )


def test_new_node_names_are_unique_in_the_registry() -> None:
    """C3: none of the 25 new names collides with an existing @node name."""
    from common_lib.modules.nodes_registry import discover_nodes

    nodes = discover_nodes()
    by_name: dict[str, list[str]] = {}
    for n in nodes:
        by_name.setdefault(n.name, []).append(n.module)
    for name in NEW_NODES:
        modules = by_name.get(name, [])
        assert len(modules) == 1, f"{name} registered {len(modules)}x: {modules}"


def test_new_nodes_are_discoverable() -> None:
    from common_lib.modules.nodes_registry import discover_nodes

    found = {
        n.name
        for n in discover_nodes()
        if n.module == "common_lib.modules.governance.nodes.legacy_tables"
    }
    assert found == set(NEW_NODES), (
        f"registry mismatch; missing {sorted(set(NEW_NODES) - found)}, "
        f"unexpected {sorted(found - set(NEW_NODES))}"
    )


# ═══════════════════════════════════════════════════════════════════════════
# G9 — the new wrappers are gated default-OFF
# ═══════════════════════════════════════════════════════════════════════════


def test_legacy_table_nodes_flag_defaults_off(monkeypatch) -> None:
    from common_lib.modules.governance.nodes import legacy_tables

    monkeypatch.delenv(legacy_tables.ENV_FLAG, raising=False)
    assert legacy_tables.is_legacy_table_nodes_enabled() is False


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("1", True),
        ("true", True),
        ("TRUE", True),
        ("yes", True),
        ("0", False),
        ("false", False),
        ("no", False),
        ("off", False),
        ("", False),
        ("  ", False),
    ],
)
def test_legacy_table_nodes_flag_env_parsing(monkeypatch, raw, expected) -> None:
    from common_lib.modules.governance.nodes import legacy_tables

    monkeypatch.setenv(legacy_tables.ENV_FLAG, raw)
    assert legacy_tables.is_legacy_table_nodes_enabled() is expected


def test_flag_off_never_touches_the_database(monkeypatch) -> None:
    """G9: with the flag off every wrapper short-circuits before any service call."""
    from common_lib.modules.governance.nodes import legacy_tables

    monkeypatch.delenv(legacy_tables.ENV_FLAG, raising=False)

    called = []

    def _boom(*_a, **_k):
        called.append(1)
        raise AssertionError("service must not be constructed while the flag is off")

    monkeypatch.setattr(legacy_tables, "_legacy_service", _boom)

    for fn in (
        legacy_tables.gov_hitl_legacy_list_tasks,
        legacy_tables.gov_hitl_legacy_task_stats,
        legacy_tables.gov_hitl_legacy_decision_stats,
        legacy_tables.gov_hitl_legacy_audit_log_stats,
    ):
        result = fn()
        assert result["enabled"] is False
        assert result["flag"] == legacy_tables.FLAG_NAME
        assert legacy_tables.ENV_FLAG in result["reason"]
    assert not called


def test_flag_on_uses_the_registered_singleton(monkeypatch) -> None:
    from common_lib.modules.governance.nodes import legacy_tables

    monkeypatch.setenv(legacy_tables.ENV_FLAG, "1")
    registry = (
        legacy_tables._rules_registry.__wrapped__
        if hasattr(legacy_tables._rules_registry, "__wrapped__")
        else None
    )
    assert registry is None  # sanity: helper is a plain function

    from common_lib.modules.governance.rules_engine.registry import (
        RuleDefinition,
        RulesRegistry,
    )

    reg = RulesRegistry()
    reg.register(RuleDefinition(rule_id="r1", when={"a": 1}, then={"set": {"b": 2}}))
    legacy_tables.register_rules_registry(reg)
    try:
        result = legacy_tables.gov_rules_all_latest()
        assert result["enabled"] is True
        assert result["scope"] == "singleton"
        assert [r["rule_id"] for r in result["rules"]] == ["r1"]
    finally:
        legacy_tables.register_rules_registry(None)


def test_transient_registry_scope_is_reported_not_hidden(monkeypatch) -> None:
    """A throwaway registry would always read empty — say so rather than lie.

    Reaching ``scope="transient"`` requires *no* live registry at all: no
    registered singleton AND no live fabric chain. The fabric chain always
    exists (it is a module-level singleton in ``nodes/fabric.py``), so the test
    has to remove that collaborator too — otherwise it is not exercising the
    transient branch it claims to pin.
    """
    from common_lib.modules.governance.nodes import legacy_tables

    monkeypatch.setenv(legacy_tables.ENV_FLAG, "1")
    legacy_tables.register_rules_registry(None)

    import common_lib.modules.governance.rules_engine.nodes.fabric as fabric

    monkeypatch.setattr(fabric, "get_fabric_rule_chain", lambda: None, raising=True)
    result = legacy_tables.gov_rules_all_latest()
    assert result["enabled"] is True
    assert result["scope"] == "transient"
    assert result["rules"] == []


def test_rules_readers_follow_the_live_fabric_chain(monkeypatch) -> None:
    """With no registered singleton the readers must still see real writes.

    ``fabric_rule_append`` writes into the process-wide fabric chain. Before the
    fix the read nodes built a *fresh* ``RulesRegistry``, so an agent could
    append a rule version and every read node would report zero rules.
    """
    from common_lib.modules.governance.nodes import legacy_tables

    monkeypatch.setenv(legacy_tables.ENV_FLAG, "1")
    legacy_tables.register_rules_registry(None)

    import common_lib.modules.governance.rules_engine.nodes.fabric as fabric

    chain = fabric.get_fabric_rule_chain()
    rule_id = "audit_fabric_scope_probe"
    chain.registry._rules.pop(rule_id, None)
    try:
        chain.append(
            rule_id,
            {"a": 1},
            {"set": {"b": 2}},
            description="scope-probe",
        )
        latest = legacy_tables.gov_rules_all_latest()
        assert latest["scope"] == "fabric", (
            "with no registered singleton the readers must resolve the live "
            "fabric chain, not a throwaway registry"
        )
        assert rule_id in [r["rule_id"] for r in latest["rules"]]

        history = legacy_tables.gov_rules_version_history(rule_id)
        assert history["scope"] == "fabric"
        assert [h["version"] for h in history["history"]] == [1]
    finally:
        chain.registry._rules.pop(rule_id, None)


def test_policy_version_history_reads_the_live_registry_chain(monkeypatch) -> None:
    """The policy history node must read the chain ``register()`` appends to.

    ``PolicyRegistry`` owns its chain as ``_versions``
    (``governance/policy/registry.py:50``) and ``register()`` appends there
    (``:57``). A node that constructed its own ``PolicyVersionChain`` read a
    different, permanently empty object — it reported ``history == []`` for
    every policy forever, which is a silent no-op, not a truthful empty result.
    """
    from common_lib.modules.governance.nodes import legacy_tables
    from common_lib.modules.governance.policy.registry import PolicyRegistry

    monkeypatch.setenv(legacy_tables.ENV_FLAG, "1")
    from common_lib.modules.governance.policy.registry import ScopedPolicy

    registry = PolicyRegistry()
    legacy_tables.register_policy_registry(registry)
    try:
        version = registry.register(
            ScopedPolicy(policy_id="p-live", scope="platform", rules={"r": 1}),
            author="alice",
        )
        assert version.version == 1

        result = legacy_tables.gov_policy_version_history("p-live")
        assert result["enabled"] is True
        assert result["scope"] == "singleton", (
            "the node must report that it read the registered registry, and it "
            "must read that registry's own chain"
        )
        assert [h["version"] for h in result["history"]] == [1]
        assert result["history"][0]["author"] == "alice"

        import json

        json.dumps(result)  # must be serialisable for the MCP bridge
    finally:
        legacy_tables.register_policy_registry(None)


def test_policy_version_history_scope_is_transient_without_a_singleton(
    monkeypatch,
) -> None:
    """With no registered registry the node must say so, not imply a live read."""
    from common_lib.modules.governance.nodes import legacy_tables

    monkeypatch.setenv(legacy_tables.ENV_FLAG, "1")
    legacy_tables.register_policy_registry(None)
    result = legacy_tables.gov_policy_version_history("p1")
    assert result["enabled"] is True
    assert result["scope"] == "transient"
    assert result["history"] == []


def test_history_nodes_return_serialisable_dicts(monkeypatch) -> None:
    from common_lib.modules.governance.nodes import legacy_tables
    from common_lib.modules.governance.policy.versioning import (
        PolicyVersionChain,
    )

    monkeypatch.setenv(legacy_tables.ENV_FLAG, "1")
    chain = PolicyVersionChain()
    chain.append("p1", {"x": 1}, author="alice", reason="first")
    chain.append("p1", {"x": 2}, author="bob", reason="second")

    import json

    # No registry is registered, so the node correctly reports a transient read.
    result = legacy_tables.gov_policy_version_history("p1")
    assert result["enabled"] is True
    assert result["scope"] == "transient"
    assert result["history"] == []
    json.dumps(result)  # must be serialisable for the MCP bridge


def test_unavailable_service_returns_a_typed_payload_not_an_exception(
    monkeypatch,
) -> None:
    """G8: a node must never take the MCP bridge down."""
    from common_lib.modules.governance.nodes import legacy_tables

    monkeypatch.setenv(legacy_tables.ENV_FLAG, "1")
    monkeypatch.setattr(legacy_tables, "_legacy_service", lambda: None)
    result = legacy_tables.gov_hitl_legacy_list_tasks()
    assert result["enabled"] is True
    assert result["ok"] is False
    assert "HitlLegacyService unavailable" in result["error"]


# ═══════════════════════════════════════════════════════════════════════════
# G2 / G5 — architecture properties of the module
# ═══════════════════════════════════════════════════════════════════════════


def test_new_nodes_file_has_no_relative_imports() -> None:
    """G5: absolute imports only."""
    tree = ast.parse(LEGACY_NODES.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level:
            pytest.fail(f"G5 violation: relative import {ast.unparse(node)}")
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith("."), f"G5: {alias.name}"


def test_new_nodes_reach_hitl_legacy_service_through_the_port() -> None:
    """G2: never import another module's service directly."""
    tree = ast.parse(LEGACY_NODES.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            assert not node.module.endswith("legacy_tables_service"), (
                "G2: use integration.ports.hitl.hitl_port.get_hitl_legacy_service"
            )
    src = LEGACY_NODES.read_text(encoding="utf-8")
    assert "integration.ports.hitl.hitl_port" in src


def test_governance_has_no_relative_imports() -> None:
    """G5 across the whole module."""
    offenders = []
    for path in GOV_LIB.rglob("*.py"):
        if "__pycache__" in path.parts or "tests" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level:
                offenders.append(f"{path}:{node.lineno}")
    assert not offenders, f"G5 relative imports: {offenders}"


# ═══════════════════════════════════════════════════════════════════════════
# C2 — HTTP surface
# ═══════════════════════════════════════════════════════════════════════════

UI_CALLED_ENDPOINTS = [
    ("GET", "/api/v1/governance/identity"),
    ("POST", "/api/v1/governance/identity"),
    ("PUT", "/api/v1/governance/identity/{agent_id}"),
    ("DELETE", "/api/v1/governance/identity/{agent_id}"),
    ("POST", "/api/v1/governance/identity/{agent_id}/transition"),
    ("GET", "/api/v1/governance/auth/tokens"),
    ("POST", "/api/v1/governance/auth/tokens"),
    ("POST", "/api/v1/governance/auth/tokens/revoke"),
    ("GET", "/api/v1/governance/auth/api-keys"),
    ("POST", "/api/v1/governance/auth/api-keys"),
    ("POST", "/api/v1/governance/auth/api-keys/revoke"),
    ("GET", "/api/v1/governance/auth/mtls"),
    ("POST", "/api/v1/governance/auth/mtls"),
    ("GET", "/api/v1/governance/rbac/roles"),
    ("POST", "/api/v1/governance/rbac/roles"),
    ("DELETE", "/api/v1/governance/rbac/roles/{role_id}"),
    ("GET", "/api/v1/governance/rbac/permissions"),
    ("POST", "/api/v1/governance/rbac/permissions"),
    ("DELETE", "/api/v1/governance/rbac/permissions/{perm_id}"),
    ("GET", "/api/v1/governance/rbac/groups"),
    ("POST", "/api/v1/governance/rbac/groups"),
    ("PUT", "/api/v1/governance/rbac/groups/{group_id}"),
    ("DELETE", "/api/v1/governance/rbac/groups/{group_id}"),
    ("POST", "/api/v1/governance/rbac/groups/{group_id}/members"),
    ("GET", "/api/v1/governance/policies"),
    ("POST", "/api/v1/governance/policies"),
    ("PUT", "/api/v1/governance/policies/{policy_id}"),
    ("DELETE", "/api/v1/governance/policies/{policy_id}"),
    ("POST", "/api/v1/governance/policies/{policy_id}/enable"),
    ("POST", "/api/v1/governance/policies/{policy_id}/disable"),
    ("GET", "/api/v1/governance/policies/groups"),
    ("POST", "/api/v1/governance/policies/groups"),
    ("GET", "/api/v1/governance/policies/groups-links"),
    ("PUT", "/api/v1/governance/policies/groups/{group_id}"),
    ("DELETE", "/api/v1/governance/policies/groups/{group_id}"),
    ("POST", "/api/v1/governance/policies/groups/{group_id}/policies/{policy_id}"),
    ("DELETE", "/api/v1/governance/policies/groups/{group_id}/policies/{policy_id}"),
    ("GET", "/api/v1/governance/hitl/requests"),
    ("POST", "/api/v1/governance/hitl/requests"),
    ("GET", "/api/v1/governance/hitl/overrides"),
    ("POST", "/api/v1/governance/hitl/overrides"),
    ("POST", "/api/v1/governance/hitl/requests/{request_id}/approve"),
    ("POST", "/api/v1/governance/hitl/requests/{request_id}/deny"),
    ("POST", "/api/v1/governance/hitl/requests/{request_id}/modify"),
    ("POST", "/api/v1/governance/hitl/requests/{request_id}/execute"),
    ("POST", "/api/v1/governance/hitl/requests/{request_id}/feedback"),
    ("GET", "/api/v1/governance/trust/scores"),
    ("GET", "/api/v1/governance/trust/events"),
    ("POST", "/api/v1/governance/trust/events"),
    ("PUT", "/api/v1/governance/trust/scores/{subject_id}"),
    ("GET", "/api/v1/governance/audit/events"),
    ("DELETE", "/api/v1/governance/audit/events"),
    ("GET", "/api/v1/governance/compliance/frameworks"),
    ("GET", "/api/v1/governance/compliance/reports"),
    ("POST", "/api/v1/governance/compliance/reports"),
    ("GET", "/api/v1/governance/incidents"),
    ("POST", "/api/v1/governance/incidents"),
    ("POST", "/api/v1/governance/incidents/{incident_id}/{status}"),
    ("GET", "/api/v1/governance/tools"),
    ("POST", "/api/v1/governance/tools"),
    ("PUT", "/api/v1/governance/tools/{tool_id}"),
    ("POST", "/api/v1/governance/tools/{tool_id}/validate"),
    ("GET", "/api/v1/governance/workflows"),
    ("POST", "/api/v1/governance/workflows"),
    ("POST", "/api/v1/governance/workflows/{workflow_id}/validate"),
    ("GET", "/api/v1/governance/memory-gov/namespaces"),
    ("POST", "/api/v1/governance/memory-gov/namespaces"),
    ("POST", "/api/v1/governance/memory-gov/namespaces/{ns_id}/check"),
    ("POST", "/api/v1/governance/integration/evaluate"),
    ("POST", "/api/v1/governance/integration/validate-token"),
    ("GET", "/api/v1/governance/delegations"),
    ("POST", "/api/v1/governance/delegations"),
    ("POST", "/api/v1/governance/delegations/{delegation_id}/revoke"),
    ("GET", "/api/v1/governance/delegations/check"),
    ("GET", "/api/v1/governance/role-assignments"),
    ("POST", "/api/v1/governance/role-assignments"),
    ("DELETE", "/api/v1/governance/role-assignments/{assignment_id}"),
    ("GET", "/api/v1/governance/approval-policies"),
    ("POST", "/api/v1/governance/approval-policies"),
    ("PUT", "/api/v1/governance/approval-policies/{policy_id}"),
    ("DELETE", "/api/v1/governance/approval-policies/{policy_id}"),
    ("GET", "/api/v1/governance/approval-policies/triggers"),
    ("POST", "/api/v1/governance/approval-policies/triggers"),
    ("PUT", "/api/v1/governance/approval-policies/triggers/{trigger_id}"),
    ("DELETE", "/api/v1/governance/approval-policies/triggers/{trigger_id}"),
    ("GET", "/api/v1/governance/approval-policies/hooks"),
    ("POST", "/api/v1/governance/approval-policies/hooks"),
    ("PUT", "/api/v1/governance/approval-policies/hooks/{hook_id}"),
    ("DELETE", "/api/v1/governance/approval-policies/hooks/{hook_id}"),
    ("GET", "/api/v1/governance/approval-policies/interceptors"),
    ("POST", "/api/v1/governance/approval-policies/interceptors"),
    ("PUT", "/api/v1/governance/approval-policies/interceptors/{interceptor_id}"),
    ("DELETE", "/api/v1/governance/approval-policies/interceptors/{interceptor_id}"),
]


@lru_cache(maxsize=1)
def _live_routes() -> frozenset[tuple[str, str]]:
    """The app's real (method, path) surface, built ONCE per session.

    ``register_routers`` pulls in every module in the platform and takes roughly
    a minute. This was previously uncached and called from a 93-case
    parametrised test, so the file took over an hour and a half to run and
    looked like a hang. The route table cannot change within a session, so it
    is memoised. Returns a frozenset so no caller can mutate the cached value.
    """
    from fastapi import FastAPI
    from fastapi.routing import APIRoute

    from app.core.routers import register_routers

    app = FastAPI()
    register_routers(app, "/api/v1", [])
    out = set()
    for r in app.routes:
        if isinstance(r, APIRoute):
            for m in r.methods:
                if m not in ("HEAD", "OPTIONS"):
                    out.add((m, r.path))
    return frozenset(out)


@pytest.mark.parametrize("method,path", UI_CALLED_ENDPOINTS)
def test_every_ui_called_governance_endpoint_is_mounted(method, path) -> None:
    """C2: GovernancePage calls 92 endpoints; none may be missing."""
    live = _live_routes()
    assert (method, path) in live, f"UI calls {method} {path} but it is not mounted"


def test_rules_engine_crud_endpoints_are_mounted() -> None:
    """C2: the rules-engine surface the RulesHub section drives."""
    live = _live_routes()
    for method, path in [
        ("GET", "/api/v1/governance/rules-engine/rules"),
        ("POST", "/api/v1/governance/rules-engine/rules"),
        ("GET", "/api/v1/governance/rules-engine/rules/{rule_id}"),
        ("PUT", "/api/v1/governance/rules-engine/rules/{rule_id}"),
        ("DELETE", "/api/v1/governance/rules-engine/rules/{rule_id}"),
        ("POST", "/api/v1/governance/rules-engine/rules/{rule_id}/evaluate"),
        ("GET", "/api/v1/governance/rules-engine/rules/{rule_id}/versions"),
        ("POST", "/api/v1/governance/rules-engine/rules/{rule_id}/versions/publish"),
        ("GET", "/api/v1/governance/rules-engine/rulesets"),
        ("POST", "/api/v1/governance/rules-engine/rulesets"),
        ("GET", "/api/v1/governance/rules-engine/rulesets/{ruleset_id}"),
        ("PUT", "/api/v1/governance/rules-engine/rulesets/{ruleset_id}"),
        ("DELETE", "/api/v1/governance/rules-engine/rulesets/{ruleset_id}"),
        ("GET", "/api/v1/governance/rules-engine/rulesets-links"),
        ("POST", "/api/v1/governance/rules-engine/rules/sync"),
        ("GET", "/api/v1/governance/rules-engine/library"),
        ("POST", "/api/v1/governance/rules-engine/library"),
    ]:
        assert (method, path) in live, f"{method} {path} is not mounted"


# ═══════════════════════════════════════════════════════════════════════════
# HIGH-1 — the rules-engine write path actually works end to end
# ═══════════════════════════════════════════════════════════════════════════


def test_create_ruleset_returns_200_with_a_generated_id(client: TestClient) -> None:
    """HIGH-1 behavioural regression — was a 500 with NOT NULL failed: rule_sets.id."""
    resp = client.post(
        "/api/v1/governance/rules-engine/rulesets",
        json={
            "name": "regression-rs",
            "description": "",
            "enabled": True,
            "priority": 1,
            "conflict_strategy": "priority_wins",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"], "a ruleset must come back with a generated primary key"
    assert body["name"] == "regression-rs"


def test_create_rule_returns_200_with_a_generated_id(client: TestClient) -> None:
    """HIGH-1 behavioural regression — was a 500 with NOT NULL failed: rules.id."""
    resp = client.post(
        "/api/v1/governance/rules-engine/rules",
        json={
            "name": "regression-rule",
            "description": "",
            "type": "standard",
            "enabled": True,
            "priority": 1,
            "version": "1.0.0",
            "status": "draft",
            "owner": "",
            "tags_json": "[]",
            "condition_group": {},
            "actions": [],
            "else_actions": None,
            "metadata_json": "{}",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"], "a rule must come back with a generated primary key"
    assert body["name"] == "regression-rule"


def test_created_ruleset_is_retrievable_by_its_id(client: TestClient) -> None:
    """The generated id must actually work as a lookup key, not just be present."""
    created = client.post(
        "/api/v1/governance/rules-engine/rulesets",
        json={"name": "regression-rs-roundtrip", "priority": 1},
    )
    assert created.status_code == 200, created.text
    ruleset_id = created.json()["id"]

    fetched = client.get(f"/api/v1/governance/rules-engine/rulesets/{ruleset_id}")
    assert fetched.status_code == 200, fetched.text
    assert fetched.json()["id"] == ruleset_id


def test_generated_ids_are_unique(client: TestClient) -> None:
    a = client.post(
        "/api/v1/governance/rules-engine/rulesets",
        json={"name": "dup-a", "priority": 1},
    )
    b = client.post(
        "/api/v1/governance/rules-engine/rulesets",
        json={"name": "dup-b", "priority": 1},
    )
    assert a.status_code == 200 and b.status_code == 200
    assert a.json()["id"] != b.json()["id"]


# ══════════════════════════════════════════════════════════════════════════
# C1 — the reactive flow's only execution entry point had no agent path.
#
# `ReactiveFlow.process_event` is the one method on the class that actually RUNS
# a flow (interceptors -> triggers -> rules -> hooks). Every other wrapped method
# is a wiring setter, and the class itself is auto-registered as a node, so an
# agent could wire a flow but had no way to execute one.
# ══════════════════════════════════════════════════════════════════════════

REACTIVE = GOV_LIB / "rules_engine" / "flow" / "reactive.py"


def test_reactive_process_event_has_an_agent_reachable_node() -> None:
    """AST: the async coroutine has a sync @node adapter, not just the class."""
    tree = ast.parse(REACTIVE.read_text())
    reactive_flow = next(
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.ClassDef) and n.name == "ReactiveFlow"
    )
    methods = {
        m.name: m
        for m in reactive_flow.body
        if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert "process_event" in methods, "the coroutine itself must still exist"
    assert isinstance(methods["process_event"], ast.AsyncFunctionDef), (
        "process_event must stay a coroutine — the @node wrapper adapts it, "
        "it does not replace it"
    )
    adapter = methods["process_event_node"]
    assert any(
        isinstance(d, ast.Call) and ast.unparse(d.func).split(".")[-1] == "node"
        for d in adapter.decorator_list
    ), "process_event_node must carry an @node decorator"


def test_reactive_process_event_node_is_gated_off_by_default(monkeypatch) -> None:
    """G9: importing the wrapper must not make it live, and flag-off runs nothing."""
    from common_lib.modules.governance.rules_engine.flow import reactive

    monkeypatch.delenv(reactive._PROCESS_EVENT_ENV, raising=False)
    assert reactive._process_event_nodes_enabled() is False

    ran: list[str] = []
    flow = reactive.ReactiveFlow(name="gate-probe")
    flow._before_interceptors.append(lambda ctx: ran.append("before"))

    out = flow.process_event_node("evt", {})
    assert out["enabled"] is False
    assert out["operation"] == "process_event"
    assert reactive._PROCESS_EVENT_FLAG in out["reason"]
    assert ran == [], "flag off must not execute any interceptor"


def test_reactive_process_event_node_runs_the_flow_when_enabled(monkeypatch) -> None:
    """Flag ON: the adapter really drives the coroutine and returns its result."""
    from common_lib.modules.governance.rules_engine.flow import reactive

    monkeypatch.setenv(reactive._PROCESS_EVENT_ENV, "1")
    assert reactive._process_event_nodes_enabled() is True

    ran: list[str] = []
    flow = reactive.ReactiveFlow(name="run-probe")
    flow._before_interceptors.append(lambda ctx: ran.append("before"))

    out = flow.process_event_node("order.created", {"id": 7}, source="test")
    assert out["enabled"] is True
    assert ran == ["before"], "the before-interceptor must actually have run"
    assert out["result"]["event_id"].startswith("evt_")
    # json-serialisable for the MCP bridge
    import json

    json.dumps(out)


def test_reactive_process_event_node_reports_failure_without_raising(
    monkeypatch,
) -> None:
    """G8: a node must never take the MCP bridge down."""
    from common_lib.modules.governance.rules_engine.flow import reactive

    monkeypatch.setenv(reactive._PROCESS_EVENT_ENV, "1")
    flow = reactive.ReactiveFlow(name="boom-probe")

    async def _explode(*args, **kwargs):
        raise RuntimeError("interceptor exploded")

    monkeypatch.setattr(flow, "process_event", _explode)
    out = flow.process_event_node("evt", {})
    assert out["enabled"] is True
    assert out["ok"] is False
    assert "RuntimeError" in out["error"]


def test_reactive_process_event_node_carries_full_g3_metadata() -> None:
    """G3: all eight fields, and a description an agent can act on."""
    from common_lib.modules.governance.rules_engine.flow import reactive

    meta = reactive.ReactiveFlow.process_event_node._node_metadata
    for field in (
        "name",
        "description",
        "category",
        "tags",
        "audience",
        "input_schema",
        "output_schema",
        "execution_timeout",
    ):
        assert meta.get(field), f"missing G3 field: {field}"
    assert meta["name"] == "rules_engine.ReactiveFlow.process_event"
    assert len(meta["description"]) > 80, "description is too thin to route on"
    assert len(meta["tags"]) >= 3


def test_reactive_process_event_node_name_is_declared_exactly_once() -> None:
    """C3: node_bridge flattens first-wins over unsorted os.walk, so a duplicated
    declared name is resolved by filesystem order. AST over the whole rules_engine
    package (not just this slice) proves the new name is not shadowed."""
    from common_lib.modules.governance.rules_engine.flow import reactive

    name = reactive.ReactiveFlow.process_event_node._node_metadata["name"]
    root = GOV_LIB / "rules_engine"
    declarations: list[str] = []
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts or "tests" in path.parts:
            continue
        tree = ast.parse(path.read_text())
        for n in ast.walk(tree):
            if not isinstance(n, ast.Call):
                continue
            if ast.unparse(n.func).split(".")[-1] != "node":
                continue
            for kw in n.keywords:
                if kw.arg == "name" and getattr(kw.value, "value", None) == name:
                    declarations.append(f"{path.relative_to(root)}:{n.lineno}")
    assert len(declarations) == 1, (
        f"{name} is declared {len(declarations)} times: {declarations}. "
        "A duplicate declared name is resolved by filesystem order at bridge time."
    )
    assert declarations[0].startswith("flow/reactive.py:"), (
        f"{name} is declared outside its own module: {declarations}"
    )
