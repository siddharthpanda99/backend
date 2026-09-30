"""Regression tests for the rules_engine slice audit (core/execution/
resilience/data/lifecycle/foundation/observability half).

Each test pins a defect that was actually measured, so a future refactor that
reintroduces it fails here rather than in production:

1. The 14 phantom ``input_schema`` keys that made 10 MCP tools silently fail to
   register.
2. The 40-line dead ``apply_mixin`` that shadowed the live one.
3. The new gated wrappers — including the shared-registry defect the first
   draft of that file shipped with.
"""

from __future__ import annotations

import ast
import pathlib
import re
from typing import Any

import pytest


def _rules_engine_dir() -> pathlib.Path:
    """Locate the rules_engine package from the import, not from __file__.

    The Backend venv resolves common_lib as an installed/editable package that
    does not live under Backend/app/, so counting parents off this test file
    walks the wrong tree. Asking the import system is exact.
    """
    import common_lib.modules.governance.rules_engine as pkg

    return pathlib.Path(pkg.__file__).resolve().parent


RULES_ENGINE = _rules_engine_dir()

#: Subpackages this agent owns. The sibling half (nodes/, definition/,
#: expression/, flow/, policy/, conditions/, intelligence/, temporal/) is
#: deliberately excluded.
OWNED = (
    "core",
    "execution",
    "resilience",
    "data",
    "lifecycle",
    "foundation",
    "observability",
)


def _node_decorators(tree: ast.AST) -> list[ast.Call]:
    """Every `@node(...)` decorator call in a parsed tree.

    `ast.walk` also yields the Module, which has no `decorator_list`, so the
    attribute has to be filtered rather than assumed.
    """
    return [
        dec
        for node in ast.walk(tree)
        for dec in getattr(node, "decorator_list", [])
        if ast.unparse(dec).startswith("node")
    ]


def _owned_files() -> list[pathlib.Path]:
    out: list[pathlib.Path] = []
    for sub in OWNED:
        out += sorted(
            p
            for p in (RULES_ENGINE / sub).rglob("*.py")
            if "__pycache__" not in str(p) and "tests" not in p.parts
        )
    for name in (
        "integration_adapter.py",
        "evaluator.py",
        "registry.py",
        "slice_nodes.py",
    ):
        f = RULES_ENGINE / name
        if f.exists():
            out.append(f)
    return out


# ---------------------------------------------------------------------------
# 1. Phantom input_schema keys
# ---------------------------------------------------------------------------

#: A schema key must be a usable Python identifier. `node_bridge._build_handler`
#: exec()s `def _handler(<key>: <type>)`, so a key like "Any]" raises SyntaxError
#: and the tool is dropped from MCP with only a log line. The real parameter is
#: always present alongside, which is why these could simply be deleted.
PHANTOM_KEY = re.compile(r"[\[\]]")


def test_no_phantom_keys_in_owned_input_schemas() -> None:
    """No owned @node declares a schema key containing a bracket.

    10 such nodes were measured failing to build an MCP handler, e.g.
    ``Failed to build handler for rules_engine.add_handler: closing
    parenthesis ']' does not match opening parenthesis '('``.
    """
    offenders: list[str] = []
    for path in _owned_files():
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not isinstance(
                node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
            ):
                continue
            for dec in node.decorator_list:
                if not ast.unparse(dec).startswith("node"):
                    continue
                for kw in dec.keywords:
                    if kw.arg not in ("input_schema", "output_schema"):
                        continue
                    if not isinstance(kw.value, ast.Dict):
                        continue
                    for key in kw.value.keys:
                        name = (
                            ast.literal_eval(key)
                            if isinstance(key, ast.Constant)
                            else None
                        )
                        if isinstance(name, str) and PHANTOM_KEY.search(name):
                            rel = path.relative_to(RULES_ENGINE)
                            offenders.append(
                                f"{rel}:{node.lineno} {ast.unparse(dec)[:40]} key={name!r}"
                            )
    assert not offenders, "phantom schema keys reintroduced:\n" + "\n".join(offenders)


