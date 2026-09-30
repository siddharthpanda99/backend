"""Tests for the startup `@node` instance-registry wiring.

Design constraints these tests exist to enforce:

* A dotted ``@node`` method on a *wired* owner must become genuinely callable
  end-to-end, with ``self`` gone from its signature.
* That signature must equal a plain-function ``@node`` with the same inputs. The
  platform requirement is that the two are indistinguishable to an LLM; if binding
  leaves ``self`` in place, the generated JSON Schema gains a required ``self``
  parameter and every caller breaks.
* One unconstructible owner must not take the server down.
* A module switched off by the per-instance feature config must not have its
  instances constructed at all.
* A per-request-shaped class must NOT be in the wiring table. This is the guard
  against a future change adding a shared instance and leaking one caller's state
  to the next; it is asserted against real classes, not stand-ins.

Every test drives the real ``app.mcp.node_bridge`` resolver and the real owner classes.
No collaborator is hand-rolled where a real one exists.
"""

from __future__ import annotations

import inspect
import logging

import pytest

from app.core.node_instances import (
    STARTUP_INSTANCE_WIRINGS,
    InstanceWiring,
    WiringReport,
    _resolve_dotted,
    register_startup_instances,
)
from common_lib.modules.common.instance_registry import (
    clear_registry,
    get_instance_for_path,
    registered_owners,
)

# ── real collaborators ────────────────────────────────────────────────────
#
# A real dotted node on a real owner that this module wires, and a real
# module-level `@node` with the same input, used as the parity reference.

WIRED_OWNER_PATH = (
    "common_lib.modules.orchestration.knowledgebase.chunking.SimpleTextSplitter"
)
WIRED_NODE_MODULE = "common_lib.modules.orchestration.knowledgebase.chunking"
WIRED_NODE_QUALNAME = "SimpleTextSplitter.split_text"
# A second REAL owner, so a fixture needing two entries registers two real classes
# rather than two names that do not import. The pass resolves the owner class before
# constructing anything -- deliberately, because the bridge keys the registry off the
# class's own dotted path -- so a fabricated owner path is rejected.
WIRED_OWNER_PATH_2 = (
    "common_lib.modules.data_storage.database.connection.DatabaseConfig"
)
PLAIN_NODE_MODULE = "common_lib.modules.audio_processing.security"
PLAIN_NODE_QUALNAME = "security_scrub_text"


@pytest.fixture(autouse=True)
def _clean_registry():
    """The registry is process-wide; a leaked entry would make a later test lie."""
    clear_registry()
    yield
    clear_registry()


def _resolved_signature(func):
    """``inspect.signature`` with string annotations resolved to real types.

    Two of the reference modules differ in whether they use
    ``from __future__ import annotations``, so one records ``str`` and the other
    ``'str'`` for the same parameter. That is a property of the *source module*, not
    of binding, and comparing the raw reprs would fail for a reason that has nothing
    to do with the thing under test.
    """
    func = inspect.unwrap(func)
    raw = inspect.get_annotations(func, eval_str=True)
    return inspect.signature(func).replace(
        parameters=[
            p.replace(annotation=raw.get(p.name, p.annotation))
            for p in inspect.signature(func).parameters.values()
        ],
        return_annotation=raw.get("return", inspect.signature(func).return_annotation),
    )


def _wired_node_module():
    """The real module object the bridge resolves the dotted owner through."""
    return __import__(WIRED_NODE_MODULE, fromlist=["SimpleTextSplitter"])


def _plain_node_module():
    """The real module holding the plain-function reference node."""
    return __import__(PLAIN_NODE_MODULE, fromlist=["security_scrub_text"])


def _wiring(owner: str, source: str, module: str = "does_not_matter") -> InstanceWiring:
    return InstanceWiring(
        owner=owner, source=source, module=module, rationale="test fixture", nodes=1
    )


# ── 1. a real dotted node on a wired owner becomes callable ────────────────


def test_wired_owner_node_is_callable_end_to_end_with_self_absent():
    """Register the real owner, then resolve its real dotted node through the bridge.

    This is the whole point of the feature: the node is decorated, discovered and
    advertised, and before this it raised ``TypeError: missing 1 required positional
    argument: 'self'`` on every call. The assertion is on the *return value* of the
    real method, not on the fact that binding returned something.
    """
    from app.mcp.node_bridge import _resolve_callable

    report = register_startup_instances(
        [_wiring(WIRED_OWNER_PATH, "app.core.node_instances:_build_text_splitter")]
    )
    assert WIRED_OWNER_PATH in report.registered, report.summary()

    bound = _resolve_callable(_wired_node_module(), WIRED_NODE_QUALNAME)

    # `self` must be gone -- that is the difference between callable and not.
    params = list(inspect.signature(bound).parameters)
    assert "self" not in params
    assert params == ["text"]

    # And the body must actually run.
    out = bound(text="alpha beta gamma delta epsilon")
    assert isinstance(out, list) and out, f"real method produced nothing: {out!r}"
    assert all(isinstance(chunk, str) for chunk in out)

    # The callable really is bound to the registered instance, not a stray object.
    assert get_instance_for_path(WIRED_OWNER_PATH) is not None
    assert inspect.ismethod(bound)


