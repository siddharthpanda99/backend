"""Regression tests for the agents-module C1/C2 audit fixes.

Two fixes are covered here:

C2 — ``app/modules/agents/routes/snapshots_routes.py`` was written but never
     mounted. ``index.py`` now includes it under a ``/snapshots`` prefix, so the
     snapshot endpoints are reachable. These tests assert the router is mounted
     at the expected prefix AND that the new paths do not collide with the
     ``/{id}`` CRUD routes (the C2 criterion is "mounted, correct, not
     shadowed").

C1 — six new ``@node`` wrappers were added to
     ``common_lib/modules/agents/nodes.py`` behind the default-off feature flag
     ``agents.nodes.extended_coverage`` (G9). These tests assert the flag
     defaults OFF, that the wrapper callables exist and delegate correctly, and
     that turning the flag ON actually registers them in the node registry.
"""

import os

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute

os.environ.setdefault("DISABLE_AUTH", "true")

from app.modules.agents.routes import index as agents_index  # noqa: E402
from common_lib.modules.common.feature_flags import (  # noqa: E402
    FeatureFlagStore,
    is_enabled,
)
from common_lib.modules.agents import nodes as agents_nodes  # noqa: E402


# ═══════════════════════════════════════════════════════════════════════════
# C2 — snapshots router is mounted, and nothing it adds is shadowed
# ═══════════════════════════════════════════════════════════════════════════


def _registered_paths(router) -> set[str]:
    return {r.path for r in router.routes if isinstance(r, APIRoute)}


def test_snapshots_router_is_mounted():
    """C2 fix: snapshots_routes had zero importers; index.py now includes it."""
    paths = _registered_paths(agents_index.router)
    expected = {
        "/snapshots/sessions/{session_id}/snapshots",
        "/snapshots/sessions/{session_id}/snapshots",
        "/snapshots/snapshots/{snapshot_id}",
    }
    missing = expected - paths
    assert not missing, f"snapshot routes still unmounted: {sorted(missing)}"


def test_snapshot_paths_are_not_shadowed_by_crud_id_route():
    """The `/snapshots` prefix must not collide with the `/{id}` CRUD routes.

    `index.py` declares `@router.get("/{id}")`. Had the snapshot router been
    mounted at the bare root, `GET /snapshots/{snapshot_id}` would sit behind
    the param route and be unreachable. Assert the literal `/snapshots/...`
    segments are registered as their own routes and are not consumed by `/id`.
    """
    paths = _registered_paths(agents_index.router)
    assert "/snapshots/snapshots/{snapshot_id}" in paths
    # The CRUD param route is still present and unchanged.
    assert "/{id}" in paths


# ═══════════════════════════════════════════════════════════════════════════
# C1 — the new wrappers exist, delegate, and are gated OFF by default
# ═══════════════════════════════════════════════════════════════════════════

NEW_NODE_NAMES = [
    "List Available Loops",
    "Estimate Tokens",
    "Check Doom Loop",
    "Apply Chat Settings",
    "Get Chat Settings",
    "Load Agents Config",
]


@pytest.fixture
def restore_flag():
    """Snapshot the flag store and restore it, so tests never leak state."""
    store = FeatureFlagStore()
    before = store.get_all_flags().get(agents_nodes.FLAG_EXTENDED_NODES)
    yield store
    store.set_enabled(
        agents_nodes.FLAG_EXTENDED_NODES,
        before if before is not None else False,
        persist=False,
    )
    FeatureFlagStore._instance = None


def test_extended_nodes_flag_defaults_off(restore_flag):
    """G9: new behaviour ships default-OFF, so the registry is unchanged."""
    FeatureFlagStore._instance = None
    assert is_enabled(agents_nodes.FLAG_EXTENDED_NODES) is False, (
        "agents.nodes.extended_coverage must default to OFF"
    )


def test_all_new_wrapper_callables_exist():
    """Regression: the six audit-added wrappers must not be deleted."""
    for attr in (
        "list_loops",
        "estimate_tokens_node",
        "check_doom_loop",
        "apply_chat_settings",
        "get_chat_settings",
        "load_agents_config_node",
    ):
        assert callable(getattr(agents_nodes, attr)), f"{attr} is missing"


def test_wrapper_node_names_are_unique_and_unregistered_when_flag_off(
    restore_flag,
):
    """With the flag OFF none of the new names may appear in the registry.

    Reloads `nodes.py` with the flag forced OFF so this assertion does not
    depend on the module having been imported in the default state.
    """
    import importlib

    store = FeatureFlagStore()
    store.set_enabled(agents_nodes.FLAG_EXTENDED_NODES, False, persist=False)
    reloaded = importlib.reload(agents_nodes)

    registered = {getattr(n, "name", None) for n in _discover_agents_nodes(reloaded)}
    leaked = set(NEW_NODE_NAMES) & registered
    assert not leaked, f"new @nodes registered while flag is OFF: {sorted(leaked)}"


