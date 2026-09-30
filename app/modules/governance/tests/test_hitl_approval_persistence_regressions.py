"""Regression tests for HITLService JSON persistence (governance-hitl-a, HIGH).

Finding 1 (FIXED here): ``GovernanceApprovalRequest`` stores ``tool_input``,
``modified_tool_input`` and ``timeline`` in ``str`` columns
(``common_lib/modules/governance/db_models.py:365-379``), but
``HITLService`` mutated them in place as Python objects. Binding a dict/list to
a str column raises on both sqlite3 and psycopg, so **every** write on the
service path failed:

    [tool_input={}]        -> ProgrammingError: Error binding parameter 13: type 'dict' is not supported
    [tool_input={'a':1}]   -> ProgrammingError: Error binding parameter 13: type 'dict' is not supported
    [tool_input='{}']      -> ProgrammingError: Error binding parameter 27: type 'list' is not supported

i.e. all 30 ``@node`` wrappers on ``HITLService`` were unreachable. Fixed with
``_encode_json_fields`` / ``_decode_json_fields`` at the persistence boundary.

Finding 2 (OPEN, HIGH — reported, not fixed; see the module audit): the service
assigns the ``apr_<hex>`` identifier to ``ApprovalRequest.id``, but ``id`` is
the ``int`` autoincrement primary key and ``request_id`` is the ``str`` unique
business key. So the INSERT binds a str into an INTEGER PRIMARY KEY and leaves
``request_id`` NULL:

    [after the Finding-1 fix] -> IntegrityError: datatype mismatch

and the seven read/decide methods key on ``ApprovalRequest.id == request_id``,
which can never match a str. ``PINNED_OPEN_*`` below pins that defect so it
cannot be forgotten; those tests are written to FAIL the moment someone fixes
it, which is the signal to finish the job.
"""

from __future__ import annotations

import json

import pytest

from common_lib.modules.governance.db_models import GovernanceApprovalRequest
from common_lib.modules.governance.hitl import approval_service as svc_mod
from common_lib.modules.governance.hitl.approval_service import (
    HITLService,
    _decode_json_fields,
    _encode_json_fields,
)
from common_lib.modules.governance.models.approvals import ApprovalRequest


def _row(**kw) -> ApprovalRequest:
    base = dict(
        agent_id="a1",
        request_id="apr_probe",
    )
    base.update(kw)
    return ApprovalRequest(**base)


# --------------------------------------------------------------------------
# 1. the columns really are str columns (the precondition for the bug)
# --------------------------------------------------------------------------


def test_json_payload_columns_are_str_not_json():
    """Guard the premise: if these ever become JSON columns, drop the codec."""
    import sqlalchemy as sa

    json_types = tuple(
        t for t in (getattr(sa, "JSON", None), getattr(sa, "JSONB", None)) if t
    )
    for name in ("tool_input", "modified_tool_input", "timeline"):
        column = GovernanceApprovalRequest.__table__.columns[name]
        assert not isinstance(column.type, json_types), (
            f"{name} is a JSON column now; _encode_json_fields/"
            "_decode_json_fields are no longer needed"
        )
        # String subclasses (AutoString, VARCHAR) report a python_type; the
        # generic TypeEngine base raises NotImplementedError, so treat that as
        # "not a str column" and assert the concrete class instead.
        assert isinstance(column.type, sa.types.TypeEngine) and (
            column.type.__class__.__name__.lower().startswith(("auto", "var", "str"))
        ), (
            f"{name} is {column.type!r} ({type(column.type).__name__}) — it is "
            "not a string column, re-check the premise of the codec"
        )


# --------------------------------------------------------------------------
# 2. THE FIX — encode on write, decode on read
# --------------------------------------------------------------------------