# ── 2. dotted signature == plain-function signature ───────────────────────


def test_dotted_node_signature_equals_plain_function_node_signature():
    """A wired dotted node and a plain-function node must be indistinguishable.

    Both are real platform ``@node`` functions. The comparison is on the full
    signature -- parameter names, kinds, defaults, annotations and return -- because
    that is what the bridge turns into the JSON Schema an LLM reads. A stray ``self``
    here is not cosmetic: it becomes a *required* parameter in the tool schema.
    """
    from app.mcp.node_bridge import _resolve_callable

    register_startup_instances(
        [_wiring(WIRED_OWNER_PATH, "app.core.node_instances:_build_text_splitter")]
    )

    dotted = _resolve_callable(_wired_node_module(), WIRED_NODE_QUALNAME)
    plain = _resolve_callable(_plain_node_module(), PLAIN_NODE_QUALNAME)

    dotted_sig = _resolved_signature(dotted)
    plain_sig = _resolved_signature(plain)

    assert list(dotted_sig.parameters) == list(plain_sig.parameters) == ["text"]
    assert [
        (p.name, p.kind, p.default, p.annotation)
        for p in dotted_sig.parameters.values()
    ] == [
        (p.name, p.kind, p.default, p.annotation) for p in plain_sig.parameters.values()
    ]

    # The *return* type is deliberately not compared: these are two different real
    # functions (`list[str]` vs `dict[str, Any]`). What must match is the caller's
    # INPUT surface -- the parameters an LLM has to fill in. The return annotation is
    # checked for preservation in the test below.

    # The same input works through both, and neither needs a `self` keyword.
    dotted(text="hello world")
    plain(text="hello world")


def test_dotted_node_signature_equals_the_owner_method_minus_self():
    """The invariant stated directly: binding removes `self` and changes nothing else.

    The cross-module comparison above is the platform requirement; this one is the
    mechanism, and it is what would actually regress -- a future change to
    `_bind_instance` that wrapped the bound method in a partial, or re-exec'd it from
    `input_schema`, would still bind but would widen or reorder the signature.
    """
    from app.mcp.node_bridge import _resolve_callable

    register_startup_instances(
        [_wiring(WIRED_OWNER_PATH, "app.core.node_instances:_build_text_splitter")]
    )

    owner_cls = _wired_node_module().SimpleTextSplitter
    declared = inspect.signature(owner_cls.split_text)
    bound = _resolve_callable(_wired_node_module(), WIRED_NODE_QUALNAME)

    expected = declared.replace(
        parameters=[p for n, p in declared.parameters.items() if n != "self"]
    )
    assert inspect.signature(bound) == expected
    assert "self" in declared.parameters, "the owner method must be an unbound function"
    assert declared.return_annotation == inspect.signature(bound).return_annotation


def test_dotted_node_input_schema_has_no_self_parameter():
    """Belt-and-braces on the real metadata the tool catalogue is built from."""
    from common_lib.modules.orchestration.knowledgebase.chunking import (
        SimpleTextSplitter,
    )

    metadata = SimpleTextSplitter.split_text._node_metadata
    schema = metadata["input_schema"]
    assert "self" not in schema, schema
    assert set(schema) == {"text"}


# ── 3. one failing owner does not abort startup ───────────────────────────


def test_one_failing_owner_does_not_abort_startup(caplog):
    """A broken entry is recorded and skipped; the entries after it still register.

    The ordering matters as much as the outcome: a real outage hits the *last* entry
    as easily as the first, so a pass that stopped at the first failure would look
    fine in a unit test that only fails entry one.
    """
    broken_owner = "common_lib.modules.knowledge_engine.knowledge_base.service.KnowledgeBaseService"
    table = [
        _wiring(WIRED_OWNER_PATH, "app.core.node_instances:_build_text_splitter"),
        # A real failure rather than a fabricated one: the knowledge-base accessor
        # raises unless the platform already called init_kb_service(), which outside
        # an app boot it has not.
        _wiring(broken_owner, "app.core.node_instances:_build_knowledge_base_service"),
        _wiring(WIRED_OWNER_PATH_2, "app.core.node_instances:_build_database_config"),
    ]

    with caplog.at_level(logging.WARNING, logger="node_instances"):
        report = register_startup_instances(table)

    assert set(report.registered) == {WIRED_OWNER_PATH, WIRED_OWNER_PATH_2}
    assert list(report.failed) == [broken_owner]
    assert "RuntimeError" in report.failed[broken_owner]
    assert "NodeInstances" in caplog.text
    # The report is honest about the loss rather than silently short.
    assert "1 failed" in report.summary()


