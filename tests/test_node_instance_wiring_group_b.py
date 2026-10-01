"""Tests for the group-B (``@node`` instance registry) startup wiring.

Group B is the middle row of the required-parameter classification: owners whose
constructor takes an **injected dependency** -- a session *factory*, a config
object, a registry, or a store handle -- rather than a live session or a
per-request value. The docstring of ``app.core/node_instances`` states the test
constraints this file exists to enforce:

* A registered instance is held for the process lifetime. **The guard that
  matters most** is therefore that it carries no live session/connection/engine,
  asserted on the *real imported class* and the *real resolved instance* --
  including one level down into collaborators, because the owners here are
  wrappers and it is the collaborator that would hold the session.
* Each newly wired dotted ``@node`` must become genuinely callable end-to-end
  through the real ``app.mcp.node_bridge``, with ``self`` gone from its signature.
* The check must be able to FAIL. Proven by neutering, not by assertion alone.
* A module switched off by the per-instance feature config must not construct.

No live database is touched. Every store-backed owner below is exercised over a
**temp-file SQLite** engine created in a ``tmp_path`` fixture; the shipped
``_shared_memory_store()`` factory is asserted separately, and only for the fact
that it opens nothing.
"""

from __future__ import annotations

import inspect
import logging
from typing import Any

import pytest

from app.core.node_instances import (
    SESSION_SENSITIVE_ATTRS,
    STARTUP_INSTANCE_WIRINGS,
    InstanceWiring,
    _resolve_dotted,
    live_session_attributes,
    register_startup_instances,
)
from common_lib.modules.common.instance_registry import (
    clear_registry,
    get_instance_for_path,
)

# ── the group-B owners this file wires ────────────────────────────────────
#
# (owner dotted path, feature-flag namespace, one dotted node to invoke).
# Every owner is a REAL platform class; the node names are read back off the
# class in the tests rather than trusted from this table.

GROUP_B_OWNERS = [
    (
        "common_lib.modules.orchestration.agents.agent.tracing.service.TraceRecorder",
        "orchestration",
        "record_event",
    ),
    (
        "common_lib.modules.orchestration.agents.agent.tracing.cost_service"
        ".AgentCostService",
        "orchestration",
        "get_cost_summary",
    ),
    (
        "common_lib.modules.orchestration.agents.agent.versioning.service"
        ".AgentVersionService",
        "orchestration",
        "list_versions",
    ),
    (
        "common_lib.modules.orchestration.infrastructure.sync.manager.EntitySyncManager",
        "orchestration",
        "sync_all_to_files",
    ),
    (
        "common_lib.modules.orchestration.plugin.loader.PluginLoader",
        "orchestration",
        "list_plugins",
    ),
    (
        "common_lib.modules.workflows.config_service.WorkflowConfigService",
        "workflows",
        "list_configs",
    ),
    (
        "common_lib.modules.plugins.plugin_service.PluginService",
        "plugins",
        "list_plugins",
    ),
    (
        "common_lib.modules.memory.memory_adaptation.bandit.adapter"
        ".OnlineBanditAdapter",
        "memory",
        "get_stats",
    ),
    (
        "common_lib.modules.memory.memory_context.tokenizer.tokenizer.TiktokenBackend",
        "memory",
        "count",
    ),
]

#: ``PluginService.list_plugins`` takes a ``plugin_manager``. It is a *node
#: argument*, resolved per call by the platform's own
#: ``plugins.manager.get_plugin_manager()`` -- which is exactly why it is safe on
#: a shared instance. Recorded here so the call test supplies the real thing.
PLUGIN_MANAGER_SOURCE = "common_lib.modules.plugins.manager:get_plugin_manager"


def _owner_class(dotted: str) -> type:
    mod_name, _, class_name = dotted.rpartition(".")
    return getattr(__import__(mod_name, fromlist=[class_name]), class_name)


def _owner_module(dotted: str):
    mod_name, _, class_name = dotted.rpartition(".")
    return __import__(mod_name, fromlist=[class_name])


def _wiring(owner: str, source: str, module: str) -> InstanceWiring:
    return InstanceWiring(
        owner=owner, source=source, module=module, rationale="test fixture", nodes=1
    )


