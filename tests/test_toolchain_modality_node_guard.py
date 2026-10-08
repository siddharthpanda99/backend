"""Guard for the ``orchestration.Modality`` defect: an ``Enum`` advertised as a tool.

THE DEFECT
----------
``@node`` was applied directly to ``class Modality(str, Enum)`` in
``common_lib/modules/orchestration/toolchain/schemas.py``, so the catalogue
advertised ``orchestration.Modality`` as an invocable tool with
``input_schema={}`` and ``executable=True``. Six toolchain modules re-export the
name, so discovery — which dedupes on ``(name, module, qualname)`` — registered
the SAME object SIX times under the SAME name.

Invoking it through the MCP node bridge produced::

    TypeError: EnumType.__call__() missing 1 required positional argument: 'value'

That is a registry entry that lies about being callable: rule 21 ("a ``@node``
must either do the work its description promises, or fail loudly").

THE FIX
-------
Two halves, deliberately asymmetric:

* **Unconditional** — the decorator came off the Enum class. This cannot be
  flag-gated: ``test_node_catalogue_guards.py::test_no_enum_class_carries_a_node``
  asserts ZERO Enum nodes in the real registry, so a flag would only hide the
  defect from the gate meant to catch it.
* **Behind ``orchestration.toolchain.schema_nodes`` (registered OFF)** — the
  catalogue *name* is offered back, attached to a real function that returns the
  modality contract rather than being one. Reusing the name is what makes the
  change additive (rule 13): no consumer learns a new spelling, and enabling the
  flag restores discoverability without restoring the lie.

WHY A SECOND GUARD FILE
-----------------------
``test_node_catalogue_guards.py`` already fails on this, but its detector skips
every entry whose ``qualname`` contains a dot and its ``_resolve`` returns
``None`` for 252 unresolvable entries, so it cannot see an Enum reached through a
subclass. This file re-implements the sweep WITHOUT those blind spots and adds
the two things that make it failable rather than decorative:

* :func:`test_the_enum_sweep_is_not_vacuous` builds a throwaway Enum carrying
  ``@node`` and asserts the very same sweep flags it — so a future "optimisation"
  that turns the sweep into ``return []`` fails here instead of passing silently.
* :func:`test_the_flag_name_cannot_prune_another_nodes_module` proves the flag is
  inert for everything except its own node. Registering a flag under a
  path-derived candidate (``orchestration.toolchain``, say) would prune the whole
  toolchain node set; that mistake is caught here rather than in production.

MEASURED (Backend Monorepo/Backend/.venv/bin/python)
----------------------------------------------------
    discover_nodes() with the defect        : 25 756
    enum entries behind it                  : 6   (1 distinct object)
    after the fix, flag OFF (default)       : 25 750
    after the fix, flag ON                  : 25 757  (+1 entry, not +6)
    nodes with qualname == "Modality"        : 0

The +-13 band between runs is import-order dependent and predates this change;
``test_node_catalogue_guards.py``'s module docstring records the same band.
"""

from __future__ import annotations

import enum
import importlib
import inspect

import pytest

from common_lib.modules.common.feature_flags import FeatureFlagStore
from common_lib.modules.common.module_pruning import node_flag_candidates
from common_lib.modules.nodes_registry import NodeInfo, discover_nodes
from common_lib.modules.orchestration.toolchain.flags import (
    SCHEMA_NODES_FLAG,
    flag_enabled,
    reference_config_path,
    registered_flag,
)
from common_lib.modules.orchestration.toolchain.nodes import describe_modality
from common_lib.modules.orchestration.toolchain.schemas import Modality
from common_lib.modules.plugins.node import node

SCHEMAS_MODULE = "common_lib.modules.orchestration.toolchain.schemas"
NODES_MODULE = "common_lib.modules.orchestration.toolchain.nodes"


@pytest.fixture(scope="module")
def nodes():
    return discover_nodes(force=True)


# ── the sweep, with no blind spots ───────────────────────────────────────────