def test_a_broken_owner_leaves_its_owner_unregistered(caplog):
    """Failure means *not registered*, not registered-with-a-half-built-object."""
    owner = "common_lib.modules.knowledge_engine.knowledge_base.service.KnowledgeBaseService"
    with caplog.at_level(logging.WARNING, logger="node_instances"):
        register_startup_instances(
            [_wiring(owner, "app.core.node_instances:_build_knowledge_base_service")]
        )
    assert get_instance_for_path(owner) is None


def test_unimportable_owner_is_skipped_not_fatal(caplog):
    """A missing owner module is the most likely real failure; it must not crash."""
    table = [
        _wiring(
            "pkg.does.not.exist.Thing", "app.core.node_instances:_build_text_splitter"
        )
    ]
    with caplog.at_level(logging.WARNING, logger="node_instances"):
        report = register_startup_instances(table)
    assert report.registered == {}
    assert "pkg.does.not.exist.Thing" in report.failed
    assert "ModuleNotFoundError" in report.failed["pkg.does.not.exist.Thing"]


# ── 4. the feature-config tie-in ─────────────────────────────────────────


def test_module_disabled_by_feature_config_is_not_constructed(monkeypatch, caplog):
    """A disabled module's source must never be called.

    The wiring gates on the same predicate the router and node pruners use, so an
    operator switching a module off does not merely stop its routes -- its services
    are never even built. The source is instrumented here so the assertion is on
    *construction*, not on the absence of a registry entry.
    """
    import app.core.node_instances as ni

    original = ni._build_text_splitter
    calls: list[str] = []
    monkeypatch.setattr(ni, "_module_enabled", lambda module: False)

    def _spy() -> object:
        calls.append("built")
        return original()

    monkeypatch.setattr(ni, "_build_text_splitter", _spy)
    table = [
        _wiring(
            WIRED_OWNER_PATH,
            "app.core.node_instances:_build_text_splitter",
            module="off_module",
        )
    ]

    with caplog.at_level(logging.INFO, logger="node_instances"):
        report = register_startup_instances(table)

    assert calls == [], "source was constructed for a disabled module"
    assert report.registered == {}
    assert report.disabled == [WIRED_OWNER_PATH]
    assert report.failed == {}
    assert get_instance_for_path(WIRED_OWNER_PATH) is None


def test_enabled_module_is_constructed(monkeypatch):
    """The negative control for the test above: ON must actually build."""
    import app.core.node_instances as ni

    original = ni._build_text_splitter
    monkeypatch.setattr(ni, "_module_enabled", lambda module: True)
    calls: list[str] = []

    def _spy() -> object:
        calls.append("built")
        return original()

    monkeypatch.setattr(ni, "_build_text_splitter", _spy)
    register_startup_instances(
        [
            _wiring(
                WIRED_OWNER_PATH,
                "app.core.node_instances:_build_text_splitter",
                module="on_module",
            )
        ]
    )
    assert calls == ["built"]


# ── 5. THE GUARD: per-request-shaped classes are never wired ──────────────


@pytest.mark.parametrize(
    ("owner", "module", "why"),
    [
        (
            "common_lib.modules.workflows.standard.nodes.etl_nodes.APIExtractNode",
            "etl_nodes",
            "takes (node_id, name) -- per-request values; a singleton would serve one "
            "node_id to every caller",
        ),
        (
            "common_lib.modules.rbac.agent_apikey_service.APIKeyService",
            "rbac",
            "holds a live Session and calls self.session.commit() -- a shared instance "
            "is a cross-tenant transaction leak",
        ),
        (
            "common_lib.modules.agents.services.snapshot_service.SnapshotService",
            "agents",
            "holds a live Session (self.db.commit()) -- same leak",
        ),
    ],
)
def test_per_request_shaped_class_is_not_in_the_wiring_table(
    owner: str, module: str, why: str
):
    """No shared instance may exist for a class whose constructor takes per-request data.

    This is the test that stops someone "fixing" the node count by registering one of
    these. It asserts absence, so it cannot be satisfied by a workaround: a singleton
    for any of these owners would commit one caller's work inside another caller's
    request. The owner path is checked against the real, importable class, so a typo
    that dodged the check would fail the companion assertion below.
    """
    from app.core.node_instances import STARTUP_INSTANCE_WIRINGS as table

    owners = {wiring.owner for wiring in table}
    assert owner not in owners, (
        f"{owner} must not be registered as a singleton -- {why}"
    )

    # And the reason it is excluded is real, not a stale note: the class genuinely
    # has a constructor that cannot be satisfied process-wide.
    mod_name, _, class_name = owner.rpartition(".")
    cls = getattr(__import__(mod_name, fromlist=[class_name]), class_name)
    required = [
        p
        for p in list(inspect.signature(cls.__init__).parameters.values())[1:]
        if p.default is inspect.Parameter.empty
    ]
    assert required, f"{owner} no longer needs an instance; retire this guard"
    assert module  # the label above is documentation, keep it honest


