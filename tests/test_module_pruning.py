"""Tests for load-time feature-flag module pruning.

These cover the *consumer* side of the hierarchical feature flags: the read path that
gives ``set_module_enabled(...)`` its effect. The write path already existed with zero
readers, so ``set_module_enabled("memory", False)`` used to succeed, persist, and change
nothing.

Every test that mutates flag state uses ``persist=False`` so the real
``resources/memory_config.ini`` is never written. A fixture reloads the store
afterwards to undo the mutation for the next test.

Design contract under test (see docs/duplication-audit/MODULE-PRUNING.md):
  * Fail-open. Unregistered path => enabled. Never prune the undeclared.
  * Hierarchical. Disabling ``memory`` disables ``memory.core.sessions.create``.
  * Most-specific-off wins, checked in the order the caller supplies.
  * ``registered default False`` != ``explicitly disabled``. A module that ships
    itself off (e.g. ``platform_controls``) is NOT pruned.
"""

from __future__ import annotations

import pytest

from common_lib.modules.common.feature_flags import (
    FeatureFlagStore,
    get_registered_flags,
    invalidate_cache,
)
from common_lib.modules.common import module_pruning as mp
from common_lib.modules.nodes_registry import discover_nodes

# ── The single most important constant in this file ──────────────────────────
# `discover_nodes()` returned this many nodes BEFORE the pruning filter existed
# (measured on a clean tree with no flags disabled). After the change the count is
# EXPECTED_UNPRUNED + 1: the extra node is `common.describe_module_pruning`, the new
# @node this feature itself registers (see test_new_pruning_node_is_discovered).
EXPECTED_UNPRUNED = 25960
EXPECTED_AFTER = EXPECTED_UNPRUNED + 1


@pytest.fixture(autouse=True)
def _clean_flag_state():
    """Undo any runtime flag mutation a test performs. Never persists to disk."""
    yield
    FeatureFlagStore().reload()


# ═══════════════════════════════════════════════════════════════════════════
# Fail-open: never prune the undeclared
# ═══════════════════════════════════════════════════════════════════════════


def test_unregistered_path_is_enabled():
    """A path nobody registered a flag for is ALWAYS enabled."""
    assert "totally.made.up.path" not in get_registered_flags()
    assert mp.is_path_enabled("totally.made.up.path") is True
    assert mp.is_path_enabled("") is True


def test_unregistered_candidates_never_resolve():
    """resolve_flag_path ignores unregistered candidates entirely."""
    assert mp.resolve_flag_path(["no.such.flag", "also.not.real"]) is None
    assert mp.resolve_flag_path([]) is None


def test_node_without_common_lib_module_is_never_pruned():
    """A node not attributable to common_lib.modules.* is never pruned (fail safe)."""

    class FakeNode:
        name = "weird.node"
        qualname = "weird"
        module = "some_third_party.pkg.elsewhere"
        metadata: dict = {}

    assert mp.node_flag_candidates(FakeNode()) == []
    assert mp.is_node_enabled(FakeNode()) is True

    class NoModule:
        name = "x"
        qualname = ""

    # No `module` attribute at all.
    assert mp.node_flag_candidates(NoModule()) == []
    assert mp.is_node_enabled(NoModule()) is True


# ═══════════════════════════════════════════════════════════════════════════
# Hierarchical evaluation
# ═══════════════════════════════════════════════════════════════════════════


def test_disabling_parent_disables_deep_descendant():
    """set_module_enabled("memory", False) => memory.core.sessions.create is off."""
    FeatureFlagStore().set_module_enabled("memory", False, persist=False)
    assert mp.is_path_enabled("memory") is False
    assert mp.is_path_enabled("memory.core") is False
    assert mp.is_path_enabled("memory.core.sessions") is False
    assert mp.is_path_enabled("memory.core.sessions.create") is False


def test_disabling_leaf_leaves_parent_on():
    """The reverse direction: a leaf being off does not imply its parent is off."""
    FeatureFlagStore().set_enabled("memory.core.sessions", False, persist=False)
    assert mp.is_path_enabled("memory.core.sessions") is False
    assert mp.is_path_enabled("memory.core.sessions.create") is False
    assert mp.is_path_enabled("memory") is True
    assert mp.is_path_enabled("memory.core") is True


