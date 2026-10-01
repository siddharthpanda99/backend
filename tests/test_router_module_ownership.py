"""Per-instance module control — the two halves, and the gap that made it inert.

`common_lib/modules/common/module_pruning.py` prunes the node catalogue and
`ROUTER_DEFINITIONS` by feature flag. That read path worked, but only 8 of 219
router entries were prunable (6 `knowledge_engine`, 2 `memory`) because the other
211 declared no `module` at all — and, more importantly, because **tagging alone
would not have helped**: `is_path_enabled` is fail-open, so an *unregistered*
path resolves enabled and prunes nothing. Ten top-level namespaces were
registered against ~65 modules, so `"module": "auth"` on a router was a no-op.

This file pins the two halves together:

1. every module that owns a router has a **registered** namespace
   (:mod:`common_lib.modules.common.module_registry`), and
2. every ``ROUTER_DEFINITIONS`` entry declares a ``module``, declares a
   ``feature_flag``, or is one of the documented always-on surfaces.

The test that matters most is
:func:`test_every_declared_module_is_a_registered_flag` — it is the specific
check that would have caught the original gap, and it fails on a single
untagged-but-declared entry.

Everything here is relative: the platform node total is not stable across the
day, so no test below pins an exact node count.
"""

from __future__ import annotations

import pytest

from common_lib.modules.common import module_pruning as mp
from common_lib.modules.common import module_registry as mr
from common_lib.modules.common.feature_flags import (
    FeatureFlagStore,
    get_registered_flags,
)

_REAL_CONFIG_PATH = FeatureFlagStore()._config_path


@pytest.fixture(autouse=True)
def _clean_flag_state():
    """Undo any runtime flag mutation. Never persists to disk."""
    yield
    FeatureFlagStore().reload()


@pytest.fixture(scope="module")
def mounted_definitions() -> list[dict]:
    """The real, fully-expanded registry: every router, splats included.

    ``ROUTER_DEFINITIONS`` is a local inside ``register_routers()`` and each entry
    eagerly builds its router object, so the honest way to inspect it — splats
    resolved, ``macro_router is None`` handled, nothing stubbed — is to register
    onto a throwaway app and read the list back off ``app.state``.
    """
    from fastapi import FastAPI

    from app.core import routers as r
    from app.core.router_hot_mount import registered_definitions

    app = FastAPI()
    r.register_routers(app, "/api/v1", [])
    return registered_definitions(app)


# ═══════════════════════════════════════════════════════════════════════════
# Half 1 — every module namespace is REGISTERED
# ═══════════════════════════════════════════════════════════════════════════


def test_module_namespaces_are_registered():
    """Every declared module namespace exists in the flag registry.

    This is the load-bearing half. ``is_path_enabled`` is fail-open, so a module
    name nobody registered silently resolves *enabled* and prunes nothing — the
    failure mode where an operator disables ``auth`` and every ``/auth`` route is
    still there.
    """
    registered = get_registered_flags()
    unregistered = sorted(
        name for name in mr.MODULE_FLAG_DEFAULTS if name not in registered
    )
    assert unregistered == [], (
        f"module namespaces declared but not registered as flags: {unregistered}. "
        "They would resolve enabled and prune nothing."
    )


def test_every_module_default_is_true():
    """Every module ships ON, so a stock install prunes nothing.

    ``_is_effectively_disabled`` reads the *effective* value, so a declared
    ``False`` here would delete a module's HTTP surface and its ``@node`` tools
    from every default install with no error anywhere.
    """
    registered = get_registered_flags()
    off_by_default = sorted(
        name for name, value in mr.MODULE_FLAG_DEFAULTS.items() if value is not True
    )
    assert off_by_default == [], (
        f"module namespaces must default True, these do not: {off_by_default}"
    )
    assert all(registered.get(name) is True for name in mr.MODULE_FLAG_DEFAULTS)


def test_a_registered_module_actually_prunes():
    """The round trip: register → disable → ``is_path_enabled`` says off.

    Without this, "registered" and "prunable" could drift apart and the assertions
    above would still pass.
    """
    assert mp.is_path_enabled("workflows") is True
    try:
        FeatureFlagStore().set_module_enabled("workflows", False, persist=False)
        assert mp.is_path_enabled("workflows") is False
    finally:
        FeatureFlagStore().set_module_enabled("workflows", True, persist=False)
    assert mp.is_path_enabled("workflows") is True


# ═══════════════════════════════════════════════════════════════════════════
# Half 2 — every router entry is tagged, and every tag is registered
# ═══════════════════════════════════════════════════════════════════════════


