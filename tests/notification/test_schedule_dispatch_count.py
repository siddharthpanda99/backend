"""``POST /schedules/dispatch`` — the count it returns must be one it can back up.

The defect this file pins
-------------------------
The handler read::

    return {"dispatched": svc.dispatch_due(limit=limit), "count": limit}

``count`` was the request **LIMIT**, not the number of schedules marked. A tick
that marked 3 of a possible 100 answered ``{"dispatched": [3 records],
"count": 100}``. The handler had the true number in hand the whole time — it is
``len()`` of the list it was already returning — and reported a number that
described its own request rather than its own work.

This is the sibling of the ``{"count": limit}`` shape in ``BaseWorker.run_once``,
and it is the exact failure mode rule 21 names: a value that reads as a result
but is not one. It is also the *only* thing about ``dispatch_due`` that was
repairable here; what happens to a row once it reaches ``status == "dispatched"``
has no consumer anywhere in the repository, which is an architecture decision
and is documented rather than fixed.

How this is tested
------------------
``dispatch_due`` is called directly as a coroutine with a stubbed service, so no
database is involved. What is asserted is the arithmetic of the response dict:
``count`` must equal the number of records actually returned, and ``limit`` must
be reported separately so the batch ceiling is still visible.
"""

from __future__ import annotations

import asyncio
import inspect
from typing import Any

import pytest

from app.modules.notification.routes.schedule_routes import dispatch_due


class _StubSchedulingService:
    """Returns a fixed number of dispatched records, whatever the limit."""

    def __init__(self, records: list[dict[str, Any]]):
        self._records = records
        self.calls: list[int] = []

    def dispatch_due(self, limit: int = 100) -> list[dict[str, Any]]:
        self.calls.append(limit)
        return self._records[:limit]


def _record(i: int) -> dict[str, Any]:
    return {"id": f"s{i}", "status": "dispatched", "channel": "email"}


@pytest.mark.parametrize(
    "n_available,limit,expected",
    [
        (0, 100, 0),  # nothing due — the case that read worst: claimed 100
        (1, 100, 1),
        (3, 100, 3),  # the motivating case: 3 done, limit 100
        (7, 7, 7),  # exactly full: count == limit, so this case cannot tell them apart
        (9, 4, 4),  # more due than the limit allows — the service clamps
    ],
)
def test_count_is_the_number_dispatched_not_the_limit(
    monkeypatch, n_available, limit, expected
):
    """``n_available`` is what the service *could* mark; ``limit`` caps it."""
    records = [_record(i) for i in range(n_available)]
    stub = _StubSchedulingService(records)

    import common_lib.modules.notification.scheduling.service as svc_mod

    monkeypatch.setattr(svc_mod, "SchedulingService", lambda session=None: stub)

    out = asyncio.run(dispatch_due(limit=limit, session=object()))

    assert out["count"] == expected, (
        f"count reported {out['count']} but {expected} schedule(s) were dispatched"
    )
    assert out["count"] == len(out["dispatched"]), (
        "count must be derivable from the records returned in the same response"
    )
    assert out["limit"] == limit, (
        "the batch ceiling must still be reported, under its own name"
    )


def test_the_limit_is_still_forwarded_to_the_service(monkeypatch):
    stub = _StubSchedulingService([])
    import common_lib.modules.notification.scheduling.service as svc_mod

    monkeypatch.setattr(svc_mod, "SchedulingService", lambda session=None: stub)
    asyncio.run(dispatch_due(limit=42, session=object()))
    assert stub.calls == [42], "the limit must reach dispatch_due, not be applied twice"


def test_count_is_not_derived_from_the_limit_argument(monkeypatch):
    """Control: prove the old bug is gone by making limit and count differ.

    If `count` were still `limit`, a stub that returns a *different* number of
    records than the limit would expose it. This is the assertion that would
    have failed against the original one-liner.
    """
    stub = _StubSchedulingService([_record(i) for i in range(5)])
    import common_lib.modules.notification.scheduling.service as svc_mod

    monkeypatch.setattr(svc_mod, "SchedulingService", lambda session=None: stub)
    out = asyncio.run(dispatch_due(limit=500, session=object()))

    assert out["count"] == 5
    assert out["count"] != out["limit"], (
        "count and limit collapsed to the same number — the response can no "
        "longer distinguish a full batch from a partial one"
    )


def test_dispatch_due_returns_records_and_never_invents_a_count():
    """The service contract the handler now relies on.

    ``SchedulingService.dispatch_due`` returns a list of records. It must not
    start returning a count of its own, because the handler's ``count`` is
    computed from that list and a second source of truth would be a third.
    """
    from common_lib.modules.notification.scheduling.service import SchedulingService

    sig = inspect.signature(SchedulingService.dispatch_due)
    assert "limit" in sig.parameters
    # ``from __future__ import annotations`` means the annotation is the *string*
    # 'list[dict[str, Any]]', so match on the origin rather than the object.
    annotation = sig.return_annotation
    assert str(annotation).startswith("list"), (
        f"dispatch_due is annotated {annotation!r}; the route computes count as "
        "len() of its result, so a non-list return would break the count"
    )

    out = SchedulingService(session=None).dispatch_due(limit=50)
    assert isinstance(out, list)
    assert all("count" not in rec for rec in out), (
        "a per-record count key would collide with the response's own count"
    )
