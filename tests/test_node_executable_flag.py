"""Tests for the `executable` flag on @node.

WHAT IT IS FOR
--------------
`@node` marks a callable for DISCOVERY. Some declarations are worth discovering
— an agent can usefully read the contract — but have no implementation to
invoke. The clearest example found:

    @node(name="adapters.IDiscoverable.discover", ...)
    class IDiscoverable(ABC):
        @abstractmethod
        @node(name="adapters.IDiscoverable.discover", ...)
        def discover(self) -> list[EntityMetadata]:
            ...  # body is only a docstring, no implementation

That node was fully discoverable, advertised as a callable tool, and raised
``TypeError: missing 1 required positional argument: 'self'`` on every call —
while being an ABC whose method body is only a docstring.

DESIGN
------
``executable`` DEFAULTS TO True. Nodes declared before the flag existed carry
no such key and are treated as executable, so nothing needs migrating. Only
declarations that genuinely cannot be called are changed, to
``executable=False``.

The node stays discoverable. Only the invocation path changes: instead of a
cryptic TypeError, the caller is told plainly that it is a declaration and is
pointed at finding a concrete implementation.
"""

from __future__ import annotations

import asyncio

import pytest

from app.mcp.node_bridge import _build_handler
from common_lib.modules.plugins.node import node


class _Info:
    def __init__(self, name, qualname, input_schema, metadata=None):
        self.name = name
        self.module = __name__
        self.qualname = qualname
        self.input_schema = input_schema
        self.metadata = metadata or {}


# ── the flag itself ───────────────────────────────────────────────────────────


@node(name="probe.executable_default", description="no executable kwarg given")
def default_node(name: str = "x") -> dict:
    return {"ok": name}


@node(name="probe.executable_true", description="explicitly true", executable=True)
def explicit_true(name: str = "x") -> dict:
    return {"ok": name}


@node(name="probe.executable_false", description="a declaration", executable=False)
def declared_only(name: str = "x") -> dict:
    return {"ok": name}


def test_default_is_executable():
    """The whole point of defaulting to True: no migration."""
    assert default_node._node_metadata["executable"] is True


def test_explicit_true_is_executable():
    assert explicit_true._node_metadata["executable"] is True


def test_explicit_false_is_recorded():
    assert declared_only._node_metadata["executable"] is False


def test_metadata_key_always_present():
    """Consumers can rely on the key existing rather than using .get()."""
    for fn in (default_node, explicit_true, declared_only):
        assert "executable" in fn._node_metadata


# ── behaviour through the bridge ──────────────────────────────────────────────


def test_missing_metadata_key_treated_as_executable():
    """A node_info with NO metadata at all — the pre-flag shape."""
    handler = _build_handler(_Info("probe.legacy", "default_node", {}))
    assert asyncio.run(handler()) == {"result": {"ok": "x"}}


def test_executable_node_still_runs():
    handler = _build_handler(
        _Info("probe.ok", "explicit_true", {}, explicit_true._node_metadata)
    )
    assert asyncio.run(handler()) == {"result": {"ok": "x"}}


def test_non_executable_node_reports_clearly():
    handler = _build_handler(
        _Info("probe.decl", "declared_only", {}, declared_only._node_metadata)
    )
    result = asyncio.run(handler())
    assert result["error"] == "not executable"
    assert result["executable"] is False
    assert "declaration" in result["reason"]


def test_non_executable_node_does_not_raise_typeerror():
    """The old failure was `missing 1 required positional argument: 'self'`.

    A declaration must not produce that; it must say what it is.
    """
    handler = _build_handler(
        _Info("probe.decl2", "declared_only", {}, declared_only._node_metadata)
    )
    result = asyncio.run(handler())
    assert "positional argument" not in str(result.get("error", ""))


def test_non_executable_node_names_itself():
    handler = _build_handler(
        _Info(
            "adapters.IDiscoverable.discover",
            "declared_only",
            {},
            declared_only._node_metadata,
        )
    )
    result = asyncio.run(handler())
    assert "adapters.IDiscoverable.discover" in result["reason"]


def test_handler_is_still_built_for_a_declaration():
    """Discovery must keep working — the tool still appears in the list."""
    handler = _build_handler(
        _Info("probe.decl3", "declared_only", {}, declared_only._node_metadata)
    )
    assert handler is not None
