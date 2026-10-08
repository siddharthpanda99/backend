"""Guards for the ``_SKIP_MODULE_SUBSTRINGS`` over-match and the Enum it masked.

THE DEFECT THAT MATTERED
------------------------
``common_lib.modules.nodes_registry`` exempts CUDA-importing modules from
import-time discovery. Every entry was matched with a bare substring test::

    if any(s in mod_dot for s in _SKIP_MODULE_SUBSTRINGS):   # nodes_registry/__init__.py:367

so the entry ``image_processing.nodes`` — written to protect ``image_processing/nodes/``
— also matched ``image_processing.nodes_registry.schema``, which is a DIFFERENT
package that imports nothing heavy. A skip-list rule written to *protect* the enum
guard silently *disabled* it for a whole package, and a real violation lived
inside: ``@node`` applied directly to ``class NodeDataType(str, Enum)`` at
``image_processing/nodes_registry/schema.py:27``.

``NodeDataType`` was therefore never in the registry, so
``test_node_catalogue_guards.py::test_no_enum_class_carries_a_node`` reported a
clean pass over a tree that contained the defect. An exemption list that over-matches
is not a performance optimisation; it is a hole in whatever rule it overlaps.

THE SAME OVER-MATCH HAPPENED TWICE
----------------------------------
Enumerated across all 3 785 discoverable paths (see ``test_the_over_match_is_exactly_five_paths``):

* ``image_processing.nodes_registry.{discovery,introspector,schema,sync}`` — 4 modules,
  masked by the ``image_processing.nodes`` entry over-matching the ``nodes_registry``
  segment. **One of them hid a live violation.** (5th: the ``nodes.py`` this branch
  adds would have been masked the same way.)
* ``workflows.standard.nodes.comfyui_wrapper`` — masked by the
  ``workflows.standard.nodes.comfyui`` entry over-matching the ``comfyui_wrapper``
  segment. Hides no violation, but 7 catalogue entries were invisible because of it.

THE FIX
-------
* **Unconditional** — ``@node`` came off ``NodeDataType``. It cannot be flag-gated:
  the enum guard asserts ZERO Enum nodes, so a flag would only hide the defect from
  the gate meant to catch it.
* **Behind ``image_processing.nodes_registry.schema_nodes`` (registered OFF)** — the
  catalogue *name* comes back attached to ``describe_node_data_type``, a real function
  returning the data-type contract. The exact name is reused, so nothing is renamed
  (rule 13) and no consumer learns a new spelling.
* **The predicate** — skip-list entries are now matched as dotted path SEGMENTS
  (``nodes_registry._skip_prefix_for``), so an entry names a module and its ancestors
  and nothing else.

WHY A SECOND GUARD FILE
-----------------------
``test_node_catalogue_guards.py`` already fails on the Enum, but nothing pinned the
*exemption predicate*, so the substring match could return silently and re-mask a
future package. The three tests that matter here are the ones that make that
impossible:

* :func:`test_the_over_match_is_exactly_five_paths` pins the exact blast radius.
* :func:`test_a_substring_entry_must_not_exempt_a_longer_segment` re-derives the old
  predicate and asserts the two disagree on ``nodes_registry`` — so the fix cannot be
  reverted to a substring match while leaving this file green.
* :func:`test_the_segment_sweep_is_not_vacuous` builds a throwaway module whose name
  the skip-list WOULD exempt and asserts discovery honours it, so a "simplification"
  to no predicate at all also fails here.

MEASURED (Backend Monorepo/Backend/.venv/bin/python, this branch)
-----------------------------------------------------------------
    discoverable paths                       : 3 785
    exemptions, unchanged by the predicate   : 3 779
    exemptions, CORRECTED by the predicate   : 6   (5 pre-existing + this branch's nodes.py)
    paths newly exempted (regression)        : 0
    image_processing.nodes_registry entries  : 0 -> 43   (flag OFF)
    image_processing.NodeDataType            : absent (flag OFF) / 1 function (flag ON)
"""

from __future__ import annotations

import enum
import importlib
import inspect
from pathlib import Path

import pytest