def test_encode_json_fields_makes_every_payload_bindable():
    """A dict/list must become the str the column expects. Can fail."""
    request = _row(
        tool_input={"a": 1}, modified_tool_input={"b": 2}, timeline=[{"x": 1}]
    )
    _encode_json_fields(request)

    assert isinstance(request.tool_input, str)
    assert isinstance(request.modified_tool_input, str)
    assert isinstance(request.timeline, str)
    assert json.loads(request.tool_input) == {"a": 1}
    assert json.loads(request.modified_tool_input) == {"b": 2}
    assert json.loads(request.timeline) == [{"x": 1}]


def test_encode_json_fields_respects_defaults():
    """NOT NULL columns must get a JSON default, not a bound None.

    ``tool_input``/``timeline`` are NOT NULL with a ``{}``/``[]`` default, so
    leaving them None would raise a NOT NULL violation on the next write.
    ``modified_tool_input`` is nullable and must stay NULL.
    """
    request = _row(tool_input=None, modified_tool_input=None, timeline=None)
    _encode_json_fields(request)
    assert json.loads(request.tool_input) == {}
    assert json.loads(request.timeline) == []
    assert request.modified_tool_input is None  # nullable column stays NULL


def test_encode_json_fields_is_idempotent():
    request = _row(tool_input={"a": 1}, timeline=[])
    _encode_json_fields(request)
    once = (request.tool_input, request.timeline)
    _encode_json_fields(request)
    assert (request.tool_input, request.timeline) == once


def test_decode_round_trip():
    request = _row(
        tool_input={"a": 1}, modified_tool_input={"b": 2}, timeline=[{"x": 1}]
    )
    _encode_json_fields(request)
    request.id = 1
    _decode_json_fields(request)
    assert request.tool_input == {"a": 1}
    assert request.modified_tool_input == {"b": 2}
    assert request.timeline == [{"x": 1}]


def test_decode_tolerates_corrupt_json():
    request = _row(tool_input="{not json", timeline="[not json")
    _decode_json_fields(request)
    assert request.tool_input == {}
    assert request.timeline == []


def test_decode_leaves_python_objects_alone():
    request = _row(tool_input={"a": 1}, timeline=[])
    _decode_json_fields(request)
    assert request.tool_input == {"a": 1}
    assert request.timeline == []


# --------------------------------------------------------------------------
# 3. every ApprovalRequest write site is encoded (regression sweep)
# --------------------------------------------------------------------------


# --------------------------------------------------------------------------
# 2b. THE FIX — a timeout auto-approval must record who decided
# --------------------------------------------------------------------------


class _FakePolicy:
    def __init__(self, on_timeout: str) -> None:
        self.timeout = {"on_timeout": on_timeout, "duration_hours": 1}
        self.approval_policy_id = "apv_t"


def _expired_request() -> ApprovalRequest:
    request = _row(timeline=[{"event_type": "triggered"}])
    request.status = "pending"
    request.expires_at = "2000-01-01T00:00:00"  # long past
    return request


class _CaptureSession:
    """Minimal Session stand-in that records what would be committed."""

    def __init__(self, sink: list) -> None:
        self._sink = sink

    def __enter__(self) -> "_CaptureSession":
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def add(self, obj: object) -> None:  # noqa: D102
        self._sink.append(obj)

    def commit(self) -> None:  # noqa: D102
        return None

    def refresh(self, obj: object) -> None:  # noqa: D102
        return None

    def exec(self, *a: object, **k: object):  # noqa: D102
        return self