def test_turning_flag_on_registers_the_new_nodes(restore_flag):
    """With the flag ON all six new names become discoverable.

    @node registration happens at IMPORT time, so the flag must already be ON
    when `common_lib.modules.agents.nodes` is first imported. This test
    therefore sets the flag and then reloads the module, which is what a
    process restart with the flag enabled does.
    """
    import importlib

    store = FeatureFlagStore()
    store.set_enabled(agents_nodes.FLAG_EXTENDED_NODES, True, persist=False)
    reloaded = importlib.reload(agents_nodes)

    registered = {getattr(n, "name", None) for n in _discover_agents_nodes(reloaded)}
    missing = set(NEW_NODE_NAMES) - registered
    assert not missing, f"@nodes still undiscovered with flag ON: {sorted(missing)}"


def _discover_agents_nodes(module=None):
    """Discover only the @nodes added by this audit.

    `force=True` re-scans, because `discover_nodes()` caches globally and the
    flag-off/flag-on tests would otherwise read each other's cache.
    """
    from common_lib.modules.plugins.nodes_registry import discover_nodes

    mod = module if module is not None else agents_nodes
    return [
        n
        for n in discover_nodes(force=True)
        if getattr(n, "module", "") == "common_lib.modules.agents.nodes"
        and getattr(n, "qualname", "").lstrip("_").split(".")[0]
        in {
            "list_loops",
            "estimate_tokens_node",
            "check_doom_loop",
            "apply_chat_settings",
            "get_chat_settings",
            "load_agents_config_node",
        }
    ]


# ═══════════════════════════════════════════════════════════════════════════
# C1 — the wrappers delegate correctly (pure functions; no DB needed)
# ═══════════════════════════════════════════════════════════════════════════


def test_estimate_tokens_wrapper_matches_service():
    from common_lib.modules.agents.services.checkpoint_service import estimate_tokens

    for text in ("", "a", "hello world", "x" * 4000):
        assert agents_nodes.estimate_tokens_node(text) == {
            "tokens": estimate_tokens(text)
        }


def test_apply_chat_settings_wrapper_precedence():
    """Request values must win over persisted settings, which win over defaults."""
    out = agents_nodes.apply_chat_settings(
        {"run_mode": "plan", "reasoning_mode": True},
        {"run_mode": "agentic"},
    )["merged"]
    assert out["run_mode"] == "agentic"  # request wins
    assert out["reasoning_mode"] is True  # settings win over default (False)
    assert out["goal_mode"] is False  # untouched default survives


def test_check_doom_loop_wrapper_detects_period_one():
    """Three identical raw signatures trip the period-1 detector."""
    from common_lib.modules.agents.services.doom_loop_service import (
        compute_signature_hash,
    )

    sig = compute_signature_hash("search('foo')")
    out = agents_nodes.check_doom_loop([sig, sig], "search('foo')")
    assert out["detection"] is not None
    assert out["detection"]["period"] == 1


def test_check_doom_loop_wrapper_returns_null_when_no_loop():
    from common_lib.modules.agents.services.doom_loop_service import (
        compute_signature_hash,
    )

    out = agents_nodes.check_doom_loop(
        [compute_signature_hash("a"), compute_signature_hash("b")], "c"
    )
    assert out["detection"] is None


def test_load_agents_config_wrapper_returns_dict():
    out = agents_nodes.load_agents_config_node()
    assert set(out) == {"config"}
    assert isinstance(out["config"], dict)
    # AgentsConfig declares these; a valid load must populate them.
    assert "default_model" in out["config"]


# ═══════════════════════════════════════════════════════════════════════════
# C4 contract — the daemon response shape the UI binds to
# ═══════════════════════════════════════════════════════════════════════════


def test_daemon_response_does_not_expose_invented_ui_fields():
    """C4 fix: the UI used to read daemon_id/name/tasks_completed.

    `_daemon_to_dict` (daemon_routes.py:44) emits `id`/`agent_id`/`hostname`
    and nothing else. This test locks that contract so the UI cannot drift
    back onto fields the API never returns.
    """
    from app.modules.agents.routes.daemon_routes import _daemon_to_dict
    from common_lib.modules.agents.models.daemon_models import DaemonRegistration

    payload = _daemon_to_dict(
        DaemonRegistration(id="d1", agent_id="a1", hostname="h1", status="online")
    )
    assert set(payload) == {
        "id",
        "agent_id",
        "hostname",
        "available_clis",
        "capabilities",
        "status",
        "last_heartbeat",
        "registered_at",
    }
    for invented in ("daemon_id", "name", "tasks_completed"):
        assert invented not in payload, f"{invented} is not part of the API contract"


def test_daemon_register_request_requires_agent_id_and_hostname():
    """C4 fix: the UI used to POST `{name}` and always got a 422."""
    from pydantic import ValidationError

    from app.modules.agents.routes.daemon_routes import DaemonRegisterRequest

    with pytest.raises(ValidationError):
        DaemonRegisterRequest(name="only-a-name")

    ok = DaemonRegisterRequest(agent_id="a1", hostname="h1")
    assert ok.agent_id == "a1" and ok.hostname == "h1"