from common_lib.modules.common.feature_flags import FeatureFlagStore
from common_lib.modules.common.module_pruning import (
    _module_flag_candidates,
    node_flag_candidates,
)
from common_lib.modules.image_processing.nodes_registry.flags import (
    SCHEMA_NODES_FLAG,
    reference_config_path,
    registered_flag,
)
from common_lib.modules.image_processing.nodes_registry.nodes import (
    describe_node_data_type,
)
from common_lib.modules.image_processing.nodes_registry.schema import NodeDataType
from common_lib.modules.nodes_registry import (
    _MODULES_ROOT,
    _SKIP_MODULE_PREFIXES,
    _path_to_module,
    _scan_module_paths,
    _skip_prefix_for,
    discover_nodes,
)

SCHEMA_MODULE = "common_lib.modules.image_processing.nodes_registry.schema"
NODES_MODULE = "common_lib.modules.image_processing.nodes_registry.nodes"
TARGET = "image_processing.NodeDataType"

#: The six paths the substring predicate over-exempted. Pinned deliberately: a
#: future edit that changes the blast radius must change this list too, loudly.
#: ``nodes_registry.nodes`` is in this list because it is this branch's own new
#: file -- the old predicate would have masked the replacement node too, which is
#: the clearest possible demonstration that the over-match is not about any one
#: package.
OVER_MATCHED = {
    "common_lib.modules.image_processing.nodes_registry.discovery",
    "common_lib.modules.image_processing.nodes_registry.introspector",
    "common_lib.modules.image_processing.nodes_registry.nodes",
    "common_lib.modules.image_processing.nodes_registry.schema",
    "common_lib.modules.image_processing.nodes_registry.sync",
    "common_lib.modules.workflows.standard.nodes.comfyui_wrapper",
}


def _old_substring_hit(mod_dot: str) -> str | None:
    """The predicate this branch replaced, kept verbatim as a control.

    ``nodes_registry/__init__.py`` used exactly this. It is retained so the tests
    can assert the OLD behaviour still over-matches — proving the fix changed the
    predicate rather than the exemption list.
    """
    return next((s for s in _SKIP_MODULE_PREFIXES if s in mod_dot), None)


@pytest.fixture(scope="module")
def nodes():
    return discover_nodes(force=True)


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


# ── 1. the skip-list predicate ───────────────────────────────────────────────


def test_a_substring_entry_must_not_exempt_a_longer_segment():
    """The core regression: ``nodes`` must not exempt ``nodes_registry``.

    This is the assertion that makes the fix unfakeable. If the predicate is ever
    reverted to a substring match, ``_skip_prefix_for`` returns a string again and
    this fails — even if every other test in the file is untouched.
    """
    assert _old_substring_hit(SCHEMA_MODULE) == "image_processing.nodes", (
        "control broken: the old substring predicate is expected to over-match here. "
        "If this fails the historical defect cannot be reproduced, so the rest of "
        "this file no longer proves anything about it."
    )
    assert _skip_prefix_for(SCHEMA_MODULE) is None, (
        f"{SCHEMA_MODULE!r} must NOT be exempt from discovery: it is a different "
        "package from image_processing.nodes and imports nothing heavy. Exempting "
        "it hides whatever its @node declarations are from every registry guard."
    )


def test_the_over_match_is_exactly_five_paths():
    """Pin the blast radius: 6 paths over-exempted, 0 newly exempted.

    Enumerated from the real ``_scan_module_paths()`` rather than hardcoded, so a
    new skip-list entry that over-matches fails here instead of quietly widening
    the hole.
    """
    over, regressed = [], []
    for path in _scan_module_paths():
        mod_dot = _path_to_module(path)
        if not mod_dot:
            continue
        old, new = _old_substring_hit(mod_dot), _skip_prefix_for(mod_dot)
        if old == new:
            continue
        if new is None:
            over.append(mod_dot)
        else:
            regressed.append((mod_dot, new))

    assert sorted(over) == sorted(OVER_MATCHED), (
        "the set of over-matched paths changed; update OVER_MATCHED with the "
        f"measured value and re-check whether a violation is hidden in the new ones"
    )
    assert regressed == [], (
        "the predicate newly EXEMPTED paths it previously discovered: "
        f"{regressed}. That is a regression -- discovery lost nodes it used to have."
    )