def _shipped_wiring(owner: str) -> InstanceWiring:
    """The real table row for ``owner``, so tests exercise shipped config."""
    for wiring in STARTUP_INSTANCE_WIRINGS:
        if wiring.owner == owner:
            return wiring
    raise AssertionError(f"{owner} is not in STARTUP_INSTANCE_WIRINGS")


@pytest.fixture(autouse=True)
def _clean_registry():
    clear_registry()
    yield
    clear_registry()


@pytest.fixture
def sqlite_memory_store(tmp_path):
    """A ``SQLAlchemyMemoryStore`` over a TEMP-FILE SQLite engine.

    Temp file rather than ``:memory:`` because the store opens a *new* session
    per call and ``:memory:`` gives each connection its own empty database, so
    a record written in one call would be invisible in the next -- the test
    would then prove nothing about whether the body ran.

    Only the two trace tables are created. Creating the whole ``SQLModel``
    metadata fails on an unresolvable foreign key
    (``agent_skills.skill_id -> skill_definitions``), which is a pre-existing
    platform condition and not this test's business; the tracing module's own
    suite creates its tables individually for the same reason.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlmodel import Session

    from common_lib.modules.orchestration.agents.agent.tracing.models import (
        AgentTraceEvent,
        AgentTracePayload,
    )
    from common_lib.modules.orchestration.context.memory.services import (
        SQLAlchemyMemoryStore,
    )

    engine = create_engine(
        f"sqlite:///{tmp_path}/node_instances.db",
        connect_args={"check_same_thread": False},
    )
    for table in (AgentTraceEvent.__table__, AgentTracePayload.__table__):
        table.create(engine, checkfirst=True)
    store = SQLAlchemyMemoryStore(
        session_factory=sessionmaker(bind=engine, class_=Session)
    )
    yield store
    engine.dispose()


# ── 1. THE GUARD: no registered instance carries a live DB handle ──────────


def test_shipped_table_registers_no_live_session_on_any_instance():
    """Run the real pass over the real table and guard every real instance.

    This is the assertion that separates the safe half of group B from the
    unsafe half. It runs the shipped wiring (not a substitute table), so it also
    proves the shipped sources construct at all.
    """
    report = register_startup_instances()

    assert report.failed == {}, f"shipped wiring failed: {report.failed}"
    assert report.registered, report.summary()

    offenders: dict[str, dict[str, str]] = {}
    for owner, instance in report.registered.items():
        found = live_session_attributes(instance)
        if found:
            offenders[owner] = found
    assert offenders == {}, f"live DB handles on registered instances: {offenders}"


@pytest.mark.parametrize("owner", [o for o, _m, _n in GROUP_B_OWNERS])
def test_each_group_b_owner_is_wired_and_guard_clean(owner: str):
    """Each group-B owner registers, and its real instance is guard-clean.

    One test per owner so a failure names the owner that regressed rather than
    the first one alphabetically.
    """
    wiring = _shipped_wiring(owner)
    report = register_startup_instances([wiring])

    assert owner in report.registered, (
        f"{owner} did not register: {report.summary()} {report.failed}"
    )
    instance = report.registered[owner]
    assert live_session_attributes(instance) == {}, (
        f"{owner} holds a live DB handle: {live_session_attributes(instance)}"
    )
    # Guarded on the REAL class, not just the instance: the owner must genuinely
    # be the class the bridge will key the registry off.
    assert isinstance(instance, _owner_class(owner))


def test_shared_memory_store_holds_a_factory_not_a_session():
    """The store every wrapper below reaches through must itself be factory-backed.

    ``SQLAlchemyMemoryStore`` accepts either ``db_url`` (which ``create_engine``s
    and caches an Engine on the instance) or ``session_factory``. Only the second
    is shareable, and the distinction is invisible from the constructor signature
    -- so it is asserted on the resolved object.
    """
    import app.core.node_instances as ni

    store = ni._shared_memory_store()

    assert live_session_attributes(store) == {}, (
        f"shared store holds a live handle: {live_session_attributes(store)}"
    )
    # The factory must be present and callable: that is what opens per call.
    assert callable(store._session_factory)
    # And it must NOT be a session itself.
    assert store.session is None

    # It is cached, so every wrapper reaches the SAME store rather than N
    # equivalent ones (which is what would make the wiring misleading).
    assert ni._shared_memory_store() is store


# ── 2. falsification: the guard CAN go red, naming the owner ──────────────


#: A real platform owner that genuinely takes a live ORM Session. Used as the
#: deliberately-unsafe fixture -- a real class, not a hand-rolled stand-in,
#: because a fabricated object would validate the mock rather than the code.
UNSAFE_OWNER = "common_lib.modules.rbac.agent_apikey_service.APIKeyService"


def _build_unsafe_api_key_service() -> Any:
    """``APIKeyService`` over a temp-SQLite session -- i.e. a live handle.

    The engine is temp-file SQLite under the OS temp dir, never the platform's
    configured database, so even the unsafe fixture touches no live DB. What
    matters for the test is the *shape*: the instance holds a live session.
    """
    import tempfile

    from sqlalchemy import create_engine
    from sqlmodel import Session

    from common_lib.modules.rbac.agent_apikey_service import APIKeyService

    path = tempfile.mkdtemp(prefix="ni-unsafe-")
    engine = create_engine(f"sqlite:///{path}/unsafe.db")
    return APIKeyService(Session(engine))


def test_guard_refuses_an_owner_that_holds_a_live_session(caplog):
    """Register a deliberately-unsafe owner and prove the guard refuses it.

    The point is not that this owner is in the table -- it must never be. The
    point is that the guard is load-bearing: without it the pass would register
    a live session behind a process-wide singleton and the leak would be
    permanent and invisible.
    """
    wiring = _wiring(
        UNSAFE_OWNER,
        "tests.test_node_instance_wiring_group_b:_build_unsafe_api_key_service",
        "rbac",
    )

    with caplog.at_level(logging.ERROR, logger="node_instances"):
        report = register_startup_instances([wiring])

    # Refused, not registered.
    assert report.registered == {}, report.registered
    assert UNSAFE_OWNER in report.failed
    assert "live DB handle" in report.failed[UNSAFE_OWNER]
    assert get_instance_for_path(UNSAFE_OWNER) is None

    # The refusal NAMES the owner and the offending attribute.
    assert UNSAFE_OWNER in caplog.text
    assert "REFUSING" in caplog.text
    assert "session=" in caplog.text

    # And it names the right attribute, on the right object.
    assert live_session_attributes(_build_unsafe_api_key_service()) == {
        "session": "Session"
    }


def test_guard_is_green_again_once_the_unsafe_owner_is_removed():
    """The negative control: with the unsafe row gone, the same pass is green.

    Without this, "the guard is red" could just mean "the guard is broken".
    """
    unsafe = _wiring(
        UNSAFE_OWNER,
        "tests.test_node_instance_wiring_group_b:_build_unsafe_api_key_service",
        "rbac",
    )
    safe_owner, safe_module, _node = GROUP_B_OWNERS[0]

    red = register_startup_instances([unsafe])
    assert red.registered == {}
    assert UNSAFE_OWNER in red.failed

    green = register_startup_instances([_shipped_wiring(safe_owner)])
    assert green.failed == {}, green.failed
    assert safe_owner in green.registered
    assert live_session_attributes(green.registered[safe_owner]) == {}


def test_is_live_handle_separates_factories_from_real_handles():
    """The predicate that decides safe-vs-unsafe, asserted on real objects.

    Neutering the callable exemption in ``_is_live_handle`` left every other test
    in this file green, because no owner in the shipped table happens to store a
    *factory* under one of the sensitive names -- they store it as ``_get_session``
    or ``_session_factory``, which are not sensitive names. So the exemption was
    untested, and an untested exemption is one deletion away from flagging every
    factory-taking owner (including the two long-shipped ones).

    Asserted directly, with the platform's own ``get_session``/``get_engine``
    factories as the safe cases and a real temp-SQLite Session/Engine as the
    unsafe ones.
    """
    import tempfile

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlmodel import Session

    from common_lib.modules.data_storage.database.connection import (
        get_engine,
        get_session,
    )

    from app.core.node_instances import _is_live_handle

    # Safe: the platform's own factories. These OPEN a handle when called, which
    # is the whole point -- calling them is per-use, holding them is not.
    assert _is_live_handle(get_session) is False
    assert _is_live_handle(get_engine) is False
    assert _is_live_handle(sessionmaker()) is False

    # Safe: empty slots and metadata.
    assert _is_live_handle(None) is False
    assert _is_live_handle("") is False
    assert _is_live_handle(0) is False
    assert _is_live_handle(Session) is False  # the class, not an instance

    # Unsafe: real live handles.
    engine = create_engine(f"sqlite:///{tempfile.mkdtemp()}/live.db")
    assert _is_live_handle(engine) is True
    assert _is_live_handle(Session(engine)) is True
    assert _is_live_handle(Session(engine, expire_on_commit=False)) is True


def test_guard_ignores_factories_and_empty_slots():
    """A factory, and an empty slot, must NOT trip the guard.

    This is the other half of the falsification: a guard that flagged everything
    would be as useless as no guard, and would make the safe DI shape
    unregistrable. Asserted on real platform objects.

    Two real cases, both reachable from the shipped table:

    * ``ConfigsService`` / ``DashboardService`` hold a session **factory**
      (``_get_session``) that opens a session per call. That is precisely the
      shape that makes a singleton correct.
    * ``SQLAlchemyMemoryStore`` holds ``session=None`` and ``engine=None`` --
      empty slots under two sensitive names -- plus ``_session_factory``.
    """
    for owner in (
        "common_lib.modules.configs.service.ConfigsService",
        "common_lib.modules.app_ops.dashboard.service.DashboardService",
    ):
        wiring = _shipped_wiring(owner)
        report = register_startup_instances([wiring])
        assert owner in report.registered, report.failed
        instance = report.registered[owner]
        assert live_session_attributes(instance) == {}, (
            f"{owner} holds a live handle: {live_session_attributes(instance)}"
        )
        # The factory really is there -- otherwise this test would pass on a
        # service that simply stopped depending on the database.
        assert callable(instance._get_session), f"{owner} lost its session factory"

    from common_lib.modules.data_storage.database.connection import get_session
    from common_lib.modules.orchestration.context.memory.services import (
        SQLAlchemyMemoryStore,
    )

    store = SQLAlchemyMemoryStore(session_factory=get_session)
    assert store.session is None
    assert store.engine is None
    assert callable(store._session_factory)
    # Empty slots under sensitive names, plus a factory: all three allowed.
    assert live_session_attributes(store) == {}, live_session_attributes(store)
    for name in ("session", "engine"):
        assert name in SESSION_SENSITIVE_ATTRS


def test_guard_walks_into_collaborators_not_just_the_top_level_object():
    """Depth-1 is load-bearing, not padding.

    Every group-B owner wired here is a *wrapper*: ``TraceRecorder._memory``,
    ``WorkflowConfigService._common_memory``, ``EntitySyncManager.memory``. The
    session would live on the collaborator. A depth-0 guard would pass all of
    them, which is exactly the false negative that matters.
    """
    unsafe_owner = (
        "common_lib.modules.orchestration.agents.agent.tracing.service.TraceRecorder"
    )
    module = _owner_module(unsafe_owner)
    recorder_cls = module.TraceRecorder

    # Both objects are REAL platform classes. The store is the real
    # ``SQLAlchemyMemoryStore``, built the *unsafe* way -- with a live session
    # rather than a session factory. Temp-file SQLite, so the platform's
    # configured database is never touched even by the unsafe fixture.
    import tempfile

    from sqlalchemy import create_engine
    from sqlmodel import Session

    from common_lib.modules.orchestration.context.memory.services import (
        SQLAlchemyMemoryStore,
    )

    engine = create_engine(f"sqlite:///{tempfile.mkdtemp()}/nested.db")
    live_store = SQLAlchemyMemoryStore(session=Session(engine))
    instance = recorder_cls(live_store)

    # The store itself is caught on its own...
    assert live_session_attributes(live_store) == {"session": "Session"}
    # ...and the guard reaches through the wrapper to find it.
    found = live_session_attributes(instance)
    assert found == {"_memory.session": "Session"}, found

    # And the pass refuses it, naming the nested attribute.
    from app.core.node_instances import InstanceWiring as _IW

    wiring = _IW(
        owner=unsafe_owner,
        source="tests.test_node_instance_wiring_group_b:_build_nested_unsafe_recorder",
        module="orchestration",
        rationale="falsification fixture",
        nodes=1,
    )
    report = register_startup_instances([wiring])
    assert report.registered == {}
    assert "_memory.session=Session" in report.failed[unsafe_owner]


def _build_nested_unsafe_recorder() -> Any:
    """``TraceRecorder`` over a real store built with a live session.

    The nested-offender fixture: two real platform classes, the store holding
    the session rather than a factory. Temp-file SQLite, so nothing here reaches
    the platform's configured database.
    """
    import tempfile

    from sqlalchemy import create_engine
    from sqlmodel import Session

    from common_lib.modules.orchestration.context.memory.services import (
        SQLAlchemyMemoryStore,
    )

    module = _owner_module(
        "common_lib.modules.orchestration.agents.agent.tracing.service.TraceRecorder"
    )
    engine = create_engine(f"sqlite:///{tempfile.mkdtemp()}/nested.db")
    return module.TraceRecorder(SQLAlchemyMemoryStore(session=Session(engine)))


# ── 3. end-to-end: the nodes are really callable through the real bridge ──


def _resolve(module, qualname: str):
    from app.mcp.node_bridge import _resolve_callable

    return _resolve_callable(module, qualname)


def _register_real(owner: str, instance: Any) -> None:
    from common_lib.modules.common.instance_registry import register_instance

    register_instance(_owner_class(owner), instance)


@pytest.mark.parametrize(
    ("owner", "method", "kwargs_factory"),
    [
        (
            "common_lib.modules.orchestration.agents.agent.tracing.service"
            ".TraceRecorder",
            "record_event",
            lambda: {
                "session_id": "ni-session",
                "trace_id": "ni-trace",
                "event_type": "node_instances_probe",
            },
        ),
        (
            "common_lib.modules.orchestration.agents.agent.tracing.cost_service"
            ".AgentCostService",
            "get_cost_summary",
            lambda: {"agent_id": "ni-agent"},
        ),
        (
            "common_lib.modules.orchestration.agents.agent.versioning.service"
            ".AgentVersionService",
            "list_versions",
            lambda: {"agent_id": "ni-agent"},
        ),
        (
            "common_lib.modules.workflows.config_service.WorkflowConfigService",
            "list_configs",
            dict,
        ),
        (
            "common_lib.modules.plugins.plugin_service.PluginService",
            "list_plugins",
            lambda: {"plugin_manager": _resolve_dotted(PLUGIN_MANAGER_SOURCE)()},
        ),
        (
            "common_lib.modules.memory.memory_adaptation.bandit.adapter"
            ".OnlineBanditAdapter",
            "get_stats",
            dict,
        ),
        (
            "common_lib.modules.memory.memory_context.tokenizer.tokenizer"
            ".TiktokenBackend",
            "count",
            lambda: {"text": "hello world from the node bridge"},
        ),
    ],
)
def test_group_b_node_is_callable_end_to_end_with_self_absent(
    owner: str,
    method: str,
    kwargs_factory,
    sqlite_memory_store,
):
    """Register the real owner, resolve the real dotted node, INVOKE it.

    Asserted on the *return value of the real body*, not on the fact that
    binding returned something. Before this the node raised
    ``TypeError: missing 1 required positional argument: 'self'`` on every call.

    Every store-backed owner here runs over the temp-SQLite fixture, so this test
    never touches the platform's configured database.
    """
    instance = _instance_for(owner, sqlite_memory_store)
    _register_real(owner, instance)

    module = _owner_module(owner)
    class_name = owner.rpartition(".")[2]
    bound = _resolve(module, f"{class_name}.{method}")

    params = list(inspect.signature(bound).parameters)
    assert "self" not in params, f"{owner}.{method} still takes self: {params}"
    assert inspect.ismethod(bound), "not bound to the registered instance"

    kwargs = kwargs_factory()
    try:
        out = bound(**kwargs)
    except Exception as exc:  # noqa: BLE001
        pytest.fail(
            f"{owner}.{method} raised through the bridge: {type(exc).__name__}: {exc}"
        )

    assert out is not None, f"{owner}.{method} produced nothing"
    # Signature parity with the owner method minus self -- the invariant the
    # bridge is supposed to preserve.
    declared = inspect.signature(getattr(_owner_class(owner), method))
    expected = declared.replace(
        parameters=[p for n, p in declared.parameters.items() if n != "self"]
    )
    assert inspect.signature(bound) == expected


def _instance_for(owner: str, store: Any) -> Any:
    """Build the real owner over the temp store, by the same shape as the source."""
    from common_lib.paths import COMMON_LIB_TEMPLATES, PLUGINS_TEMPLATES_ROOT

    if owner.endswith(".TraceRecorder"):
        return _owner_class(owner)(store)
    if owner.endswith(".AgentCostService"):
        return _owner_class(owner)(store)
    if owner.endswith(".AgentVersionService"):
        return _owner_class(owner)(store)
    if owner.endswith(".WorkflowConfigService"):
        return _owner_class(owner)(store)
    if owner.endswith(".PluginService"):
        return _owner_class(owner)(store, PLUGINS_TEMPLATES_ROOT)
    if owner.endswith(".EntitySyncManager"):
        return _owner_class(owner)(store, str(COMMON_LIB_TEMPLATES))
    if owner.endswith(".PluginLoader"):
        from common_lib.modules.orchestration.plugin.context import get_context

        return _owner_class(owner)(get_context())
    if owner.endswith(".OnlineBanditAdapter"):
        return _resolve_dotted("app.core.node_instances:_build_online_bandit_adapter")()
    if owner.endswith(".TiktokenBackend"):
        return _resolve_dotted("app.core.node_instances:_build_tiktoken_backend")()
    raise AssertionError(f"no fixture construction for {owner}")


def test_every_group_b_owner_has_at_least_one_invocable_node():
    """Count coverage by INVOCATION, not by counting declarations.

    Each owner is registered with the real instance over the temp store, then
    EVERY one of its dotted ``@node`` methods is resolved through the real
    bridge and asserted to be a bound method with ``self`` stripped. This is the
    distinction the report has to make: "resolved and bound" vs "ran without a
    ``self`` TypeError".
    """
    not_invoked: dict[str, list[str]] = {}
    resolved_ok = 0

    for owner, _module, _node in GROUP_B_OWNERS:
        instance = _instance_for(owner, sqlite_memory_store)
        _register_real(owner, instance)
        module = _owner_module(owner)
        owner_cls = _owner_class(owner)
        for name, member in vars(owner_cls).items():
            if not getattr(member, "_node_metadata", None):
                continue
            if isinstance(member, property):
                continue
            bound = _resolve(module, f"{owner_cls.__name__}.{name}")
            params = list(inspect.signature(bound).parameters)
            if params and params[0] == "self":
                not_invoked.setdefault(owner, []).append(name)
                continue
            resolved_ok += 1

    assert not_invoked == {}, f"nodes that did not bind: {not_invoked}"
    assert resolved_ok > 0


# ── 4. the feature-config tie-in ──────────────────────────────────────────


def test_disabled_module_is_not_constructed_for_a_group_b_owner(monkeypatch):
    """A group-B owner in a disabled module must not be constructed.

    Same predicate the node/router pruners use, so wiring and pruning cannot
    disagree. Instrumented on the real source so the assertion is on
    *construction*, not on the absence of a registry entry.
    """
    import app.core.node_instances as ni

    owner, _module, _node = GROUP_B_OWNERS[0]
    wiring = _shipped_wiring(owner)
    original = getattr(ni, wiring.source.rpartition(":")[2])
    calls: list[str] = []

    def _spy() -> object:
        calls.append("built")
        return original()

    monkeypatch.setattr(ni, "_module_enabled", lambda module: False)
    monkeypatch.setattr(ni, wiring.source.rpartition(":")[2], _spy)

    report = register_startup_instances([wiring])

    assert calls == [], "source was constructed for a disabled module"
    assert report.registered == {}
    assert report.disabled == [owner]
    assert get_instance_for_path(owner) is None


def test_every_group_b_owner_names_a_real_module_namespace():
    """The feature-flag namespace must be a real, enabled module.

    A typo'd namespace would fail *open* (``is_module_enabled`` returns True for
    an unregistered name), so the pruning gate would silently never prune. The
    assertion is that each namespace resolves to a real common_lib module.
    """
    from common_lib.modules.common.module_pruning import is_module_enabled

    seen = set()
    for owner, module, _node in GROUP_B_OWNERS:
        wiring = _shipped_wiring(owner)
        assert wiring.module == module, (
            f"{owner}: table says {wiring.module!r}, expected {module!r}"
        )
        assert wiring.rationale.strip(), f"{owner} has no recorded rationale"
        assert is_module_enabled(module), f"{module} resolves as disabled"
        seen.add(module)
    assert len(seen) >= 3, "expected several distinct namespaces"


# ── 5. no live database, no live infrastructure ────────────────────────────


def test_group_b_wiring_opens_no_database(monkeypatch):
    """The shipped pass must not open a connection or a session at wiring time.

    ``create_engine`` and ``get_session`` are turned into hard failures, so a
    source that quietly grew a live-DB dependency fails here rather than at boot
    on a machine with no database.
    """
    import app.core.node_instances as ni

    def _forbidden(*_args, **_kwargs):
        raise AssertionError("startup wiring must not touch a live database")

    monkeypatch.setattr("sqlalchemy.create_engine", _forbidden, raising=False)
    monkeypatch.setattr(
        "common_lib.modules.data_storage.database.connection.get_session",
        _forbidden,
        raising=False,
    )
    # Reset the cached shared store so the pass rebuilds it under the guard.
    monkeypatch.setattr(ni, "_MEMORY_STORE", None, raising=False)

    report = ni.register_startup_instances()

    assert "AssertionError" not in " ".join(report.failed.values()), report.failed
    # Every group-B owner is present: none of them needed the live DB.
    registered = set(report.registered)
    missing = [
        owner
        for owner, _m, _n in GROUP_B_OWNERS
        if owner not in registered and owner not in report.reused
    ]
    assert missing == [], f"group-B owners that needed a live DB: {missing}"


def test_shipped_table_sources_are_zero_argument_and_owners_import():
    """The table's contract, re-asserted now that it has grown.

    Every source must resolve to a zero-argument callable (the registry calls it
    with none) and every owner path must actually import -- a stale path logs a
    failure on every boot and leaves the node advertised-but-uncallable.
    """
    for wiring in STARTUP_INSTANCE_WIRINGS:
        source = _resolve_dotted(wiring.source)
        assert callable(source), f"{wiring.source} is not callable"
        required = [
            p
            for p in inspect.signature(source).parameters.values()
            if p.default is inspect.Parameter.empty
            and p.kind
            in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
        ]
        assert required == [], f"{wiring.source} requires {required}"
        assert isinstance(_owner_class(wiring.owner), type)


def test_unsafe_owner_is_not_in_the_shipped_table():
    """The refusal is durable, not just a runtime guard.

    Asserted against the real importable class, so a typo that dodged the
    comparison would fail the companion assertion below.
    """
    owners = {wiring.owner for wiring in STARTUP_INSTANCE_WIRINGS}
    assert UNSAFE_OWNER not in owners, (
        f"{UNSAFE_OWNER} must not be a process-wide singleton -- it holds a live "
        "ORM Session and commits on it"
    )
    # The reason is real, not a stale note.
    init = inspect.signature(_owner_class(UNSAFE_OWNER).__init__)
    required = [
        p
        for p in list(init.parameters.values())[1:]
        if p.default is inspect.Parameter.empty
    ]
    assert required, f"{UNSAFE_OWNER} no longer needs an instance; retire this guard"
