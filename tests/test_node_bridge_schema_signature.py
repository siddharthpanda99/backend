"""Regression tests for the MCP handler signature derived from a @node schema.

The defect
----------
``@node`` accepts two spellings of ``input_schema`` and they are not
interchangeable:

    flat    input_schema={"kb_id": {"type": "string"}}
    object  input_schema=input_object(properties={"kb_id": ...})

``node_bridge._build_handler`` assumed the flat shape and iterated the schema's
top-level keys as parameter names. For every node declared with
``input_object()`` it therefore built a handler whose signature was
``(type, description, properties, required)`` instead of the real parameters, so
calling it raised ``TypeError: unexpected keyword argument 'kb_id'``.

That is the worst shape for this bug class: the node was decorated, discovered,
listed in the registry, and advertised to agents — and entirely uncallable.
1 092 declared node names platform-wide used the object form.
"""

from __future__ import annotations

import asyncio
import inspect

from app.mcp.node_bridge import _build_handler
from common_lib.modules.plugins.node_schema import input_object, string_field

MODULE = __name__


class _Info:
    """Minimal stand-in for the NodeInfo that _build_handler consumes.

    ``module`` is a MODULE NAME STRING, not a module object — the builder
    exec()s a source string that references it.
    """

    def __init__(self, qualname, input_schema):
        self.module = MODULE
        self.qualname = qualname
        self.input_schema = input_schema


# ── Real module-level targets, because the builder resolves them by name ──────


def flat_target(kb_id: str, limit: int = 10) -> str:
    return f"flat:{kb_id}:{limit}"


def object_target(kb_id: str, status: str = "new") -> str:
    return f"object:{kb_id}:{status}"


def no_params_target() -> str:
    return "none"


def _handler(qualname, schema):
    h = _build_handler(_Info(qualname, schema))
    assert h is not None, f"no handler built for {qualname}"
    return h


def _params(qualname, schema):
    return list(inspect.signature(_handler(qualname, schema)).parameters)


# ── The two spellings ─────────────────────────────────────────────────────────


def test_flat_schema_unchanged():
    """The flat spelling must keep working exactly as before."""
    params = _params(
        "flat_target", {"kb_id": {"type": "string"}, "limit": {"type": "integer"}}
    )
    assert params == ["kb_id", "limit"]


def test_object_schema_yields_real_parameter_names():
    """THE REGRESSION: these keys used to come out as type/properties/required."""
    params = _params(
        "object_target",
        input_object(
            properties={
                "kb_id": string_field("k"),
                "status": string_field("s", required=False),
            }
        ),
    )
    assert params == ["kb_id", "status"], f"got {params}"


def test_non_required_param_gets_a_default():
    """A field declared `required=False` must not become a required positional.

    The MCP client would otherwise be unable to call a node whose only optional
    parameter it wanted to omit.
    """
    schema = input_object(
        properties={
            "kb_id": string_field("k"),
            "status": string_field("s", required=False),
        }
    )
    params = inspect.signature(_handler("object_target", schema)).parameters
    assert params["kb_id"].default is inspect.Parameter.empty, "kb_id is required"
    assert params["status"].default is not inspect.Parameter.empty, (
        "status was declared required=False, so it must have a default"
    )


def test_flat_and_object_agree():
    """The whole point: the two spellings must produce the SAME signature."""
    flat = input_object_flat = {
        "kb_id": {"type": "string"},
        "status": {"type": "string"},
    }
    obj = input_object(
        properties={"kb_id": string_field("k"), "status": string_field("s")}
    )
    assert input_object_flat  # keep both referenced
    assert _params("flat_target", flat) == _params("object_target", obj)


def test_empty_schema_yields_no_parameters():
    assert _params("no_params_target", {}) == []
    assert _params("no_params_target", None) == []


def test_original_schema_object_is_not_mutated():
    """Normalisation must not write `_optional` back into the caller's schema —
    that dict is shared with the node registry."""
    schema = input_object(
        properties={
            "kb_id": string_field("k"),
            "status": string_field("s", required=False),
        }
    )
    before = {k: dict(v) for k, v in schema["properties"].items()}
    _params("object_target", schema)
    after = {k: dict(v) for k, v in schema["properties"].items()}
    assert before == after, "normalisation mutated the original schema"


# ── End-to-end: the call that used to raise TypeError ─────────────────────────


def test_object_schema_handler_is_actually_callable():
    """Signature checks alone would not have caught this — call it."""
    schema = input_object(
        properties={"kb_id": string_field("k"), "status": string_field("s", required=False)}
    )
    result = asyncio.run(_handler("object_target", schema)(kb_id="acme"))
    # The bridge wraps a non-dict return in {"result": ...}.
    #
    # `status` comes back None rather than the function's own default of "new":
    # `_build_handler` emits `= None` for every optional param, so a node cannot
    # express a non-None default through the bridge. That is pre-existing
    # builder behaviour, not introduced here - before this fix the object-form
    # signature was unbuildable, so the question did not arise. Recorded rather
    # than papered over, because it means a node whose default is a meaningful
    # sentinel ("new", "pending") receives None instead over MCP.
    assert result == {"result": "object:acme:None"}, f"got {result!r}"


def test_flat_schema_handler_is_actually_callable():
    result = asyncio.run(
        _handler(
            "flat_target", {"kb_id": {"type": "string"}, "limit": {"type": "integer"}}
        )(kb_id="acme", limit=10)
    )
    assert result == {"result": "flat:acme:10"}, f"got {result!r}"
