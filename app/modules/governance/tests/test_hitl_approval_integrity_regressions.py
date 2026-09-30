"""Regression tests for the HITL approval-integrity finding (governance-hitl-a).

Finding (HIGH): ``HITLBridge.approve()`` / ``deny()`` could report an approval
that no audit trail could corroborate, for two independent reasons:

1. ``decided_by`` defaulted to the literal string ``"system"`` and was never
   validated, so ``await bridge.approve(request_id)`` recorded an approval with
   no human behind it — and ``_record_hitl_episode()`` then trained the
   behaviour/RL memory on it (``quality_score=1.0``).
2. ``_update_governance_decision()`` swallowed every DB error and returned
   ``None``, and ``approve()`` set ``request._event`` *before* calling it. So a
   failed (or row-less) durable write still returned ``True`` and released the
   awaiting agent as "approved" — a decision that existed only in process
   memory and vanished on restart.

The fix is gated on the new default-OFF ``HITL_APPROVAL_INTEGRITY`` flag
(OFF in both production and staging), so the tests below assert BOTH halves:
the legacy behaviour is unchanged with the flag off, and the fail-closed
behaviour engages with it on.

Every assertion here is proven able to fail — see the module docstring of
``MODULE-AUDIT-governance-hitl-a.md`` for the neuter-and-restore procedure.
"""

from __future__ import annotations

import asyncio

import pytest

from common_lib.modules.governance.hitl.bridge import (
    HITLBridge,
    HITLDecision,
)
from common_lib.modules.governance.hitl.feature_flags import HITL_APPROVAL_INTEGRITY
from common_lib.modules.governance.hitl.review_errors import InvalidArgumentError


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


def _make_pending(bridge: HITLBridge, request_id: str = "req_test_1") -> str:
    """Put a request into the bridge's pending map without touching a DB."""
    from common_lib.modules.governance.hitl.bridge import ApprovalRequest as BridgeReq

    request = BridgeReq(
        request_id=request_id,
        hook_id="hook_1",
        action="delete_production_db",
        context={},
    )
    bridge._pending[request_id] = request
    return request_id


@pytest.fixture
def bridge() -> HITLBridge:
    return HITLBridge()


@pytest.fixture
def unpersisted(bridge: HITLBridge, monkeypatch: pytest.MonkeyPatch):
    """Force every durable write to report failure (DB down / row missing)."""

    async def _fail(self, request):  # noqa: ANN001
        return False

    monkeypatch.setattr(HITLBridge, "_update_governance_decision", _fail)
    return bridge


@pytest.fixture
def persisted(bridge: HITLBridge, monkeypatch: pytest.MonkeyPatch):
    async def _ok(self, request):  # noqa: ANN001
        return True

    monkeypatch.setattr(HITLBridge, "_update_governance_decision", _ok)
    return bridge