def test_is_module_enabled_uses_first_segment():
    FeatureFlagStore().set_module_enabled("memory", False, persist=False)
    assert mp.is_module_enabled("memory") is False
    assert mp.is_module_enabled("memory.core.sessions.create") is False
    assert mp.is_module_enabled("") is True


# ═══════════════════════════════════════════════════════════════════════════
# Precedence: most-specific-off wins
# ═══════════════════════════════════════════════════════════════════════════


def test_most_specific_off_wins_over_on_ancestors():
    """memory.core.sessions OFF, .create still at its registered default => .sessions wins.

    The caller offers most-specific-first. `.create` is *not itself* off (its own
    registered default is True), so the shallower `.sessions` — which IS off — is the
    answer. Nothing is pruned only when *every* candidate is on.

    Note `is_enabled("memory.core.sessions.create")` is False here, but only because
    the store's hierarchical walk sees the off ancestor. That is what
    `_is_explicitly_disabled` compares against the *registered default*, and the
    reason the resolution lands on `.sessions` rather than `.create`.
    """
    store = FeatureFlagStore()
    store.set_enabled("memory.core.sessions", False, persist=False)

    candidates = [
        "memory.core.sessions.create",
        "memory.core.sessions",
        "memory.core",
        "memory",
    ]
    assert mp.resolve_flag_path(candidates) == "memory.core.sessions"


def test_all_candidates_on_resolves_to_none():
    """Nothing disabled => nothing pruned."""
    assert (
        mp.resolve_flag_path(
            [
                "memory.core.sessions.create",
                "memory.core.sessions",
                "memory.core",
                "memory",
            ]
        )
        is None
    )


def test_deepest_disabled_wins_when_both_off():
    """When both the leaf and its parent are explicitly off, the leaf is reported."""
    store = FeatureFlagStore()
    store.set_module_enabled("memory", False, persist=False)
    store.set_enabled("memory.core.sessions.create", False, persist=False)
    candidates = ["memory.core.sessions.create", "memory.core.sessions", "memory"]
    # Most-specific-first: the leaf is checked before its parent.
    assert mp.resolve_flag_path(candidates) == "memory.core.sessions.create"


def test_leaf_turned_back_on_falls_through_to_parent():
    """Re-enabling the leaf while the parent is off reports the parent instead."""
    store = FeatureFlagStore()
    store.set_module_enabled("memory", False, persist=False)
    store.set_enabled("memory.core.sessions.create", True, persist=False)
    candidates = ["memory.core.sessions.create", "memory.core.sessions", "memory"]
    # .create matches its registered default again, so .sessions is the first
    # candidate that is genuinely off.
    assert mp.resolve_flag_path(candidates) == "memory.core.sessions"


# ═══════════════════════════════════════════════════════════════════════════
# registered-default-False must NOT be treated as "disabled by an admin"
# ═══════════════════════════════════════════════════════════════════════════


def test_registered_default_false_is_not_pruned():
    """A module that ships itself off is NOT pruned.

    ~44 flags are registered False by their own modules (the whole
    `platform_controls` subtree, `knowledge_engine.alerts`, ...). Treating those as
    prunable would remove 243 nodes from the live platform on deploy with no admin
    action. `is_path_enabled` honestly reports them as off; pruning must not act.
    """
    registered = get_registered_flags()
    default_falses = [k for k, v in registered.items() if v is False]
    assert default_falses, "registry should still contain default-False flags"

    for flag in default_falses:
        assert mp.is_path_enabled(flag) is False, f"{flag} should read as off"
        assert mp.resolve_flag_path([flag]) is None, (
            f"{flag} ships default-False and must not be pruned without admin action"
        )