def test_owned_nodes_all_build_an_mcp_handler() -> None:
    """Every owned node that resolves must produce a working MCP handler.

    Before the fix this was 446 built / 10 dropped. Import of the bridge is
    lazy and app-wide, so a failure here is reported as a skip rather than
    masking the assertion above.
    """
    from app.mcp.node_bridge import _build_handler
    from common_lib.modules.nodes_registry import discover_nodes_in_package

    prefix = "common_lib.modules.governance.rules_engine"

    def owned(node: Any) -> bool:
        mod = node.module or ""
        if not mod.startswith(prefix):
            return False
        tail = mod[len(prefix) :].lstrip(".")
        if tail == "":
            return True
        return any(tail == s or tail.startswith(s + ".") for s in OWNED) or tail in (
            "integration_adapter",
            "evaluator",
            "registry",
            "slice_nodes",
        )

    nodes = [
        n for n in discover_nodes_in_package("governance.rules_engine") if owned(n)
    ]
    assert nodes, "no owned nodes discovered — discovery is broken, not the code"
    failed = [
        f"{n.name} ({n.module}.{n.qualname})"
        for n in nodes
        if _build_handler(n) is None
    ]
    assert not failed, f"nodes that cannot become MCP tools: {failed}"


# ---------------------------------------------------------------------------
# 2. Dead apply_mixin
# ---------------------------------------------------------------------------


def test_apply_mixin_is_defined_exactly_once() -> None:
    """One class, one `apply_mixin`.

    Two definitions in one class body meant the second silently overwrote the
    first, leaving 40 lines of unreachable RuleVersion-based code that still
    ran its @node decorator and registered a duplicate
    ``rules_engine.apply_mixin`` tool against dead code.
    """
    from common_lib.modules.governance.rules_engine.lifecycle.composition import (
        RuleCompositionEngine,
    )

    src = (RULES_ENGINE / "lifecycle" / "composition.py").read_text()
    tree = ast.parse(src)
    for cls in tree.body:
        if isinstance(cls, ast.ClassDef) and cls.name == "RuleCompositionEngine":
            names = [n.name for n in cls.body if isinstance(n, ast.FunctionDef)]
            assert names.count("apply_mixin") == 1, (
                f"apply_mixin defined {names.count('apply_mixin')}x in RuleCompositionEngine"
            )
            return
    pytest.fail("RuleCompositionEngine class body not found")


def test_apply_mixin_has_no_duplicate_node_registration() -> None:
    """`rules_engine.apply_mixin` must be declared by exactly one @node."""
    src = (RULES_ENGINE / "lifecycle" / "composition.py").read_text()
    tree = ast.parse(src)
    declared: list[int] = []
    for dec in _node_decorators(tree):
        for kw in dec.keywords:
            if (
                kw.arg == "name"
                and ast.literal_eval(kw.value) == "rules_engine.apply_mixin"
            ):
                declared.append(1)
    assert len(declared) == 1, f"rules_engine.apply_mixin declared {len(declared)}x"


# ---------------------------------------------------------------------------
# 3. The gated wrappers
# ---------------------------------------------------------------------------


@pytest.fixture
def slice_nodes_on(monkeypatch: pytest.MonkeyPatch) -> Any:
    from common_lib.modules.governance.rules_engine import slice_nodes

    monkeypatch.setenv(slice_nodes.ENV_FLAG, "1")
    return slice_nodes


def test_slice_nodes_flag_is_default_off() -> None:
    """G9: new behaviour must not be live by default."""
    from common_lib.modules.governance.rules_engine import slice_nodes

    assert slice_nodes.is_slice_nodes_enabled() is False
    assert slice_nodes.ENV_FLAG == "GOVERNANCE_RULES_ENGINE_SLICE_NODES"