def test_wiring_table_contains_no_orm_session_owners():
    """Belt-and-braces: no owner in the table takes a live ORM Session.

    A live ``Session`` in a constructor is the specific shape that turns a registry
    entry into a data leak, so the table is checked for it directly rather than only
    through the named cases above.
    """
    from app.core.node_instances import STARTUP_INSTANCE_WIRINGS as table

    offenders: list[str] = []
    for wiring in table:
        mod_name, _, class_name = wiring.owner.rpartition(".")
        cls = getattr(__import__(mod_name, fromlist=[class_name]), class_name)
        annotations = {
            p.name: p.annotation
            for p in list(inspect.signature(cls.__init__).parameters.values())[1:]
            if p.default is inspect.Parameter.empty
        }
        for name, annotation in annotations.items():
            label = getattr(annotation, "__name__", str(annotation))
            if label in ("Session", "AsyncSession"):
                offenders.append(f"{wiring.owner}.__init__({name}: {label})")
    assert offenders == [], f"live-session owners must not be wired: {offenders}"


# ── 6. no live infrastructure needed ──────────────────────────────────────


def test_registration_requires_no_database(monkeypatch):
    """The pass must not need a DB, a live engine or a network.

    Any attempt to open infrastructure is turned into a hard failure, so a source that
    quietly grew a ``create_engine()`` would fail here instead of at boot on a
    machine with no database.
    """
    import app.core.node_instances as ni

    def _forbidden(*_args, **_kwargs):
        raise AssertionError("startup wiring must not touch live infrastructure")

    monkeypatch.setattr("sqlalchemy.create_engine", _forbidden, raising=False)
    monkeypatch.setattr(
        "common_lib.modules.data_storage.database.connection.get_session",
        _forbidden,
        raising=False,
    )

    report = ni.register_startup_instances()
    # A refusal here is a legitimate outcome (KnowledgeBaseService is uninitialised
    # outside an app boot); an *infrastructure* error is not.
    assert "AssertionError" not in " ".join(report.failed.values()), report.failed
    assert len(report.registered) >= 1, report.summary()


def test_shipped_table_entries_are_zero_argument():
    """The table's contract: every source resolves to a zero-argument callable.

    ``instance_registry._call_source`` calls the source with no arguments, so an entry
    whose source needs one would only fail later, at resolution, with a confusing
    ``TypeError`` in a completely different module.
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
        assert wiring.rationale.strip(), f"{wiring.owner} has no recorded rationale"
        assert wiring.module.strip(), f"{wiring.owner} has no feature-flag namespace"


def test_shipped_table_owners_all_import():
    """Every owner in the shipped table must actually be importable.

    A dotted path that no longer resolves is worse than no entry: the pass logs a
    failure on every boot and the node stays uncallable, with the reason buried in a
    startup log line.
    """
    for wiring in STARTUP_INSTANCE_WIRINGS:
        mod_name, _, class_name = wiring.owner.rpartition(".")
        module = __import__(mod_name, fromlist=[class_name])
        assert hasattr(module, class_name), f"{wiring.owner} does not resolve"


# ── 7. the report itself ──────────────────────────────────────────────────


def test_wiring_report_summary_counts_owners_and_nodes():
    report = WiringReport()
    report.registered["a"] = object()
    report.registered["b"] = object()
    report.nodes_registered = 7
    report.reused.append("e")
    report.disabled.append("c")
    report.failed["d"] = "boom"
    assert report.summary() == (
        "2 owner(s) / 7 node(s) registered; 1 reused; "
        "1 skipped (module disabled); 1 failed"
    )


def test_duplicate_registration_of_the_same_instance_is_idempotent():
    """Re-running startup wiring must not raise.

    ``register_instance`` raises on a *conflicting* re-registration, and the platform
    calls the pass once per app build. Two app objects in one process (tests, a worker
    that reloads) is a real case, so it must be a no-op rather than a crash.
    """
    wiring = _wiring(WIRED_OWNER_PATH, "app.core.node_instances:_build_text_splitter")
    first = register_startup_instances([wiring])
    second = register_startup_instances([wiring])
    assert first.registered[WIRED_OWNER_PATH] is second.registered[WIRED_OWNER_PATH]
    assert second.reused == [WIRED_OWNER_PATH]
    assert second.failed == {}
    assert len(registered_owners()) == 1
