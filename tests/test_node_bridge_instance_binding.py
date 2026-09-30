"""Regression tests for binding unbound @node methods to an instance.

THE DEFECT
----------
``@node`` applied to a method of a class yields a plain function. The MCP bridge
resolved ``Class.method`` and called it as a bare function, so the first keyword
argument landed on ``self`` and the body never ran::

    DeduplicationService.__init__() got an unexpected keyword argument
    'notification_type'

Measured platform-wide before the fix: of 25 655 generated handlers, a 300-node
sample showed 156 raising ``TypeError: ... missing 1 required positional argument:
'self'`` — about 52%. Three independent module audits hit it (notification 202
nodes, observability 218, a 120-handler sample 58). Every one of those nodes is
decorated, discovered, listed in the registry and advertised to agents, and
uncallable.

Enabled by ``MCP_BIND_NODE_INSTANCES=1``, default OFF.
"""

from __future__ import annotations

import asyncio
import sys

import pytest

from app.mcp.node_bridge import (
    _bind_instance,
    _build_handler,
    _looks_unbound,
    _resolve_callable,
)

# _build_handler exec()s source that references the module BY NAME, so
# NodeInfo.module is a string. Direct helper calls take the module object.
MODULE_NAME = __name__
MODULE = sys.modules[__name__]


class _Info:
    def __init__(self, qualname, input_schema):
        self.module = MODULE_NAME
        self.qualname = qualname
        self.input_schema = input_schema


# ── targets ──────────────────────────────────────────────────────────────────


class Widget:
    """Takes no constructor arguments, so binding can succeed."""

    def __init__(self):
        self.calls: list[str] = []

    def ping(self, name: str) -> dict:
        self.calls.append(name)
        return {"pong": name}

    async def aping(self, name: str) -> dict:
        self.calls.append(f"async:{name}")
        return {"apong": name}


class NeedsArgs:
    """Constructor requires arguments, so binding must fail and fall back."""

    def __init__(self, required: str):
        self.required = required

    def ping(self, name: str) -> dict:
        return {"never": name}


class NotAClass:
    pass


def module_level(name: str) -> dict:
    """A plain function — the flag must leave it alone."""
    return {"ok": name}


def nested() -> dict:
    return {"ok": "nested"}


class Outer:
    class Inner:
        def __init__(self):
            pass

        def ping(self, name: str) -> dict:
            return {"inner": name}


def _enabled(monkeypatch, on: bool):
    if on:
        monkeypatch.setenv("MCP_BIND_NODE_INSTANCES", "1")
    else:
        monkeypatch.delenv("MCP_BIND_NODE_INSTANCES", raising=False)


# ── the detector ─────────────────────────────────────────────────────────────


def test_detects_unbound_methods():
    assert _looks_unbound(Widget.ping) is True
    assert _looks_unbound(NeedsArgs.ping) is True


def test_ignores_bound_methods_and_plain_functions():
    assert _looks_unbound(Widget().ping) is False, "already bound"
    assert _looks_unbound(module_level) is False
    assert _looks_unbound(nested) is False
    assert _looks_unbound("not callable") is False


# ── the binding ──────────────────────────────────────────────────────────────


def test_binds_unbound_method_to_a_new_instance(monkeypatch):
    _enabled(monkeypatch, True)
    bound = _resolve_callable(MODULE, "Widget.ping")
    assert bound(name="a") == {"pong": "a"}


def test_flag_off_preserves_the_old_unbound_call(monkeypatch):
    _enabled(monkeypatch, False)
    raw = _resolve_callable(MODULE, "Widget.ping")
    assert _looks_unbound(raw) is True
    with pytest.raises(TypeError):
        raw(name="a")


def test_plain_functions_are_untouched_by_the_flag(monkeypatch):
    _enabled(monkeypatch, True)
    assert _resolve_callable(MODULE, "module_level")(name="a") == {"ok": "a"}


def test_constructor_failure_falls_back_rather_than_raising(monkeypatch):
    """A class needing constructor args must not break the handler build.

    Falling back means the caller sees the pre-existing TypeError, not a new one.
    """
    _enabled(monkeypatch, True)
    resolved = _resolve_callable(MODULE, "NeedsArgs.ping")
    assert _looks_unbound(resolved) is True, "should have fallen back to unbound"


def test_unresolvable_qualname_still_raises_at_resolution(monkeypatch):
    """Binding happens AFTER resolution, so a target that does not exist fails
    in `_resolve_func` — which is pre-existing behaviour, unchanged by this
    flag. `_build_handler` catches it and returns None."""
    _enabled(monkeypatch, True)
    with pytest.raises(AttributeError):
        _resolve_callable(MODULE, "NoSuchClass.ping")
    # Resolution happens when the handler is CALLED, not when it is built, so the
    # tool still appears in the registry and reports the failure rather than
    # vanishing. That is pre-existing behaviour and is unchanged here.
    handler = _build_handler(_Info("NoSuchClass.ping", {}))
    assert handler is not None
    assert "error" in asyncio.run(handler())


def test_non_class_owner_is_not_instantiated(monkeypatch):
    """A dotted path whose owner is not a class must never be constructed."""
    _enabled(monkeypatch, True)
    with pytest.raises(AttributeError):
        _resolve_callable(MODULE, "nested.ping")


def test_nested_class_owner_is_resolved(monkeypatch):
    _enabled(monkeypatch, True)
    bound = _resolve_callable(MODULE, "Outer.Inner.ping")
    assert bound(name="a") == {"inner": "a"}


# ── end to end through the generated handler ─────────────────────────────────


def test_handler_call_succeeds_with_the_flag_on(monkeypatch):
    """The call that used to raise `missing ... argument 'self'`."""
    _enabled(monkeypatch, True)
    handler = _build_handler(_Info("Widget.ping", {"name": {"type": "string"}}))
    assert handler is not None
    assert asyncio.run(handler(name="hello")) == {"result": {"pong": "hello"}}


def test_async_method_call_succeeds_with_the_flag_on(monkeypatch):
    _enabled(monkeypatch, True)
    handler = _build_handler(_Info("Widget.aping", {"name": {"type": "string"}}))
    assert asyncio.run(handler(name="hello")) == {"result": {"apong": "hello"}}


def test_handler_still_builds_when_binding_is_impossible(monkeypatch):
    """Must degrade to today's behaviour, not fail the build."""
    _enabled(monkeypatch, True)
    handler = _build_handler(_Info("NeedsArgs.ping", {"name": {"type": "string"}}))
    assert handler is not None, "handler must still be built"
    result = asyncio.run(handler(name="x"))
    assert "error" in result, "should report the pre-existing failure shape"


def test_flag_off_is_byte_identical_to_previous_behaviour(monkeypatch):
    _enabled(monkeypatch, False)
    handler = _build_handler(_Info("Widget.ping", {"name": {"type": "string"}}))
    result = asyncio.run(handler(name="hello"))
    assert "error" in result
    assert "positional argument" in str(result.get("error", ""))


def test_bind_instance_is_a_noop_for_bound_methods():
    widget = Widget()
    assert _bind_instance(MODULE, "Widget.ping", widget.ping) == widget.ping