@pytest.mark.parametrize(
    ("prefix", "child"),
    [
        ("image_processing.nodes", "image_processing.nodes_registry.schema"),
        (
            "workflows.standard.nodes.comfyui",
            "workflows.standard.nodes.comfyui_wrapper",
        ),
        ("security.pii.presidio_analyzer", "security.pii.presidio_analyzer_v2"),
    ],
)
def test_a_prefix_exempts_exactly_itself_and_its_descendants(prefix, child):
    """A segment matches itself and deeper paths, and nothing with a longer segment."""
    assert _skip_prefix_for(f"common_lib.modules.{prefix}") == prefix
    assert _skip_prefix_for(f"common_lib.modules.{prefix}.deep.module") == prefix
    assert _skip_prefix_for(f"common_lib.modules.{child}") is None, (
        f"{child!r} shares a prefix with the skip-list entry {prefix!r} but is a "
        "different package; matching it is the bug this test exists to prevent"
    )


def test_the_absolute_prefix_is_not_matched_against_the_relative_entry():
    """The entry is relative; matching must happen on the relative form.

    Guards the strip step: without it, an entry whose first segment coincides with
    a leading absolute segment would match for the wrong reason.
    """
    assert _skip_prefix_for("modules.image_processing.nodes.x") is None
    assert _skip_prefix_for("image_processing.nodes.x") == "image_processing.nodes"


def test_intended_exemptions_are_untouched():
    """The heavy-import exemptions must still hold, or discovery gets expensive.

    A segment-prefix fix that also stopped exempting ``image_processing/nodes/``
    would pull CUDA-scale imports into server boot. That is the failure mode this
    test exists to catch, and it is invisible to every other assertion here.
    """
    for expected in _SKIP_MODULE_PREFIXES:
        assert _skip_prefix_for(f"common_lib.modules.{expected}") == expected, (
            f"{expected!r} is no longer exempt from discovery; it imports "
            "torch/CUDA-scale deps and would be imported at server boot"
        )


def test_the_segment_sweep_is_not_vacuous():
    """Discovery must STILL honour an exemption -- the fix is not "exempt nothing".

    Without this, deleting the skip-list entirely would pass every other test here.
    """
    exempt = [
        p
        for p in _scan_module_paths()
        if _path_to_module(p).endswith("image_processing.nodes.sota.sota_nodes")
    ]
    assert exempt, "precondition: the heavy sota module must be a scan candidate"
    assert (
        _skip_prefix_for("common_lib.modules.image_processing.nodes.sota.sota_nodes")
        == "image_processing.nodes"
    )


# ── 2. the Enum itself ───────────────────────────────────────────────────────


def test_the_enum_carries_no_node_marker():
    """``NodeDataType`` must stay a working Enum AND stop being a catalogue entry.

    The class body is untouched: it still coerces, still has all 28 members. Only
    the decorator moved, which is why removing it breaks no code reference.
    """
    assert issubclass(NodeDataType, enum.Enum)
    assert len(list(NodeDataType)) == 28
    assert NodeDataType("IMAGE") is NodeDataType.IMAGE
    assert getattr(NodeDataType, "_is_plugin_node", False) is False, (
        "NodeDataType still carries @node. An Enum advertised with input_schema={} "
        "raises TypeError: EnumType.__call__() missing 1 required positional "
        "argument: 'value' when the MCP bridge invokes it."
    )


def test_the_masked_module_is_now_discovered(nodes):
    """The package the over-match hid must be in the real registry.

    This is the guard that was silently switched off. If the predicate regresses,
    the count goes to 0 and this fails.
    """
    modules = {
        n.module
        for n in nodes
        if (n.module or "").startswith(
            "common_lib.modules.image_processing.nodes_registry."
        )
    }
    assert modules >= {
        "common_lib.modules.image_processing.nodes_registry.schema",
        "common_lib.modules.image_processing.nodes_registry.discovery",
        "common_lib.modules.image_processing.nodes_registry.introspector",
        "common_lib.modules.image_processing.nodes_registry.sync",
    }, (
        "image_processing/nodes_registry/ is not reaching the registry. Either the "
        "skip-list is exempting it again, or these modules now fail to import -- "
        "both leave the same hole the over-match did."
    )
    assert (
        len(
            [
                n
                for n in nodes
                if (n.module or "").startswith(
                    "common_lib.modules.image_processing.nodes_registry."
                )
            ]
        )
        == 43
    ), "the nodes_registry contribution changed; re-measure and re-pin"