def test_platform_controls_ships_off_and_is_kept():
    """The flagship default-off module is still loadable until an admin disables it."""
    assert get_registered_flags()["platform_controls"] is False
    assert mp.is_path_enabled("platform_controls") is False
    assert mp.resolve_flag_path(["platform_controls"]) is None
    # A module that ships default-False is *never* "explicitly disabled", because
    # disabled-by-someone is defined as a value that DIFFERS from the registered
    # default. Re-asserting False is a no-op (it already matches), so no pruning.
    # This is a deliberate limit, not an oversight: such a module has declared itself
    # off, and load-pruning it would change the platform's node surface silently.
    # An admin who genuinely wants it gone uses `platform.module_pruning_enabled=false`
    # to restore the pre-pruning surface wholesale, or the module's own default is
    # flipped to True in its registration.
    store = FeatureFlagStore()
    store.set_module_enabled("platform_controls", False, persist=False)
    assert mp.resolve_flag_path(["platform_controls"]) is None
    store.set_module_enabled("platform_controls", True, persist=False)
    assert mp.resolve_flag_path(["platform_controls"]) is None


def test_default_false_module_stays_discoverable_end_to_end():
    """platform_controls nodes are still advertised despite shipping off."""
    names = {n.name for n in discover_nodes(force=True)}
    pc_nodes = [
        n for n in discover_nodes(force=True) if "platform_controls" in n.module
    ]
    assert pc_nodes, "expected platform_controls nodes to be discoverable"
    assert names  # sanity: registry is populated


def test_explicitly_disabled_default_true_module_prunes():
    """The normal case: a default-True module turned off by an admin IS pruned."""
    store = FeatureFlagStore()
    assert get_registered_flags()["memory"] is True
    assert mp.resolve_flag_path(["memory"]) is None
    store.set_module_enabled("memory", False, persist=False)
    assert mp.resolve_flag_path(["memory"]) == "memory"


# ═══════════════════════════════════════════════════════════════════════════
# BACKWARD COMPAT — the load-bearing assertion
# ═══════════════════════════════════════════════════════════════════════════


def test_discover_nodes_count_unchanged_with_no_flag_disabled():
    """With nothing disabled, discover_nodes() returns the SAME count as before.

    This is the single most important assertion in the file: the filter must be a
    pure no-op on a default install, so the pre-existing 25960 nodes must all still
    be there, plus exactly one new node (`common.describe_module_pruning`).

    The absolute number is asserted as a FLOOR, not an equality, because the count is
    process-dependent — a pytest session that imports more of the package first
    discovers more nodes (25961 standalone vs ~25974 in-suite). Pinning an exact
    integer would make this test fail for reasons that have nothing to do with
    pruning, which is how baseline-drift regressions get normalised. The exact
    invariant that IS deterministic is asserted in
    test_pruning_removes_nothing_on_a_default_install: in-process, discover_nodes()
    returns exactly what the unpruned scan returns.
    """
    nodes = discover_nodes(force=True)
    assert len(nodes) >= EXPECTED_AFTER, (
        f"node count regressed below the pre-change baseline: expected at least "
        f"{EXPECTED_AFTER} ({EXPECTED_UNPRUNED} pre-existing + 1 new "
        f"describe_module_pruning), got {len(nodes)}"
    )
    names = {n.name for n in nodes}
    assert "common.describe_module_pruning" in names


def test_pruning_removes_nothing_on_a_default_install():
    """The filter itself drops zero nodes when no flag is explicitly disabled."""
    import common_lib.modules.nodes_registry as registry

    raw = registry._discover_from_paths(registry._scan_module_paths())
    pruned = mp.prune_nodes(raw)
    kept = {id(x) for x in pruned}
    assert len(pruned) == len(raw), (
        "pruning must be a no-op on a default install; dropped "
        f"{[n.name for n in raw if id(n) not in kept]}"
    )
    # The same invariant, exercised through the public entry point: whatever the
    # unpruned scan yields, discover_nodes() must yield identically when nothing is
    # explicitly disabled. This is the deterministic form of the count assertion.
    assert len(discover_nodes()) == len(raw)