@pytest.mark.parametrize(
    "on_timeout,expected_status",
    [("deny", "denied"), ("allow", "approved"), ("escalate", "escalated")],
)
def test_handle_timeout_records_a_decider(
    monkeypatch: pytest.MonkeyPatch, on_timeout: str, expected_status: str
):
    """Every terminal timeout branch must attribute the decision.

    Previously the auto-allow branch set status/decision/token but left
    ``decided_by`` and ``decided_at`` NULL, so an auto-approved request was
    indistinguishable from a human approval whose record went missing.
    Can fail: delete the ``decided_by``/``decided_at`` assignments in
    ``_handle_timeout`` and this goes red.
    """
    svc = HITLService.__new__(HITLService)
    monkeypatch.setattr(
        HITLService, "get_approval_policy", lambda self, pid: _FakePolicy(on_timeout)
    )

    written: list[ApprovalRequest] = []
    monkeypatch.setattr(svc_mod, "Session", lambda *a, **k: _CaptureSession(written))
    monkeypatch.setattr(
        svc_mod,
        "get_db_port",
        lambda: type("P", (), {"get_engine": staticmethod(lambda: None)})(),
    )

    request = _expired_request()
    svc._handle_timeout(request)

    assert request.status == expected_status
    assert request.decided_by == "system:auto-timeout", (
        f"{expected_status} via timeout recorded no decider — an auto-approval "
        "with a NULL decided_by is indistinguishable from a human approval"
    )
    assert request.decided_at, "decided_at must be stamped on every terminal branch"
    assert request.decision == expected_status or request.decision is None
    if expected_status == "approved":
        assert request.approval_token, "an auto-approval must still mint a token"
    assert written, "the terminal decision must be persisted"


def test_auto_approved_timeout_is_not_attributed_to_a_person():
    """The sentinel must be unmistakably machine, never a plausible name."""
    assert svc_mod._TIMEOUT_DECIDER == "system:auto-timeout"
    assert "system" not in svc_mod._TIMEOUT_DECIDER.replace("system:", "")


def test_every_request_write_site_encodes_before_persisting():
    """No ``session.add(req)``/``session.add(request)`` may bypass the codec.

    Can fail: revert one call site to ``session.add(req)`` and this goes red.
    """
    import inspect

    source = inspect.getsource(svc_mod)
    # The seed loader (_load_seed_data) is the one legitimate bare `add`: it
    # already encodes each JSON field at construction via _to_json_str, so it
    # is a codec call site too. Every other site must go through the codec
    # helper, otherwise a dict/list is bound into a str column and raises.
    # Resolved by AST rather than line number so edits above do not break it.
    import ast

    module_source = inspect.getsource(svc_mod)
    module_start = inspect.getsourcelines(svc_mod)[1]
    tree = ast.parse(module_source)
    src_lines = module_source.splitlines()

    def _abs_lineno(node: ast.AST) -> int:
        return node.lineno + module_start - 1

    # _load_seed_data pre-encodes every JSON field at construction time
    # (_to_json_str), so its bare add() is legitimate.
    # _load_seed_data pre-encodes every JSON field at construction time
    # (_to_json_str), so its bare add() is legitimate. Exclude its whole line
    # range by counting source lines, which is offset-proof.
    seed_lines_list = inspect.getsourcelines(svc_mod.HITLService._load_seed_data)
    seed_start = seed_lines_list[1]
    seed_end = seed_start + len(seed_lines_list[0]) - 1

    def _in_seed_loader(lineno: int) -> bool:
        return seed_start <= lineno <= seed_end

    bare = [
        _abs_lineno(node)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "add"
        and node.args
        and isinstance(node.args[0], ast.Name)
        and node.args[0].id in ("req", "request")
        and not _in_seed_loader(_abs_lineno(node))
    ]
    assert bare == [], (
        f"unencoded ApprovalRequest write site(s) at source lines {bare} "
        f"(context: {[src_lines[n - 1].strip() for n in bare]}) — JSON payloads "
        "will be bound as dict/list into str columns and the write will raise"
    )
    # 8 runtime write sites: create_request(1) + approve/deny/modify/execute/
    # add_feedback(5) + _handle_timeout(2, incl. the no-policy branch).
    assert source.count("session.add(_encode_json_fields(req))") == 8
    assert source.count("session.add(_encode_json_fields(request))") == 1


def test_append_event_never_sees_a_json_string():
    """``_append_event`` does ``list(request.timeline)``.

    On the raw JSON string that yields a list of single characters, silently
    corrupting the timeline of any request that was read back from the DB. The
    only way it can see a string is a read path that forgot to decode.
    """
    request = _row(timeline='[{"event_type": "triggered"}]')
    _decode_json_fields(request)
    svc = HITLService.__new__(HITLService)  # no DB needed for _append_event
    svc._append_event(request, "approved", "Action approved", {"decided_by": "x"})
    assert request.timeline[-1]["event_type"] == "approved"
    assert request.timeline[-1]["message"] == "Action approved"
    assert all(isinstance(e, dict) for e in request.timeline)