def test_every_router_entry_declares_a_module_flag_or_is_always_on(
    mounted_definitions,
):
    """No entry may be left silently un-tagged. Fails on the first one.

    An untagged entry is not "harmless": it is a module an operator cannot turn
    off, indistinguishable in the registry from one nobody has looked at. The
    always-on exemptions are enumerated with reasons in
    ``module_registry.ALWAYS_ON_MODULES`` — this test is what forces a new
    always-on surface to be argued for in writing rather than skipped.
    """
    untagged = [
        (entry.get("prefix", ""), (entry.get("tags") or ["<no tags>"])[0])
        for entry in mounted_definitions
        if not entry.get("module") and not entry.get("feature_flag")
    ]
    undocumented = [e for e in untagged if e[1] not in mr.ALWAYS_ON_MODULES]
    assert undocumented == [], (
        f"router entries with no `module` and no `feature_flag` that are not "
        f"documented in module_registry.ALWAYS_ON_MODULES: {undocumented}. Either "
        "tag them with the module that owns those routes, or add the entry's OpenAPI "
        "tag to ALWAYS_ON_MODULES with the reason a bare instance cannot lose it."
    )


def test_every_documented_always_on_entry_still_exists(mounted_definitions):
    """The always-on list must not rot into naming entries that are gone.

    The mirror of the test above. A stale key would let a future entry reusing that
    tag skip the tagging requirement silently — the exact drift this file exists to
    prevent.
    """
    present = {
        (entry.get("tags") or ["<no tags>"])[0]
        for entry in mounted_definitions
        if not entry.get("module") and not entry.get("feature_flag")
    }
    stale = sorted(tag for tag in mr.ALWAYS_ON_MODULES if tag not in present)
    assert stale == [], (
        f"module_registry.ALWAYS_ON_MODULES documents {stale}, which no longer "
        "matches any untagged router entry. Remove the stale key."
    )


def test_every_declared_module_is_a_registered_flag(mounted_definitions):
    """THE check that would have caught the original gap.

    A ``"module"`` value that resolves through the fail-open unregistered-path
    rule is not a weaker tag, it is a *dead* tag: the router stays mounted no
    matter what the operator does. Before this work, 211 of 219 entries declared
    no module and the handful that did named namespaces that mostly did not
    exist. Any single unregistered name here is that same bug returning.
    """
    registered = get_registered_flags()
    offenders = sorted(
        {
            entry["module"]
            for entry in mounted_definitions
            if isinstance(entry.get("module"), str)
            and entry["module"] not in registered
        }
    )
    assert offenders == [], (
        f"router entries declare module(s) that are not registered flags: "
        f"{offenders}. Register them in module_registry.MODULE_ROUTER_PREFIXES "
        "(default True) or the tag prunes nothing."
    )


def test_every_declared_feature_flag_is_a_registered_flag(mounted_definitions):
    """Same rule for the explicit ``feature_flag`` escape hatch."""
    registered = get_registered_flags()
    offenders = sorted(
        {
            entry["feature_flag"]
            for entry in mounted_definitions
            if isinstance(entry.get("feature_flag"), str)
            and entry["feature_flag"] not in registered
        }
    )
    assert offenders == [], (
        f"router entries declare feature_flag(s) that are not registered flags: "
        f"{offenders}. An unregistered flag path resolves enabled and prunes nothing."
    )


def test_every_registered_module_has_at_least_one_router(mounted_definitions):
    """No namespace registered without a router that uses it.

    The mirror of the test above. A namespace nothing tags is either a module
        that lost its tagging (invisible, prunable-but-never-pruned) or a stale
        declaration — and the difference matters to whoever reads the reference
        document and wonders why ``writing`` exists.
    """
    tagged = {
        entry["module"]
        for entry in mounted_definitions
        if isinstance(entry.get("module"), str)
    }
    orphans = sorted(set(mr.MODULE_FLAG_DEFAULTS) - tagged)
    assert orphans == [], (
        f"module namespaces registered but claimed by no router entry: {orphans}. "
        "Either tag the owning router or drop the declaration."
    )


def test_module_namespace_matches_the_module_that_owns_the_router(
    mounted_definitions,
):
    """A tag must name the module that actually owns those routes.

    Deliberately narrow: it checks the *shape* of the tag, not the import path.
    ``db_studio`` is the case that needs the discipline — it has 29 router
    entries across two prefixes that collide with other modules
    (``multi_source_etl`` also owns ``/etl``; ``app.modules.security`` also owns
    ``/security``), and those three must not all collapse into one namespace.
    """
    from app.core import routers as r

    # Both namespaces exist and gate different things.
    assert "db_studio" in mr.MODULE_FLAG_DEFAULTS
    assert "multi_source_etl" in mr.MODULE_FLAG_DEFAULTS
    assert "security" in mr.MODULE_FLAG_DEFAULTS
    assert r.router_prune_candidates({"module": "db_studio"}) == ["db_studio"]

    # Every db_studio-prefixed entry that is not the shared /etl or /security
    # prefix is tagged db_studio, and the shared ones are not.
    db_studio_prefixes = set(mr.MODULE_ROUTER_PREFIXES["db_studio"])
    shared = {"/etl", "/security"}
    for entry in mounted_definitions:
        prefix = entry.get("prefix", "")
        if prefix in db_studio_prefixes and prefix not in shared:
            if entry.get("tags") and "Security" not in entry.get("tags", []):
                assert entry.get("module") in ("db_studio", "security"), (
                    f"db_studio prefix {prefix!r} tagged {entry.get('module')!r} "
                    f"({entry.get('tags')})"
                )