def test_every_wrapper_is_inert_while_the_gate_is_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With the flag off every wrapper must decline, not silently succeed.

    This is the "silent no-op" failure mode: a wrapper that returned an empty
    success payload would read to an agent as "there is nothing here".
    """
    monkeypatch.delenv("GOVERNANCE_RULES_ENGINE_SLICE_NODES", raising=False)
    from common_lib.modules.governance.rules_engine import slice_nodes as S

    calls = {
        "evaluate_rule_definitions": ({"a": 1},),
        "register_rule_definition": ("r",),
        "latest_rule_definition": ("r",),
        "explain_decision": ({},),
        "rule_from_rdl_dict": ({},),
        "process_unified_event": ("custom", {}),
        "rules_integration_components": (),
    }
    for name, args in calls.items():
        out = getattr(S, name)(*args)
        assert out["enabled"] is False, f"{name} acted with the gate off: {out}"
        assert out["operation"] == name
        assert out["flag"] == S.FLAG_NAME


def test_register_then_latest_shares_one_registry(slice_nodes_on: Any) -> None:
    """register -> latest must agree.

    The first draft of slice_nodes.py built a fresh `RulesRegistry()` per call,
    so `register` wrote into a throwaway and `latest` read a different one and
    always reported `found: False` — the write and the read silently looked at
    different objects.
    """
    S = slice_nodes_on
    rid = "test_shared_registry"
    written = S.register_rule_definition(rid, when={"t": 1}, then={"set": {"x": 1}})
    assert written["rule_id"] == rid
    assert written["version"] == 1

    read = S.latest_rule_definition(rid)
    assert read["found"] is True, f"register then latest disagreed: {read}"
    assert read["rule"]["rule_id"] == rid
    assert read["rule"]["when"] == {"t": 1}

    # A second register appends a version rather than replacing the rule.
    again = S.register_rule_definition(rid, when={"t": 2}, then={})
    assert again["version"] == 2
    assert S.latest_rule_definition(rid)["rule"]["version"] == 2


def test_latest_reports_absent_rather_than_empty(slice_nodes_on: Any) -> None:
    """`found: False` must be distinguishable from an empty registry."""
    out = slice_nodes_on.latest_rule_definition("definitely_not_registered_xyz")
    assert out["found"] is False
    assert out["rule"] is None


def test_evaluate_reports_match_and_derived_facts(slice_nodes_on: Any) -> None:
    S = slice_nodes_on
    rid = "test_eval"
    S.register_rule_definition(rid, when={"tier": "gold"}, then={"set": {"vip": True}})

    hit = S.evaluate_rule_definitions({"tier": "gold"})
    evals = {e["rule_id"]: e for e in hit["evaluations"]}
    assert evals[rid]["matched"] is True
    assert evals[rid]["derived"] == {"vip": True}

    miss = S.evaluate_rule_definitions({"tier": "bronze"})
    evals = {e["rule_id"]: e for e in miss["evaluations"]}
    assert evals[rid]["matched"] is False
    assert evals[rid]["derived"] == {}


def test_evaluate_reports_an_unknown_rule_id(slice_nodes_on: Any) -> None:
    """A bad rule_id must be an explicit error, not an empty result set."""
    out = slice_nodes_on.evaluate_rule_definitions({}, ["no_such_rule_zzz"])
    assert "error" in out, f"unknown rule_id reported as success: {out}"


def test_rule_from_rdl_dict_applies_defaults(slice_nodes_on: Any) -> None:
    rule = slice_nodes_on.rule_from_rdl_dict({"name": "r"})["rule"]
    assert rule["name"] == "r"
    assert rule["status"] == "draft"
    assert rule["type"] == "conditional"
    assert rule["priority"] == 100
    assert rule["id"]  # generated, not empty


def test_explain_decision_advertises_that_it_is_a_stub(slice_nodes_on: Any) -> None:
    """ExplainabilityEngine returns a constant; the node must not imply
    otherwise (silent-success trap)."""
    out = slice_nodes_on.explain_decision({"anything": 1})
    assert out["stub"] is True
    assert isinstance(out["explanation"], str)


def test_process_unified_event_returns_a_dict(slice_nodes_on: Any) -> None:
    """The declared output_schema says dict; IntegrationContext is a plain
    dataclass so it needs asdict(), not model_dump()."""
    out = slice_nodes_on.process_unified_event("custom", {"id": "evt_test_1"})
    assert out["available"] is True
    assert isinstance(out["context"], dict)
    assert out["context"]["event_id"] == "evt_test_1"


def test_process_unified_event_rejects_a_bad_event_type(slice_nodes_on: Any) -> None:
    out = slice_nodes_on.process_unified_event("not_a_real_event_type", {})
    assert out.get("available") is False
    assert "error" in out


def test_rules_integration_components_reports_each_component(
    slice_nodes_on: Any,
) -> None:
    out = slice_nodes_on.rules_integration_components()
    assert out["available"] is True
    assert set(out["components"]) == {"rules_engine", "rules_registry", "policy_engine"}
    for label, entry in out["components"].items():
        assert "resolved" in entry, f"{label} did not report resolution state"


# ---------------------------------------------------------------------------
# 4. Subpackage __init__ exports
# ---------------------------------------------------------------------------


def test_owned_subpackages_are_importable_and_import_star_works() -> None:
    """Each owned subpackage must import, and `import *` must not raise.

    Measured before the fix: 31 names sat in `__all__` without a matching
    import, 30 of which do not exist anywhere in the package, so
    `from ... import *` raised AttributeError and a consumer asking for a
    symbol that *was* implemented (`Cache`, `RuleResultCache`, `BranchResult`,
    `KnowledgeBaseEngine`, `CircuitOpenError`, ...) got ImportError. That left
    54 tests in this slice un-collectable.
    """
    import importlib

    for pkg in OWNED:
        mod_name = f"common_lib.modules.governance.rules_engine.{pkg}"
        mod = importlib.import_module(mod_name)
        assert getattr(mod, "__all__", None), f"{pkg} has no __all__"
        namespace: dict[str, object] = {}
        exec(f"from {mod_name} import *", namespace)  # noqa: S102 - the point of the test
        undeclared = [n for n in mod.__all__ if not hasattr(mod, n)]
        assert not undeclared, f"{pkg}.__all__ advertises unbound names: {undeclared}"


def test_unimplemented_exports_are_recorded_not_advertised() -> None:
    """A name in `__all__` that does not exist is a lie in both directions:
    it breaks `import *` and misleads a reader. It must be recorded in
    NOT_IMPLEMENTED instead."""
    import importlib

    for pkg in OWNED:
        mod = importlib.import_module(
            f"common_lib.modules.governance.rules_engine.{pkg}"
        )
        recorded = set(getattr(mod, "NOT_IMPLEMENTED", ()))
        assert not (recorded & set(mod.__all__)), (
            f"{pkg}: {recorded & set(mod.__all__)} is both advertised and recorded"
        )
        for name in recorded:
            assert not hasattr(mod, name), (
                f"{pkg}.{name} is recorded as unimplemented but is importable"
            )


def test_previously_unimportable_symbols_now_resolve() -> None:
    """The exact symbols the 54 dead tests were asking for."""
    import importlib

    expected = {
        "observability": ["Cache", "RuleResultCache", "AuditCategory", "AuditQuery"],
        "execution": [
            "BranchResult",
            "ParallelTask",
            "get_hybrid_engine",
            "get_parallel_engine",
            "ResourceQuota",
            "SandboxResult",
        ],
        "data": ["KnowledgeBaseEngine"],
        "resilience": ["CircuitOpenError"],
    }
    for pkg, names in expected.items():
        mod = importlib.import_module(
            f"common_lib.modules.governance.rules_engine.{pkg}"
        )
        for name in names:
            assert hasattr(mod, name), f"{pkg}.{name} still not importable"


def test_slice_node_names_are_unique_within_the_file() -> None:
    """72 duplicate @node names already exist in this package; the new file
    must not add to them."""
    tree = ast.parse((RULES_ENGINE / "slice_nodes.py").read_text())
    names = [
        ast.literal_eval(kw.value)
        for dec in _node_decorators(tree)
        for kw in dec.keywords
        if kw.arg == "name"
    ]
    assert len(names) == len(set(names)), f"duplicate names in slice_nodes: {names}"
    assert len(names) == 7, f"expected 7 wrappers, found {len(names)}"