def resolve_target(node_info):
    """Resolve a node's underlying object, or ``None`` if genuinely unresolvable.

    Walks the longest resolvable prefix of ``qualname`` inside ``module``; if
    none resolves it also sweeps module-level classes for a matching member, so
    an Enum reachable only through a subclass is still found. Unlike
    ``test_node_catalogue_guards._resolve`` this does not skip dotted qualnames
    and does not give up silently.
    """
    try:
        module = importlib.import_module(node_info.module)
    except Exception:
        return None
    parts = (node_info.qualname or "").split(".")
    for k in range(len(parts), 0, -1):
        obj = module
        try:
            for part in parts[:k]:
                obj = getattr(obj, part)
        except AttributeError:
            continue
        return obj
    if len(parts) > 1:
        leaf = parts[-1]
        for candidate in dir(module):
            owner = getattr(module, candidate, None)
            if not inspect.isclass(owner):
                continue
            for base in inspect.getmro(owner):
                member = getattr(base, leaf, None)
                if member is not None:
                    return member
    return None


def enum_nodes_in(nodes):
    """Every registry entry whose target is an ``enum.Enum`` subclass."""
    found = []
    for n in nodes:
        obj = resolve_target(n)
        if inspect.isclass(obj) and issubclass(obj, enum.Enum):
            found.append((n.name, n.module, n.qualname))
    return found


# ── guard 1: the class survives, the decorator does not ───────────────────────


def test_modality_is_still_an_enum_with_its_members():
    """The fix dropped the decorator, never the class.

    Every ``modality=Modality.LLM`` annotation and every
    ``decision.modality in (Modality.WORKFLOW, ...)`` comparison across the
    toolchain resolves through this class.
    """
    assert inspect.isclass(Modality) and issubclass(Modality, enum.Enum)
    assert [m.name for m in Modality] == [
        "WORKFLOW",
        "TOOL",
        "AGENT",
        "SYSTEM",
        "LLM",
    ]
    assert Modality("llm") is Modality.LLM


def test_modality_is_still_importable_from_every_module_that_reexports_it():
    """The six inflated registrations were six imports of one object.

    If the decorator removal had been done by deleting the class, every one of
    these imports would raise — and discovery would silently drop ~30 toolchain
    nodes with it.
    """
    for module_name in (
        f"{SCHEMAS_MODULE}",
        "common_lib.modules.orchestration.toolchain.router",
        "common_lib.modules.orchestration.toolchain.builder",
        "common_lib.modules.orchestration.toolchain.interactive",
        "common_lib.modules.orchestration.toolchain.agent.planner",
        "common_lib.modules.orchestration.toolchain.agent.executor",
    ):
        module = importlib.import_module(module_name)
        assert getattr(module, "Modality", None) is Modality, module_name


def test_modality_carries_no_node_marker():
    """The defect itself: the Enum no longer advertises itself as a tool."""
    assert getattr(Modality, "_is_plugin_node", False) is False
    assert not hasattr(Modality, "_node_metadata")


# ── guard 2: no Enum is advertised, anywhere, by ANY spelling ────────────────


def test_no_registry_node_resolves_to_an_enum(nodes):
    """The blast radius, re-measured from the real registry on every run."""
    offenders = enum_nodes_in(nodes)
    assert not offenders, (
        f"{len(offenders)} Enum class(es) are advertised as callable nodes; an Enum "
        f"is a type tag, not a tool: {offenders[:10]}"
    )