def test_no_enum_anywhere_in_the_registry_carries_a_node(nodes):
    """The invariant the over-match was hiding, asserted over ALL entries.

    Broader than ``test_node_catalogue_guards.py``'s version on purpose: this one
    does not skip dotted qualnames, because an Enum reached through a module whose
    module/qualname pair is inconsistent is exactly how this defect escaped.
    """
    offenders = []
    for n in nodes:
        try:
            module = importlib.import_module(n.module)
        except Exception:
            continue
        obj = module
        for part in (n.qualname or "").split("."):
            obj = getattr(obj, part, None)
            if obj is None:
                break
        if inspect.isclass(obj) and issubclass(obj, enum.Enum):
            offenders.append((n.name, n.module, n.qualname))
    assert not offenders, (
        f"{len(offenders)} Enum class(es) are advertised as callable tools: {offenders}"
    )


# ── 3. the replacement node ──────────────────────────────────────────────────


def test_the_replacement_node_is_a_function_that_returns_real_data():
    """Rule 21 on the replacement: it delivers what it promises, or fails loudly."""
    assert inspect.isfunction(describe_node_data_type)
    contract = describe_node_data_type()
    assert contract["members"] == [m.value for m in NodeDataType]
    assert len(contract["members"]) == 28
    assert contract["valid"] is True and contract["data_type"] is None
    assert describe_node_data_type("mask")["data_type"] == "MASK"
    assert describe_node_data_type("  latent  ")["data_type"] == "LATENT"
    assert describe_node_data_type("nope")["valid"] is False
    assert describe_node_data_type("nope")["data_type"] is None


def test_the_replacement_reuses_the_exact_original_name():
    """Rule 13: nothing is renamed, so no consumer learns a new spelling."""
    meta = describe_node_data_type._node_metadata
    assert meta["name"] == TARGET
    # And the name the OLD decorator advertised is the same string.
    assert TARGET == "image_processing.NodeDataType"


def test_flag_off_advertises_nothing_under_the_old_name(nodes):
    """Default install: the lie is gone and the name is simply absent."""
    assert [n.name for n in nodes if n.name == TARGET] == [], (
        "image_processing.NodeDataType must not be advertised on a default install; "
        "the replacement is gated and starts OFF"
    )


def test_enabling_the_flag_advertises_exactly_one_invocable_entry(flag_on):
    """ON: the name returns, as one real function — never as a class."""
    visible = [n for n in discover_nodes(force=True) if n.name == TARGET]
    assert len(visible) == 1, (
        f"expected exactly one entry, got {[(n.module, n.qualname) for n in visible]}"
    )
    entry = visible[0]
    assert entry.module == NODES_MODULE
    assert entry.qualname == "describe_node_data_type"
    assert entry.executable is True
    module = importlib.import_module(entry.module)
    assert getattr(module, "describe_node_data_type") is describe_node_data_type
    # The thing the bridge would actually invoke must succeed.
    assert module.describe_node_data_type()["members"]


def test_the_flag_name_cannot_prune_another_nodes_module(flag_on):
    """The flag must be inert for everything except its own node.

    Runs with the flag **ON** on purpose. With it off, a path-derived flag name
    prunes its own collateral out of the registry and the scan finds nothing to
    complain about — the assertion would pass for exactly the mistake it exists to
    catch.
    """
    visible = discover_nodes(force=True)
    collateral = sorted(
        (n.module, n.qualname)
        for n in visible
        if SCHEMA_NODES_FLAG in node_flag_candidates(n)
    )
    assert collateral == [(NODES_MODULE, "describe_node_data_type")], (
        f"{SCHEMA_NODES_FLAG} is a pruning candidate for nodes other than its own, "
        f"so switching it off would prune them too: {collateral}"
    )

    # The explicit feature_flag must suppress the path-derived candidates.
    mine = [n for n in visible if n.name == TARGET][0]
    derived = _module_flag_candidates(mine.module, "describe_node_data_type")
    assert node_flag_candidates(mine) == [SCHEMA_NODES_FLAG]
    assert SCHEMA_NODES_FLAG not in derived, (
        "the flag name is also a path-derived candidate; had it been derived, "
        f"turning it off would have pruned {len(derived)} nodes: {derived}"
    )