def test_describe_pruning_node_is_not_self_pruned():
    """Guard the no-op claim explicitly, so a future `common.*` flag can't surprise.

    Even the new node survives: its module path derives to
    `common.module_pruning.describe_pruning` -> ... -> `common`, and no `common*`
    flag is registered, so the unregistered-is-enabled fail-open rule keeps it. The
    gate flag lives under `platform.`, a different top-level segment, so it is not
    an ancestor of `common`.
    """
    nodes = [
        n
        for n in discover_nodes(force=True)
        if n.name == "common.describe_module_pruning"
    ]
    assert len(nodes) == 1
    assert mp.node_flag_candidates(nodes[0]) == [
        "common.module_pruning.describe_pruning",
        "common.module_pruning",
        "common",
    ]
    assert mp.resolve_flag_path(mp.node_flag_candidates(nodes[0])) is None


def test_new_pruning_node_is_discovered():
    """The describe_pruning @node is itself discoverable (G3)."""
    names = {n.name for n in discover_nodes(force=True)}
    assert "common.describe_module_pruning" in names


# ═══════════════════════════════════════════════════════════════════════════
# set_module_enabled actually removes nodes
# ═══════════════════════════════════════════════════════════════════════════


def test_set_module_enabled_false_removes_memory_nodes():
    """THE consumer test: disabling a module removes its nodes from discovery."""
    before = discover_nodes(force=True)
    memory_before = [
        n for n in before if n.module.startswith("common_lib.modules.memory")
    ]
    assert memory_before, "expected memory nodes to exist before pruning"

    FeatureFlagStore().set_module_enabled("memory", False, persist=False)
    after = discover_nodes()  # no force — the filter must apply to the cached scan
    memory_after = [
        n for n in after if n.module.startswith("common_lib.modules.memory")
    ]

    assert not memory_after, f"{len(memory_after)} memory nodes survived pruning"
    assert len(after) == len(before) - len(memory_before)


def test_re_enabling_restores_nodes():
    """Re-enabling brings the nodes back (proves the filter is not destructive)."""
    before = discover_nodes(force=True)
    store = FeatureFlagStore()
    store.set_module_enabled("memory", False, persist=False)
    assert len(discover_nodes()) < len(before)

    store.set_module_enabled("memory", True, persist=False)
    assert len(discover_nodes()) == len(before)


def test_prune_survives_a_broken_flag_store(monkeypatch):
    """If pruning raises, discover_nodes() serves the full unpruned list."""

    def boom(_):
        raise RuntimeError("flag store exploded")

    monkeypatch.setattr(mp, "prune_nodes", boom)
    assert len(discover_nodes(force=True)) >= EXPECTED_UNPRUNED


# ═══════════════════════════════════════════════════════════════════════════
# The gate
# ═══════════════════════════════════════════════════════════════════════════


def test_gate_is_registered_and_defaults_true():
    assert mp.PRUNING_FLAG == "platform.module_pruning_enabled"
    assert get_registered_flags()[mp.PRUNING_FLAG] is True
    assert mp.is_pruning_enabled() is True


def test_gate_off_disables_all_pruning():
    """The gate is a single global kill switch (fail-open: nothing is pruned)."""
    store = FeatureFlagStore()
    store.set_module_enabled("memory", False, persist=False)
    assert mp.resolve_flag_path(["memory"]) == "memory"

    store.set_enabled(mp.PRUNING_FLAG, False, persist=False)
    assert mp.is_pruning_enabled() is False
    assert mp.resolve_flag_path(["memory"]) is None
    assert mp.is_path_enabled("memory") is True  # fail-open
    # Nodes come back — memory nodes are present again.
    assert [
        n for n in discover_nodes() if n.module.startswith("common_lib.modules.memory")
    ]


# ═══════════════════════════════════════════════════════════════════════════
# Candidate derivation + explicit @node(feature_flag=...)
# ═══════════════════════════════════════════════════════════════════════════


def test_candidates_are_most_specific_first():
    cands = mp.node_flag_candidates(
        type(
            "N",
            (),
            {
                "module": "common_lib.modules.memory.core.sessions",
                "qualname": "create_session",
                "name": "memory.create",
                "metadata": {},
            },
        )()
    )
    assert cands == [
        "memory.core.sessions.create_session",
        "memory.core.sessions",
        "memory.core",
        "memory",
    ]