def test_the_enum_sweep_is_not_vacuous():
    """Prove guard 2 can fail, by running it against a known offender.

    Without this, ``enum_nodes_in`` could degenerate into ``return []`` and guard
    2 would pass forever — the exact shape of the ten unfailable gates already
    found in this project. The synthetic Enum below is decorated in-process and
    never touches the registry or the filesystem.
    """
    from common_lib.modules.plugins.node import node as node_decorator

    @node_decorator(
        name="test_only.SyntheticOffender",
        description="An Enum pretending to be a tool.",
        category="test_only",
        tags=["test_only"],
        audience=["executor"],
    )
    class SyntheticOffender(str, enum.Enum):
        ONE = "one"

    class FakeInfo:
        name = "test_only.SyntheticOffender"
        module = __name__
        qualname = "SyntheticOffender"

    # The synthetic class must be reachable from THIS module for resolve_target
    # to find it, which is why the sweep is fed a real module path.
    globals()["SyntheticOffender"] = SyntheticOffender
    assert enum_nodes_in([FakeInfo()]) == [
        ("test_only.SyntheticOffender", __name__, "SyntheticOffender")
    ]
    del globals()["SyntheticOffender"]

    # And the same sweep must be silent on a decorated *function*, so the
    # assertion above discriminates on class-kind rather than reporting every
    # decorated thing in existence.
    @node_decorator(
        name="test_only.SyntheticCallable",
        description="An ordinary callable, which is what a node is supposed to be.",
        category="test_only",
        tags=["test_only"],
        audience=["executor"],
    )
    def synthetic_callable():
        return "fine"

    class CallableInfo:
        name = "test_only.SyntheticCallable"
        module = __name__
        qualname = "synthetic_callable"

    globals()["synthetic_callable"] = synthetic_callable
    assert enum_nodes_in([CallableInfo()]) == []
    del globals()["synthetic_callable"]


def test_no_node_advertises_the_bare_qualname_modality(nodes):
    """Named regression on the exact inflation shape that was fixed.

    The six entries all carried ``qualname == "Modality"`` with no owner, which
    is the signature of a class-level decorator seen through a re-export.
    """
    bare = [(n.name, n.module, n.qualname) for n in nodes if n.qualname == "Modality"]
    assert bare == [], f"a bare 'Modality' qualname is back in the catalogue: {bare}"


# ── guard 3: the flag is registered OFF, and inert for anything else ──────────


def test_flag_is_registered_off_in_the_reference_json():
    """Assert REGISTRATION, not the resolved value.

    ``common.feature_flags.is_enabled`` returns ``True`` for a key nobody
    registered, so a value assertion cannot tell "registered and off" from
    "never existed". ``registered_flag`` reads the shipped JSON and returns
    ``None`` when absent, which is the distinction this needs.
    """
    assert reference_config_path() is not None, "reference JSON not found"
    assert registered_flag(SCHEMA_NODES_FLAG) is False, (
        f"{SCHEMA_NODES_FLAG} must be registered with enabled=false in "
        f"resources/feature_flags.reference.json"
    )
    assert flag_enabled(SCHEMA_NODES_FLAG, default=True) is False


def test_the_flag_name_cannot_prune_another_nodes_module(flag_on):
    """A flag name is also a pruning candidate for anything beneath it.

    Discovery derives candidates as ``<module path>.<leaf>`` plus every ancestor,
    so registering ``orchestration.toolchain`` — or ``orchestration`` — at
    ``False`` would silently delete the entire toolchain node set.

    The sweep runs with the flag **ON** on purpose. With it off, a
    path-derived flag name prunes its own collateral out of the registry, and
    the scan finds nothing to complain about — the assertion would pass for
    exactly the mistake it exists to catch. (Verified: that is how the first
    version of this test survived mutant 6.)
    """
    assert flag_on.is_enabled(SCHEMA_NODES_FLAG) is True, "precondition"
    collateral = sorted(
        (n.module, n.qualname)
        for n in discover_nodes()
        if SCHEMA_NODES_FLAG in node_flag_candidates(n)
    )
    assert collateral == [
        ("common_lib.modules.orchestration.toolchain.nodes", "describe_modality")
    ], (
        f"{SCHEMA_NODES_FLAG} is a pruning candidate for nodes other than its own, "
        f"so switching it off would prune them too: {collateral}"
    )

    # And the flag must target describe_modality ALONE — an explicit
    # ``feature_flag=`` suppresses the path-derived candidates, so this is the
    # only reason the entry above is empty. If that suppression ever stops
    # working, ``orchestration.toolchain`` becomes a candidate and 109 toolchain
    # nodes vanish on a default install.
    mine = NodeInfo(
        name=describe_modality._node_metadata["name"],
        module=NODES_MODULE,
        qualname="describe_modality",
        feature_flag=describe_modality._node_metadata["metadata"]["feature_flag"],
    )
    assert node_flag_candidates(mine) == [SCHEMA_NODES_FLAG], (
        f"describe_modality's candidates are {node_flag_candidates(mine)}; the "
        f"explicit flag must be used alone or the toolchain set is at risk"
    )