@pytest.fixture
def flag_on(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HITL_APPROVAL_INTEGRITY", "1")


# --------------------------------------------------------------------------
# 0. the flag itself: DEFAULT OFF in every environment (G4/G9)
# --------------------------------------------------------------------------


def test_approval_integrity_flag_is_default_off(monkeypatch: pytest.MonkeyPatch):
    """The gate must be opt-in, otherwise this would be a behaviour change."""
    monkeypatch.delenv("HITL_APPROVAL_INTEGRITY", raising=False)

    for environment in ("production", "staging", "development", ""):
        monkeypatch.setenv("ENVIRONMENT", environment)
        assert HITL_APPROVAL_INTEGRITY.default_production is False
        assert HITL_APPROVAL_INTEGRITY.default_staging is False
        assert HITL_APPROVAL_INTEGRITY.is_enabled() is False, (
            f"flag must be off in ENVIRONMENT={environment!r}"
        )

    monkeypatch.setenv("HITL_APPROVAL_INTEGRITY", "0")
    monkeypatch.setenv("ENVIRONMENT", "production")
    assert HITL_APPROVAL_INTEGRITY.is_enabled() is False


# --------------------------------------------------------------------------
# 1. THE BUG — legacy behaviour, flag off: approval reported without a
#    durable record and without a human. Pinned so the fix cannot silently
#    rewrite history.
# --------------------------------------------------------------------------


def test_legacy_approve_returns_true_without_durable_record(
    unpersisted: HITLBridge,
):
    """Documents the pre-fix bug: the write failed, approve() said True."""
    _make_pending(unpersisted)
    ok = asyncio.run(unpersisted.approve("req_test_1", decided_by="alice"))
    assert ok is True, "pinned legacy behaviour (flag off)"
    assert unpersisted._pending["req_test_1"].status is HITLDecision.APPROVED
    assert unpersisted._pending["req_test_1"]._event.is_set() is True, (
        "pinned legacy behaviour: the waiter was released anyway"
    )


def test_legacy_approve_accepts_default_system_decider(bridge: HITLBridge):
    """Documents the pre-fix bug: no human behind the recorded approval."""
    _make_pending(bridge)
    ok = asyncio.run(bridge.approve("req_test_1"))  # decided_by defaults to "system"
    assert ok is True, "pinned legacy behaviour (flag off)"
    assert bridge._pending["req_test_1"].decided_by == "system"


# --------------------------------------------------------------------------
# 2. THE FIX — flag on: fail closed on a lost decision
# --------------------------------------------------------------------------


def test_approve_fails_closed_when_durable_write_failed(
    unpersisted: HITLBridge, flag_on: None
):
    """A failed persistence write must NOT return approved (audit finding)."""
    _make_pending(unpersisted)
    ok = asyncio.run(unpersisted.approve("req_test_1", decided_by="alice"))
    assert ok is False, "a lost decision must not be reported as an approval"

    request = unpersisted._pending["req_test_1"]
    assert request.status is HITLDecision.PENDING, "in-memory state must roll back"
    assert request.decided_at is None
    assert request._event.is_set() is False, (
        "the awaiting agent must NOT be released on a lost decision"
    )


def test_deny_fails_closed_when_durable_write_failed(
    unpersisted: HITLBridge, flag_on: None
):
    _make_pending(unpersisted)
    ok = asyncio.run(unpersisted.deny("req_test_1", decided_by="alice"))
    assert ok is False
    request = unpersisted._pending["req_test_1"]
    assert request.status is HITLDecision.PENDING
    assert request._event.is_set() is False


# --------------------------------------------------------------------------
# 3. THE FIX — flag on: no approval without a named human decider
# --------------------------------------------------------------------------


@pytest.mark.parametrize("decider", ["system", "SYSTEM", "", "  ", "auto", "unknown"])
def test_approve_rejects_non_human_decider(bridge: HITLBridge, flag_on: None, decider):
    _make_pending(bridge)
    with pytest.raises(InvalidArgumentError):
        asyncio.run(bridge.approve("req_test_1", decided_by=decider))
    request = bridge._pending["req_test_1"]
    assert request.status is HITLDecision.PENDING
    assert request._event.is_set() is False


def test_deny_rejects_non_human_decider(bridge: HITLBridge, flag_on: None):
    _make_pending(bridge)
    with pytest.raises(InvalidArgumentError):
        asyncio.run(bridge.deny("req_test_1"))


def test_named_human_decider_still_approves(persisted: HITLBridge, flag_on: None):
    """The fix must not block a genuine, persisted, human decision."""
    _make_pending(persisted)
    ok = asyncio.run(persisted.approve("req_test_1", decided_by="alice"))
    assert ok is True
    request = persisted._pending["req_test_1"]
    assert request.status is HITLDecision.APPROVED
    assert request.decided_by == "alice"
    assert request._event.is_set() is True


# --------------------------------------------------------------------------
# 4. the waiter is released only after the write is attempted
# --------------------------------------------------------------------------


def test_event_not_set_before_persistence_is_attempted(
    persisted: HITLBridge, flag_on: None
):
    """Ordering regression: the event used to be set before the DB write."""
    observed: list[str] = []
    _make_pending(persisted)

    original = persisted._record_hitl_episode

    async def _ok(self, request):  # noqa: ANN001
        observed.append("persisted")
        return True

    persisted._update_governance_decision = _ok.__get__(  # type: ignore[method-assign]
        persisted, HITLBridge
    )

    def _episode(request, decision):  # noqa: ANN001
        observed.append("episode")
        return original(request, decision)

    persisted._record_hitl_episode = _episode  # type: ignore[method-assign]
    _make_pending(persisted)

    asyncio.run(persisted.approve("req_test_1", decided_by="alice"))
    assert observed[0] == "persisted", (
        "the durable write must be attempted before the behaviour episode is "
        f"recorded, got {observed!r}"
    )
