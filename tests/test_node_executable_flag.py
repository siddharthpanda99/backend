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
import inspect

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


# ── regression: the flag must be read off a REAL NodeInfo, not a stand-in ────
#
# The tests above use `_Info`, a hand-rolled stand-in that carries `executable`
# inside `.metadata` and has no `.executable` attribute. Real `NodeInfo` is the
# opposite: `executable` is a dataclass FIELD, and `.metadata` holds only the
# inner user dict. So the fake validated itself while the real bridge silently
# read `metadata.get("executable")` -> None -> True for every node, and all 259
# markings were inert. These tests use real discovered nodes so that cannot
# happen again.


def test_real_nodeinfo_carries_executable_as_a_field_not_in_metadata():
    from common_lib.modules.plugins.nodes_registry import discover_nodes

    marked = [n for n in discover_nodes() if getattr(n, "executable", True) is False]
    assert marked, "expected the platform to have non-executable declarations"
    sample = marked[0]
    # The field is populated ...
    assert sample.executable is False
    # ... and metadata does NOT carry it. Reading metadata is the bug.
    assert "executable" not in sample.metadata, (
        "if metadata now carries the flag, this regression test is obsolete"
    )


def test_bridge_guard_fires_for_a_real_marked_node():
    """A marked node must return the guard, not a raw TypeError."""
    import asyncio

    from common_lib.modules.plugins.nodes_registry import discover_nodes

    marked = [n for n in discover_nodes() if getattr(n, "executable", True) is False]
    assert marked
    sample = marked[0]
    handler = _build_handler(sample)
    assert handler is not None, "a marked node must still be buildable/discoverable"
    # Supply the declared parameters; the guard must fire before the body runs.
    kwargs = {name: {} for name in (sample.input_schema or {})}
    for name in inspect.signature(handler).parameters:
        kwargs.setdefault(name, {})
    result = asyncio.run(handler(**kwargs))
    assert result.get("executable") is False
    assert result.get("error") == "not executable"
    assert "self" not in str(result.get("reason", ""))


def test_bridge_does_not_guard_a_real_plain_function():
    """The guard must not fire for ordinary functions."""
    import asyncio

    from common_lib.modules.plugins.nodes_registry import discover_nodes

    plain = [n for n in discover_nodes() if "." not in (n.qualname or "")]
    assert plain
    result = asyncio.run(_build_handler(plain[0])())
    assert "executable" not in result