# --------------------------------------------------------------------------
# 4. PINNED OPEN DEFECT (Finding 2) — the inventory below IS the bug
# --------------------------------------------------------------------------


def test_PINNED_OPEN_service_identifier_does_not_fit_the_id_column():
    """OPEN HIGH: the service writes ``apr_<hex>`` into an ``int`` PK.

    ``db_models.py:353-354`` declares ``id: int | None`` (autoincrement PK) and
    ``request_id: str`` (unique business key). ``create_request`` assigns the
    string identifier to ``id`` and never sets ``request_id``, so the INSERT
    binds a str into an INTEGER PRIMARY KEY and omits the NOT NULL business key
    (observed: ``IntegrityError: datatype mismatch``).

    Fixing this makes this test FAIL — that is intentional: it is the prompt to
    move the identifier onto ``request_id`` and re-key the seven read/decide
    methods from ``ApprovalRequest.id`` to ``ApprovalRequest.request_id``.
    """
    id_column = GovernanceApprovalRequest.__table__.columns["id"]
    assert id_column.type.python_type is int, (
        f"`id` now binds as {id_column.type.python_type!r}, so the service's "
        "`id=f'apr_...'` is valid. FINISH Finding 2: put the apr_ identifier on "
        "`request_id` and re-key get_request/approve/deny/modify/execute/"
        "add_feedback/validate_approval_token off `ApprovalRequest.id`, then "
        "delete this test and the one below."
    )
    import inspect

    source = inspect.getsource(svc_mod.HITLService.create_request)
    assert 'id=f"apr_' in source, "the string identifier is no longer assigned to `id`"
    assert "request_id=" not in source, (
        "the service now populates the `request_id` business key as well"
    )


def test_PINNED_OPEN_decision_methods_are_keyed_on_the_int_pk():
    """OPEN HIGH: the read/decide methods filter on the int PK with a str value.

    ``where(ApprovalRequest.id == request_id)`` can never match, so
    ``get_request``/``approve``/``deny``/``modify``/``execute``/
    ``add_feedback`` silently return ``False``/``None`` forever — and
    ``create_request`` is the only writer, so nothing exists to match anyway.

    This pins the CURRENT (broken) inventory so the defect cannot be
    forgotten. ``expected_broken`` is the list of methods that DO use the wrong
    column: a method leaving the list is progress, and the assertion message
    tells you to reconcile it. When all of them are re-keyed to
    ``ApprovalRequest.request_id``, DELETE this test.
    """
    import inspect

    expected_broken = {
        "add_feedback",
        "approve",
        "deny",
        "execute",
        "get_request",
        "modify",
    }
    candidates = (*sorted(expected_broken), "validate_approval_token")
    offenders = {
        name
        for name in candidates
        if "ApprovalRequest.id == request_id"
        in inspect.getsource(getattr(svc_mod.HITLService, name))
    }
    assert offenders == expected_broken, (
        "the set of methods keyed on the int PK changed. If you re-keyed some "
        "to ApprovalRequest.request_id, reconcile expected_broken or DELETE "
        f"this test. now={sorted(offenders)} expected={sorted(expected_broken)}"
    )

    # validate_approval_token keys on approval_token, not the id — assert it
    # really is unaffected so the inventory above is not a lie.
    assert "ApprovalRequest.id ==" not in inspect.getsource(
        svc_mod.HITLService.validate_approval_token
    )


@pytest.mark.parametrize(
    "method",
    [
        "get_request",
        "approve",
        "deny",
        "modify",
        "execute",
        "add_feedback",
        "validate_approval_token",
    ],
)
def test_every_decision_method_still_exists_and_is_public(method):
    """Guard against a 'fix' that quietly drops a decision method."""
    assert callable(getattr(svc_mod.HITLService, method))