def test_explicit_feature_flag_is_used_alone():
    """@node(feature_flag=...) overrides derivation entirely."""
    from common_lib.modules.plugins.node import node

    @node(
        name="test.pruning.explicit_flag",
        description="probe",
        category="common",
        tags=["test"],
        audience=["executor"],
        input_schema={},
        output_schema={},
        feature_flag="memory.core.sessions",
    )
    def probe() -> str:
        return "ok"

    # The flag really is in the metadata dict (not just the decorator signature).
    assert probe._node_metadata["metadata"]["feature_flag"] == "memory.core.sessions"

    class N:
        name = "test.pruning.explicit_flag"
        qualname = "probe"
        module = "common_lib.modules.memory.core.sessions"
        metadata = probe._node_metadata["metadata"]

    assert mp.node_flag_candidates(N()) == ["memory.core.sessions"]

    FeatureFlagStore().set_module_enabled("memory", False, persist=False)
    assert mp.is_node_enabled(N()) is False

    # A node with a DIFFERENT module but the same explicit flag prunes identically.
    class Other:
        name = "elsewhere"
        qualname = "x"
        module = "common_lib.modules.totally_other_thing"
        metadata = probe._node_metadata["metadata"]

    assert mp.is_node_enabled(Other()) is False


# ═══════════════════════════════════════════════════════════════════════════
# filter_enabled helper
# ═══════════════════════════════════════════════════════════════════════════


def test_filter_enabled_keeps_and_drops():
    items = [
        {"flag": "memory.core.sessions.create"},
        {"flag": "behaviour.policies.safety"},
    ]
    FeatureFlagStore().set_module_enabled("memory", False, persist=False)
    kept = mp.filter_enabled(items, lambda i: i["flag"])
    assert kept == [{"flag": "behaviour.policies.safety"}]


def test_filter_enabled_keeps_unnameable_items():
    """An item whose key cannot be read is KEPT (fail-open)."""

    def bad(_item):
        raise RuntimeError("nope")

    items = [1, 2, 3]
    assert mp.filter_enabled(items, bad) == items
    assert mp.filter_enabled([], lambda i: i) == []


# ═══════════════════════════════════════════════════════════════════════════
# describe_pruning — the admin/UI surface
# ═══════════════════════════════════════════════════════════════════════════


def test_describe_pruning_shape():
    d = mp.describe_pruning()
    assert set(d) == {"enabled", "registered", "disabled", "modules", "tree"}
    assert d["enabled"] is True
    assert d["registered"] == len(get_registered_flags())
    assert d["disabled"] == sorted(d["disabled"])
    assert "memory" in d["modules"]
    assert "memory" in d["tree"]
    # serializable — the MCP/REST bridge must be able to ship it
    import json

    json.dumps(d)


def test_describe_pruning_reports_disabled_after_set_module_enabled():
    d0 = mp.describe_pruning()
    assert "memory.core.sessions.create" not in d0["disabled"]

    FeatureFlagStore().set_module_enabled("memory", False, persist=False)
    d1 = mp.describe_pruning()

    assert d1["modules"]["memory"] is False
    assert "memory.core.sessions.create" in d1["disabled"]
    assert "memory.core.sessions.create" not in d0["disabled"]  # old snapshot intact


def test_describe_pruning_marks_module_off():
    """An admin toggles a module off and the UI surface reflects it."""
    assert mp.describe_pruning()["modules"]["memory"] is True
    FeatureFlagStore().set_module_enabled("memory", False, persist=False)
    assert mp.describe_pruning()["modules"]["memory"] is False
    # Unrelated module untouched.
    assert mp.describe_pruning()["modules"]["behaviour"] is True


# ═══════════════════════════════════════════════════════════════════════════
# Persistence safety
# ═══════════════════════════════════════════════════════════════════════════


def test_tests_never_write_memory_config_ini(tmp_path, monkeypatch):
    """Guard: persist=False must not touch the real config file."""
    path = tmp_path / "memory_config.ini"
    path.write_text("[Memory]\nmemory = true\n", encoding="utf-8")
    monkeypatch.setattr(mp, "_MODULE_UNUSED", None, raising=False)
    store = FeatureFlagStore()
    monkeypatch.setattr(store, "_config_path", path)

    store.set_module_enabled("memory", False, persist=False)
    assert "false" not in path.read_text(encoding="utf-8")
    # But persist=True does write.
    store.set_module_enabled("memory", False, persist=True)
    assert "memory = false" in path.read_text(encoding="utf-8")


