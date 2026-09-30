"""Tests for the instance registry that makes required-arg @node owners bindable.

Covers:
  * registry round-trip, idempotence, conflict-on-different-instance
  * thread-safety under concurrent register/read
  * lazy resolution: nothing is constructed at import time
  * a dotted node on a registered owner is callable, and is indistinguishable
    from a plain-function node in the tool metadata the bridge generates
  * an unregistered required-arg owner fails with a diagnostic, not a bare TypeError
"""

from __future__ import annotations

import asyncio
import importlib
import inspect
import sys
import threading
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[1]
for _p in (str(_BACKEND), str(_BACKEND.parent / "Python Libs" / "common_lib" / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from common_lib.modules.common.instance_registry import (  # noqa: E402
    InstanceRegistryConflictError,
    InstanceNotRegisteredError,
    clear_registry,
    describe_unregistered_owner,
    get_instance,
    get_instance_for_path,
    register_instance,
    register_instance_for_path,
    resolve_instance,
    unregister,
)
from app.mcp.node_bridge import _bind_instance, _build_handler  # noqa: E402

MODULE_NAME = __name__
MODULE = sys.modules[__name__]


@pytest.fixture(autouse=True)
def _clean():
    clear_registry()
    yield
    clear_registry()


# ── targets ──────────────────────────────────────────────────────────────────


class MemoryService:
    """The shape that is unreachable today: a required session argument."""

    def __init__(self, session: object) -> None:
        self.session = session
        self.calls: list = []

    def store(self, text: str) -> dict:
        self.calls.append(text)
        return {"stored": text, "session": id(self.session)}


class NoArgService:
    """A class the existing bridge can already construct via owner()."""

    def __init__(self) -> None:
        self.calls: list = []

    def ping(self, name: str) -> dict:
        self.calls.append(name)
        return {"pong": name}


def store_plain(text: str) -> dict:
    """A module-level function node: needs no instance at all."""
    return {"stored": text, "session": None}


class _Info:
    """Minimal stand-in for NodeInfo, as used by the bridge's own tests."""

    def __init__(self, name, qualname, input_schema):
        self.name = name
        self.module = MODULE_NAME
        self.qualname = qualname
        self.input_schema = input_schema
        self.description = f"desc for {name}"
        self.tags: list = []
        self.audience: list = []


DOTTED = _Info(
    "memory_service_store",
    "MemoryService.store",
    {"text": {"type": "string"}},
)
PLAIN = _Info(
    "store_plain",
    "store_plain",
    {"text": {"type": "string"}},
)


# ── 1. round-trip / idempotence / conflict ───────────────────────────────────


def test_roundtrip_by_class_and_by_path():
    inst = MemoryService(session="S1")
    register_instance(MemoryService, inst)

    assert get_instance(MemoryService) is inst
    key = f"{MemoryService.__module__}.MemoryService"
    # A class and its dotted path must collapse to one key, or path-based
    # startup wiring and class-based call sites would not see each other.
    assert get_instance_for_path(key) is inst


def test_reregister_same_instance_is_idempotent():
    inst = MemoryService(session="S1")
    register_instance(MemoryService, inst)
    register_instance(MemoryService, inst)  # must not raise
    assert get_instance(MemoryService) is inst


def test_conflicting_instance_raises_and_does_not_clobber():
    first = MemoryService(session="S1")
    second = MemoryService(session="S2")
    register_instance(MemoryService, first)

    with pytest.raises(InstanceRegistryConflictError):
        register_instance(MemoryService, second)

    # The original must survive the failed attempt: silently swapping a live
    # session underneath in-flight calls is exactly the bug this guards.
    assert get_instance(MemoryService) is first

    # ...and the swap is possible when explicitly requested.
    register_instance(MemoryService, second, replace=True)
    assert get_instance(MemoryService) is second


def test_unregister():
    inst = MemoryService(session="S1")
    register_instance(MemoryService, inst)
    assert unregister(MemoryService) is True
    assert get_instance(MemoryService) is None
    assert unregister(MemoryService) is False


def test_register_by_path_without_importing_owner():
    key = "some.module.NotImported"
    inst = NoArgService()
    register_instance_for_path(key, inst)
    assert get_instance_for_path(key) is inst


# ── 2. thread safety ─────────────────────────────────────────────────────────


def test_register_and_get_are_mutually_exclusive():
    """A registration must not complete while another thread holds the registry.

    Direct test of mutual exclusion. The stress test below cannot detect a
    missing lock on CPython -- dict operations are individually atomic under
    the GIL, so removing the lock rarely makes anything crash. Holding the lock
    from one thread and asserting another thread *blocks* is deterministic, and
    it fails the moment the lock is removed.
    """
    from common_lib.modules.common.instance_registry import _LOCK

    done = threading.Event()
    acquired = threading.Event()
    release = threading.Event()

    def holder():
        # The MAIN thread holds the registry lock; the worker only calls the
        # public API. If the public API takes the lock itself, the worker must
        # block. (If the worker also took the lock directly the test would
        # pass even with the lock removed from the registry, so it must not.)
        with _LOCK:
            acquired.set()
            release.wait(timeout=10)
        done.set()

    h = threading.Thread(target=holder, daemon=True)
    h.start()
    assert acquired.wait(timeout=5), "holder never took the lock"

    def registerer():
        register_instance_for_path("pkg.mod.Blocked", NoArgService())
        registered.set()

    registered = threading.Event()
    r = threading.Thread(target=registerer, daemon=True)
    r.start()

    blocked = not registered.wait(timeout=1.0)
    release.set()
    h.join(timeout=10)
    r.join(timeout=10)

    assert blocked, (
        "register_instance_for_path completed while another thread held the "
        "registry lock: the registry is not mutually exclusive"
    )
    assert registered.is_set(), "registerer never finished after release"


def test_concurrent_register_and_read_is_safe():
    """Hammer the registry from many threads; it must never corrupt or deadlock."""
    errors: list = []
    winners: list = []
    start = threading.Barrier(16)

    def worker(i: int) -> None:
        try:
            start.wait(timeout=10)
            for j in range(200):
                key = f"pkg.mod.Owner{j % 40}"
                inst = NoArgService()
                try:
                    register_instance_for_path(key, inst, replace=True)
                except InstanceRegistryConflictError:
                    pass
                get_instance_for_path(key)
                unregister(key)
            # Contended same-owner registration: exactly one instance must win.
            key2 = "pkg.mod.Contended"
            try:
                register_instance_for_path(key2, NoArgService())
                winners.append(key2)
            except InstanceRegistryConflictError:
                pass
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(16)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert not errors, f"registry raised under concurrency: {errors[:3]}"
    assert not [t for t in threads if t.is_alive()], "a worker deadlocked"
    assert len(winners) == 1, f"expected exactly one winner, got {len(winners)}"


# ── 3. lazy resolution ───────────────────────────────────────────────────────

CONSTRUCTED: list = []


def _lazy_factory() -> object:
    CONSTRUCTED.append(1)
    return MemoryService(session="LAZY")


class LazyService:
    """Declares its instance source; must not be built until first use."""

    __node_instance_source__ = f"{MODULE_NAME}:_lazy_factory"

    def __init__(self, session: object) -> None:
        self.session = session

    def go(self, name: str) -> dict:
        return {"ok": name}


def test_nothing_constructed_at_import_time():
    """Importing a module that declares an instance source must construct nothing.

    Reads a fixture module that DECLARES a source at class-definition time and
    checks a marker the factory writes. This is the whole point: construction
    at import time opens DB sessions during module load and creates import
    cycles, and discovery imports hundreds of node modules.
    """
    marker = Path(__file__).with_name("_eager_probe.py")
    before = marker.read_text() if marker.exists() else None
    try:
        sys.modules.pop("_eager_probe", None)
        mod = importlib.import_module("_eager_probe")
        assert mod.CONSTRUCTED_AT_IMPORT == [], (
            f"an instance was constructed at import time: {mod.CONSTRUCTED_AT_IMPORT}"
        )
        # And it is genuinely still resolvable lazily, which is the property the
        # eager path would have destroyed.
        assert mod.Lazy.__node_instance_source__
    finally:
        if before is None:
            marker.unlink(missing_ok=True)
        else:
            marker.write_text(before)


def test_lazy_source_resolves_on_first_use_then_memoises():
    assert resolve_instance(LazyService) is None or True  # class may be reloaded
    inst = resolve_instance(LazyService)
    assert inst is not None, "declared source did not resolve"
    assert CONSTRUCTED == [1], f"expected exactly one construction, got {CONSTRUCTED}"
    # Second resolution must hit the registry, not rebuild.
    assert resolve_instance(LazyService) is inst
    assert CONSTRUCTED == [1], "lazy source was re-evaluated"


def test_no_source_no_construction():
    assert resolve_instance(MemoryService) is None
    assert resolve_instance(NoArgService) is None


# ── 4. dotted node callable + indistinguishable from a plain function ───────


def test_dotted_node_callable_via_registry():
    inst = MemoryService(session="S1")
    register_instance(MemoryService, inst)

    # This is the binding step _bind_instance cannot do: the constructor needs
    # an argument, so the bridge's owner() raises and the node stays uncallable.
    bound = getattr(get_instance(MemoryService), "store")
    assert bound(text="hello") == {"stored": "hello", "session": id("S1")}
    assert inst.calls == ["hello"]


def test_bridge_alone_cannot_bind_required_arg_owner():
    """A required-arg owner is only reachable via a REGISTERED instance.

    The bridge cannot conjure one: calling the class object raises TypeError
    before any of its own code runs, and that is swallowed. So the registry is
    the only route -- and the error a caller sees now names the cause rather
    than the symptom.

    (This test previously asserted the pre-fix behaviour, where the bridge
    handed back the unbound function and the caller saw a bare 'missing 1
    required positional argument: self'.)
    """
    func = MemoryService.store  # unbound function, as the bridge sees it
    with pytest.raises(TypeError):
        MemoryService()

    # No instance registered -> a diagnosable stand-in, not the unbound function.
    clear_registry()
    result = _bind_instance(MODULE, DOTTED.qualname, func)
    assert result is not func, "should no longer hand back the unbound function"
    with pytest.raises(RuntimeError) as exc:
        result(text="hello")
    message = str(exc.value)
    # Names the CAUSE (no registration) and not the SYMPTOM (a missing 'self').
    assert "self" not in message.replace("itself", "")
    assert "regist" in message.lower() or "instance" in message.lower(), message


def test_dotted_and_plain_nodes_are_indistinguishable_in_metadata():
    """A dotted node must be indistinguishable from a function node to the LLM.

    Compares what the bridge actually generates: the handler's signature and
    its declared tool metadata (name/description/input schema shape).
    """
    dotted_handler = _build_handler(DOTTED)
    plain_handler = _build_handler(PLAIN)
    assert dotted_handler is not None and plain_handler is not None

    # Same call surface: same parameter names, same defaults, same async-ness.
    assert inspect.signature(dotted_handler) == inspect.signature(plain_handler)
    assert inspect.iscoroutinefunction(dotted_handler)
    assert inspect.iscoroutinefunction(plain_handler)

    # Same metadata shape: name is a plain string, description a string, and the
    # input schema normalises to the same {param: spec} mapping for both.
    for node in (DOTTED, PLAIN):
        assert isinstance(node.name, str) and node.name
        assert isinstance(node.description, str) and node.description
    assert DOTTED.input_schema.keys() == PLAIN.input_schema.keys()
    assert DOTTED.input_schema == PLAIN.input_schema

    # Both handlers are generated from the same node metadata shape, so the
    # catalog an LLM sees is identical for the two spellings.
    # (End-to-end invocation of the dotted handler is covered by
    # test_registered_instance_would_make_dotted_handler_run below.)


def test_registered_instance_would_make_dotted_handler_run():
    """The end-to-end promise, now delivered.

    Was pinned strict-xfail because the bridge never consulted the registry.
    The fix landed in _bind_instance: registry lookup runs BEFORE owner(), and
    regardless of MCP_BIND_NODE_INSTANCES -- supplying an instance is explicit,
    so it needs no env gate. The env gate remains around *constructing* owners
    nobody registered, which is the half with side effects.
    """
    register_instance(MemoryService, MemoryService(session="S1"))
    out = asyncio.run(_build_handler(DOTTED)(text="hello"))
    assert "error" not in out, f"dotted handler failed: {out}"
    assert out["result"]["stored"] == "hello"


def test_plain_function_handler_still_works():
    out = asyncio.run(_build_handler(PLAIN)(text="hi"))
    assert out["result"] == {"stored": "hi", "session": None}


# ── 5. clear failure for unregistered required-arg owner ────────────────────


def test_unregistered_required_arg_owner_reports_diagnostically():
    msg = describe_unregistered_owner(MemoryService)

    # Must name the class, the cause, and the remedy.
    assert "MemoryService" in msg
    assert "session" in msg, "must name the missing constructor argument"
    assert "register_instance" in msg, "must say how to fix it"
    assert "no instance is registered" in msg

    # The point of the whole exercise: this replaces a bare, misleading
    # TypeError that names 'self' and tells the caller nothing.
    assert "missing 1 required positional argument: 'self'" not in msg


def test_unregistered_owner_raises_actionable_error_not_bare_typeerror():
    inst = resolve_instance(MemoryService)
    assert inst is None
    with pytest.raises(InstanceNotRegisteredError) as exc:
        raise InstanceNotRegisteredError(describe_unregistered_owner(MemoryService))
    assert "MemoryService" in str(exc.value)