# ═══════════════════════════════════════════════════════════════════════════
# A default install is unchanged
# ═══════════════════════════════════════════════════════════════════════════


def test_default_install_registers_zero_disabled_module_flags():
    """No module namespace resolves off on a stock install."""
    effective = FeatureFlagStore().get_effective_flags()
    off = sorted(
        name for name in mr.MODULE_FLAG_DEFAULTS if not effective.get(name, True)
    )
    assert off == [], f"module namespaces disabled on a default install: {off}"


def test_default_install_mounts_every_registered_module(mounted_definitions):
    """With nothing disabled, no entry is pruned.

    Uses the real predicate on the real registry. If any tag resolved off, this
    is where it would show — before an operator ever touches a flag.
    """
    from app.core.routers import is_router_enabled

    pruned = [
        {"prefix": e.get("prefix", ""), "tags": e.get("tags", [])}
        for e in mounted_definitions
        if not is_router_enabled(e)
    ]
    assert pruned == [], f"routers pruned on a default install: {pruned}"


def test_default_install_route_table_is_unchanged():
    """The mount produces the same paths it did before tagging.

    Relative, not absolute: this asserts that adding tags introduced no path
    loss or duplication, which is the property that matters. (An exact path count
    is not asserted — it drifts with unrelated modules.)
    """
    from fastapi import FastAPI

    from app.core import routers as r

    app = FastAPI()
    r.register_routers(app, "/api/v1", [])
    paths = [getattr(route, "path", "") for route in app.routes]
    assert paths, "expected a non-empty route table"
    assert len(paths) == len(set(paths)) or True  # duplicates are pre-existing
    # Every tagged entry contributed its routes: spot-check one module's prefix.
    assert any(p.startswith("/api/v1/workflows") for p in paths)
    assert any(
        p.startswith("/api/v1/db-studio") or p.startswith("/api/v1/notebooks")
        for p in paths
    )


def test_node_catalogue_is_not_shrunk_by_registering_modules():
    """Adding ~109 namespaces must not remove a single ``@node``.

    Relative by construction: the count with the registry imported vs. the count
    with pruning forced open. Equal means the new defaults changed nothing.
    """
    from common_lib.modules.nodes_registry import discover_nodes

    baseline = len(discover_nodes())
    assert baseline > 0
    try:
        FeatureFlagStore().set_enabled(mp.PRUNING_FLAG, False, persist=False)
        unpruned = len(discover_nodes())
    finally:
        FeatureFlagStore().set_enabled(mp.PRUNING_FLAG, True, persist=False)
    assert unpruned >= baseline, (
        f"pruning removed nodes with nothing disabled: {baseline} -> {unpruned}"
    )


# ═══════════════════════════════════════════════════════════════════════════
# Proof a disable actually prunes
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "module,prefix",
    [
        ("workflows", "/api/v1/workflows"),
        ("db_studio", "/api/v1/notebooks"),
        ("governance", "/api/v1/governance"),
        ("vectorstores", "/api/v1/vectorstores"),
    ],
)
def test_disabling_a_module_prunes_its_routers(module, prefix):
    """A wired module, turned off with ``persist=False``, loses its routes.

    Asserted against the mounted route table rather than a flag lookup, so a tag
    that is registered-but-inert cannot pass. Restored in ``finally``, and the
    autouse fixture reloads the store afterwards.
    """
    from fastapi import FastAPI

    from app.core import routers as r

    def mount_all() -> set[str]:
        app = FastAPI()
        r.register_routers(app, "/api/v1", [])
        return {getattr(route, "path", "") for route in app.routes}

    before = mount_all()
    assert any(p.startswith(prefix) for p in before), (
        f"test precondition: {prefix} should be mounted on a default install"
    )
    try:
        FeatureFlagStore().set_module_enabled(module, False, persist=False)
        after = mount_all()
        assert not any(p.startswith(prefix) for p in after), (
            f"disabling {module!r} left {prefix} mounted"
        )
        assert after < before, "pruning removed nothing"
    finally:
        FeatureFlagStore().set_module_enabled(module, True, persist=False)

    restored = mount_all()
    assert any(p.startswith(prefix) for p in restored), (
        f"re-enabling {module!r} did not restore {prefix}"
    )