# ── guard 4: both flag states behave, and the node is real when visible ──────


def test_modality_name_is_absent_from_the_catalogue_by_default(nodes):
    """Default install: the name is not advertised, and nothing lies under it."""
    assert [n.name for n in nodes if n.name == "orchestration.Modality"] == []


def test_the_replacement_node_is_a_function_that_returns_real_data():
    """Rule 21, checked on the replacement: it must deliver what it promises.

    Importable and callable regardless of the flag — pruning governs what the
    catalogue advertises, not what the platform can do.
    """
    assert inspect.isfunction(describe_modality)
    contract = describe_modality()
    assert contract["members"] == ["workflow", "tool", "agent", "system", "llm"]
    assert contract["valid"] is True and contract["modality"] is None
    assert describe_modality("AGENT")["modality"] == "agent"
    assert describe_modality("nope")["valid"] is False
    assert describe_modality("nope")["modality"] is None


@pytest.fixture
def flag_on():
    """Turn the flag on for one test and restore the store exactly.

    Restored by popping the two dict entries the store mutated — NOT by
    ``invalidate_cache()``, which drops the whole singleton and would also revert
    any ``set_enabled(persist=False)`` another test made.
    """
    store = FeatureFlagStore()
    overrides, file_cache = store._overrides, store._file_cache
    had = (SCHEMA_NODES_FLAG in overrides, SCHEMA_NODES_FLAG in file_cache)
    before = (overrides.get(SCHEMA_NODES_FLAG), file_cache.get(SCHEMA_NODES_FLAG))
    store.set_enabled(SCHEMA_NODES_FLAG, True, persist=False)
    try:
        yield store
    finally:
        for mapping, present, value in (
            (overrides, had[0], before[0]),
            (file_cache, had[1], before[1]),
        ):
            if present:
                mapping[SCHEMA_NODES_FLAG] = value
            else:
                mapping.pop(SCHEMA_NODES_FLAG, None)


def test_enabling_the_flag_advertises_exactly_one_invocable_entry(flag_on):
    """ON: the name returns, but as one real function — not six Enums.

    The original defect registered the same object six times because six modules
    re-export it. ``describe_modality`` lives in ``nodes.py`` and is deliberately
    not re-exported, so the count must be exactly 1.
    """
    visible = [n for n in discover_nodes() if n.name == "orchestration.Modality"]
    assert len(visible) == 1, (
        f"expected exactly one entry, got {[(n.module, n.qualname) for n in visible]}"
    )
    entry = visible[0]
    assert entry.module == NODES_MODULE
    assert entry.qualname == "describe_modality"
    assert entry.executable is True

    module = importlib.import_module(entry.module)
    target = resolve_target(entry)
    assert target is describe_modality
    assert not inspect.isclass(target), "the replacement must not be a class"
    # The thing the bridge would actually invoke must succeed.
    assert module.describe_modality()["members"]


def test_the_flag_off_state_hides_only_the_replacement(nodes):
    """OFF must cost exactly one entry, never a neighbour.

    Guards the reverse mistake: a flag name that collides with a derived
    candidate would delete the whole toolchain set at import time.
    """
    toolchain = [
        n
        for n in nodes
        if n.module.startswith("common_lib.modules.orchestration.toolchain")
    ]
    assert len(toolchain) == 109, (
        f"toolchain lost nodes while the flag was off: {len(toolchain)} (expected 109)"
    )
    for required in (
        "orchestration.ToolchainBuilder",
        "orchestration.ToolchainRouter",
        "orchestration.ToolchainTask",
        "toolchain.plan",
        "toolchain.execute_task",
    ):
        assert required in {n.name for n in toolchain}, required