def test_invalidate_cache_is_available():
    """Sanity: the store exposes the documented reset hook."""
    assert callable(invalidate_cache)


# ═══════════════════════════════════════════════════════════════════════════
# Router pruning (app/core/routers.py)
# ═══════════════════════════════════════════════════════════════════════════


def test_router_candidates_and_pruning():
    """A router with a disabled module is not mounted; one without never is."""
    from app.core.routers import is_router_enabled, prune_router_definitions

    # No module key => fail-open => always mounted (this is every existing entry).
    assert is_router_enabled({"router": None, "prefix": "", "tags": ["X"]}) is True

    # Explicit feature_flag wins outright.
    entry = {
        "router": None,
        "prefix": "",
        "module": "memory",
        "feature_flag": "memory.core",
    }
    FeatureFlagStore().set_enabled("memory.core", False, persist=False)
    assert is_router_enabled(entry) is False
    FeatureFlagStore().reload()
    assert is_router_enabled(entry) is True

    # Derived from `module`.
    mem = {"router": None, "prefix": "/memory", "module": "memory"}
    other = {"router": None, "prefix": "/workflows", "module": "workflows"}
    assert is_router_enabled(mem) is True

    FeatureFlagStore().set_module_enabled("memory", False, persist=False)
    kept = prune_router_definitions([mem, other])
    assert mem not in kept
    assert other in kept
    assert len(kept) == 1


def test_router_pruning_candidate_shape():
    from app.core.routers import router_prune_candidates

    assert router_prune_candidates({}) == []
    assert router_prune_candidates({"module": "memory"}) == ["memory"]
    assert router_prune_candidates({"module": "a.b"}) == ["a.b", "a"]
    assert router_prune_candidates({"module": "memory", "feature_flag": "x.y"}) == [
        "x.y"
    ]
    assert router_prune_candidates({"module": ""}) == []


def test_real_registry_entries_are_prunable():
    """The real ROUTER_DEFINITIONS registry has entries wired to real flags.

    Guards against the failure where the plumbing is added but no entry ever declares
    a `module`, leaving router pruning permanently inert.
    """
    from fastapi import FastAPI

    from app.core import routers as r

    def mount_all() -> set[str]:
        """Register every router onto a throwaway app; return its route paths.

        ROUTER_DEFINITIONS is a local inside register_routers() (each entry eagerly
        builds its router object), so the honest end-to-end check is the mounted
        route table — which is exactly what a disabled module must disappear from.
        """
        app = FastAPI()
        r.register_routers(app, "/api/v1", [])
        return {getattr(route, "path", "") for route in app.routes}

    # A default install mounts the memory surface, and the knowledge_hub surface
    # (the six entries that declare feature_flag="knowledge_engine").
    before = mount_all()
    assert any(p.startswith("/api/v1/memory") for p in before)
    assert any(p.startswith("/api/v1/memories") for p in before)

    # Disabling `memory` unmounts both memory routers: the paths vanish from the route
    # table entirely, so they also stop appearing in the OpenAPI schema.
    try:
        FeatureFlagStore().set_module_enabled("memory", False, persist=False)
        after = mount_all()
        assert not any(p.startswith("/api/v1/memory") for p in after)
        assert not any(p.startswith("/api/v1/memories") for p in after)
        # knowledge_engine is untouched by a memory-only disable.
        assert after >= {p for p in before if "memor" not in p}
        assert after < before, "pruning should have removed at least the memory paths"
    finally:
        FeatureFlagStore().set_module_enabled("memory", True, persist=False)


def test_router_pruning_fails_open_on_error(monkeypatch):
    """If the flag store explodes, every router is still mounted."""
    from app.core import routers as r

    monkeypatch.setattr(
        mp, "resolve_flag_path", lambda _c: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    assert r.is_router_enabled({"module": "memory"}) is True