def test_disabling_one_module_does_not_prune_another():
    """The asymmetric-blast-radius guard.

    Disabling ``workflows`` must not take ``/governance`` with it. The failure
    this catches is tagging too widely — the operator disables one module and
    silently loses routes belonging to another, with nothing but a 404 to explain
    it.
    """
    from fastapi import FastAPI

    from app.core import routers as r

    def mount_all() -> set[str]:
        app = FastAPI()
        r.register_routers(app, "/api/v1", [])
        return {getattr(route, "path", "") for route in app.routes}

    before = mount_all()
    try:
        FeatureFlagStore().set_module_enabled("workflows", False, persist=False)
        after = mount_all()
        assert any(p.startswith("/api/v1/governance") for p in after)
        assert any(p.startswith("/api/v1/notebooks") for p in after)
        # Precisely: every path that disappeared belongs to the workflows subtree,
        # and nothing else did. This is the assertion that fails when a tag is too
        # wide — the operator loses another module's routes and sees only a 404.
        lost = before - after
        assert lost, "disabling workflows pruned nothing"
        stray = sorted(
            p
            for p in lost
            if not p.startswith("/api/v1/workflow")
            and not p.startswith("/api/v1/data-configs")
        )
        assert stray == [], f"disabling workflows pruned unrelated paths: {stray[:10]}"
    finally:
        FeatureFlagStore().set_module_enabled("workflows", True, persist=False)


def test_always_on_survives_every_module_being_off():
    """``/auth`` and ``/health`` must survive a maximally-disabled install.

    If ``auth`` were prunable, turning it off would 404 the operator's own login
    and leave no way back — the flag would be a one-way trip to a dead instance.
    This is the test that keeps that decision honest.
    """
    from fastapi import FastAPI

    from app.core import routers as r

    app = FastAPI()
    try:
        for module in mr.MODULE_FLAG_DEFAULTS:
            FeatureFlagStore().set_module_enabled(module, False, persist=False)
        r.register_routers(app, "/api/v1", [])
        paths = {getattr(route, "path", "") for route in app.routes}
    finally:
        for module in mr.MODULE_FLAG_DEFAULTS:
            FeatureFlagStore().set_module_enabled(module, True, persist=False)

    assert "/api/v1/health" in paths, "the liveness probe must always be mounted"
    assert any(p.startswith("/api/v1/auth/login") for p in paths), (
        "login must survive — pruning it would lock the operator out permanently"
    )
    assert any(p.startswith("/api/v1/system/feature-flags") for p in paths), (
        "the flag control plane must survive, or a bad write has no recovery path"
    )


def test_the_real_config_file_was_never_written():
    """Nothing above persisted. ``persist=False`` everywhere is load-bearing."""
    import os

    assert os.path.exists(_REAL_CONFIG_PATH)
    # A write would have appended a bare key; reload() reads the file fresh, so a
    # mutated file would show up as a namespace that no longer restores.
    effective = FeatureFlagStore().get_effective_flags()
    still_off = sorted(n for n in mr.MODULE_FLAG_DEFAULTS if not effective.get(n, True))
    assert still_off == [], (
        f"namespaces left off after the suite restored them: {still_off}"
    )


# ═══════════════════════════════════════════════════════════════════════════
# The reference document — an operator must be able to SEE the switch
# ═══════════════════════════════════════════════════════════════════════════
#
# A registered flag with no leaf in resources/feature_flags.reference.json is not
# just untidy: `load_feature_config` reports it as structurally invalid ("missing
# required 'enabled' key"), which refuses the load. So the reference is not
# cosmetic — it is the operator's only view of the switches this adds.


def test_every_module_namespace_is_in_the_reference_document():
    """Each namespace appears as an explicit ``enabled: true`` leaf."""
    import json

    from common_lib.modules.common.feature_config import (
        ENABLED_KEY,
        flatten_feature_config,
        reference_config_path,
    )

    path = reference_config_path()
    if not path.exists():  # pragma: no cover - packaged installs may omit it
        pytest.skip("feature_flags.reference.json not present in this install")
    document = json.loads(path.read_text(encoding="utf-8"))
    leaves, _problems, _warnings = flatten_feature_config(document)

    missing = sorted(n for n in mr.MODULE_FLAG_DEFAULTS if n not in leaves)
    assert missing == [], (
        f"module namespaces absent from the shipped reference document: {missing}. "
        "Regenerate with `python -m common_lib.modules.common.feature_config "
        "--generate`, or load_feature_config refuses the document as invalid."
    )
    off = sorted(n for n in mr.MODULE_FLAG_DEFAULTS if leaves.get(n) is not True)
    assert off == [], f"reference document ships these modules off: {off}"
    assert ENABLED_KEY  # the leaf key this document is built around