def test_the_nodes_registry_package_is_not_a_pruning_candidate(nodes):
    """The 43 newly visible nodes must not depend on my flag to stay visible.

    A flag named ``image_processing.nodes_registry`` or ``image_processing.nodes``
    would prune the whole package on a default install — the newly unmasked
    package would flip from hidden-by-accident to hidden-by-design.
    """
    at_risk = [
        (n.module, n.qualname)
        for n in nodes
        if (n.module or "").startswith(
            "common_lib.modules.image_processing.nodes_registry."
        )
        and SCHEMA_NODES_FLAG in node_flag_candidates(n)
    ]
    assert at_risk == [], (
        f"nodes_registry nodes would be pruned by {SCHEMA_NODES_FLAG}: {at_risk}"
    )


# ── 4. the flag registration ─────────────────────────────────────────────────


def test_flag_is_registered_off_in_the_reference_json():
    """Registration, not resolved value.

    ``is_enabled`` is fail-open and returns True for an unregistered key, so the
    resolved value cannot distinguish "registered and off" from "never existed".
    Only ``registered_flag()`` reads the shipped JSON and can tell.
    """
    path = reference_config_path()
    assert path is not None, "feature_flags.reference.json was not found"
    assert path.name == "feature_flags.reference.json"
    assert registered_flag(SCHEMA_NODES_FLAG) is False, (
        f"{SCHEMA_NODES_FLAG} must be REGISTERED and OFF in {path}. "
        "`is False`, not `is not None` -- an unregistered key resolves to False "
        "too, and would let the flag be deleted without any test noticing."
    )


def test_flag_parent_is_already_on():
    """A leaf under an OFF parent would be unreachable, so the parent must be True."""
    assert registered_flag("image_processing") is True


def test_the_flag_file_is_valid_json_with_an_unchanged_top_level_shape():
    """Several agents rewrite this file concurrently; a bad write must fail here."""
    import json

    path = reference_config_path()
    tree = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(tree, dict)
    assert "image_processing" in tree
    assert "nodes_registry" in tree["image_processing"]
    assert "schema_nodes" in tree["image_processing"]["nodes_registry"]
    assert (
        tree["image_processing"]["nodes_registry"]["schema_nodes"]["enabled"] is False
    )
    assert tree["image_processing"]["enabled"] is True


# ── 5. the other masked package ──────────────────────────────────────────────


def test_comfyui_wrapper_is_now_discovered(nodes):
    """The second over-match, unmasked: 7 entries were invisible because of it."""
    entries = [
        n
        for n in nodes
        if n.module == "common_lib.modules.workflows.standard.nodes.comfyui_wrapper"
    ]
    assert entries, (
        "workflows/standard/nodes/comfyui_wrapper.py is still not discovered. The "
        "skip-list entry 'workflows.standard.nodes.comfyui' was matching it as a "
        "substring."
    )
    assert len(entries) == 7, (
        f"contribution changed: {[(n.name, n.qualname) for n in entries]}"
    )


def test_no_module_is_exempt_twice_over():
    """A module hit by two entries must still report a real prefix, not a partial one."""
    for path in _scan_module_paths():
        mod_dot = _path_to_module(path)
        if not mod_dot:
            continue
        hit = _skip_prefix_for(mod_dot)
        if hit is not None:
            rel = mod_dot.removeprefix("common_lib.modules.")
            assert rel == hit or rel.startswith(hit + "."), (
                f"{mod_dot} matched prefix {hit!r} without being under it"
            )


def test_the_schema_module_has_exactly_fourteen_entries(nodes):
    """Pin the schema.py contribution so a new @node there is a deliberate act.

    Was 15 with the Enum counted, is 14 now. If this changes, the change is
    visible in a diff rather than discovered by an agent three weeks from now.
    """
    entries = [n for n in nodes if n.module == SCHEMA_MODULE]
    assert len(entries) == 14, f"got {[(n.name, n.qualname) for n in entries]}"
    assert not [n for n in entries if n.name == TARGET], (
        "schema.py is advertising the Enum again"
    )
