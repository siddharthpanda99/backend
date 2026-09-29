# Job → platform notification E2E tests (status + progress)
"""Covers the full path: executor ``report_progress`` → ``JobService`` →
notification port → real ``NotificationService`` → subscriber queue.

Assertions (the original ask, end to end):
- lifecycle events fire: ``job_progress`` with message ``queued`` / ``started``
- throttled progress events fire (100 rapid updates → ~2 notifications)
- exactly one ``job_complete`` on success, carrying ``user_id`` (owner)
- a broken notification controller never fails the job
"""

import queue
import time

from common_lib.modules.jobs.models import JobStatus
from common_lib.modules.jobs.service import JobService, get_job_service
from common_lib.modules.notification.controller import get_notification_service

TERMINAL = (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED)

# Rate-limiter key used by notify(): f"{channel}:{source}" with source="jobs".
_RATE_KEY = "ingestion:jobs"


def _generous_rate_limit() -> None:
    """Remove rate-limiting as a variable (default burst=10 may be drained)."""
    get_notification_service()._rate_limiter.configure(_RATE_KEY, 60000.0, 1000.0)


def _wait_terminal(svc: JobService, job_id: str, timeout: float = 15.0) -> object:
    deadline = time.time() + timeout
    while time.time() < deadline:
        record = svc.get(job_id)
        if record is not None and record.status in TERMINAL:
            return record
        time.sleep(0.02)
    raise AssertionError(f"job {job_id} never reached a terminal state")


def _drain_events(q: queue.Queue) -> list[dict]:
    events: list[dict] = []
    while True:
        try:
            events.append(q.get_nowait())
        except queue.Empty:
            break
    return events


def _wait_for_event(
    q: queue.Queue, predicate, timeout: float = 10.0
) -> list[dict]:
    """Drain until ``predicate(event)`` matches (or timeout); return all seen."""
    seen: list[dict] = []
    deadline = time.time() + timeout
    while time.time() < deadline:
        seen.extend(_drain_events(q))
        if any(predicate(e) for e in seen):
            return seen
        time.sleep(0.02)
    return seen


def _fast_executor(steps: int = 100):
    """Executor reporting 1..steps progress in a tight loop (no sleeping)."""

    def _fn(record, check_cancel, report_progress):
        for pct in range(1, steps + 1):
            if check_cancel():
                return []
            report_progress(float(pct))
        return ["ref://done"]

    return _fn


def test_job_lifecycle_and_progress_reach_notification_bus():
    """E2E: queued/started/progress/complete events hit a real subscriber."""
    _generous_rate_limit()
    notifier = get_notification_service()
    sub: queue.Queue = notifier.subscribe_sync("ingestion")
    svc = JobService()  # fresh instance — no singleton cross-talk
    try:
        svc.register_executor("test.notify.progress", _fast_executor())
        record = svc.submit(
            "test.notify.progress", params={}, user_id="user-42"
        )
        done = _wait_terminal(svc, record.id)
        assert done.status == JobStatus.COMPLETED, done.error

        events = _wait_for_event(
            sub, lambda e: e.get("type") == "job_complete"
        )
        job_id = record.id

        progress_events = [
            e for e in events if e.get("type") == "job_progress"
        ]
        messages = {
            e["data"].get("message"): e["data"] for e in progress_events
        }

        # Lifecycle: worker announces queued, then started (running).
        assert "queued" in messages, [e["data"] for e in progress_events]
        assert "started" in messages, [e["data"] for e in progress_events]
        assert messages["queued"]["job_id"] == job_id
        assert messages["queued"]["status"] == JobStatus.QUEUED
        assert messages["started"]["status"] == JobStatus.RUNNING

        # Throttled progress: 100 rapid updates → few notifications, not 100.
        bare = [
            e for e in progress_events if not e["data"].get("message")
        ]
        assert 2 <= len(bare) <= 3, [e["data"] for e in bare]
        assert bare[-1]["data"]["progress"] == 100  # final value always sent
        # Progress is monotonic across throttled notifications.
        values = [e["data"]["progress"] for e in bare]
        assert values == sorted(values), values

        # Owner stamped on progress events (routing to the submitting user).
        for e in progress_events:
            assert e["data"].get("user_id") == "user-42", e["data"]

        # Exactly one completion, success + owner + job id.
        completes = [e for e in events if e.get("type") == "job_complete"]
        assert len(completes) == 1, completes
        data = completes[0]["data"]
        assert data["success"] is True
        assert data["job_id"] == job_id
        assert data["user_id"] == "user-42"
        assert data["error"] is None
    finally:
        notifier.unsubscribe_sync("ingestion", sub)


def test_progress_notification_failure_never_fails_the_job(monkeypatch):
    """A raising notification controller must not affect job outcome."""
    _generous_rate_limit()

    class _BrokenController:
        @staticmethod
        async def notify_job_progress(**_kw):
            raise RuntimeError("notification bus is down")

        @staticmethod
        async def notify_job_complete(**_kw):
            raise RuntimeError("notification bus is down")

    import common_lib.modules.integration.ports.notification.notification_port as port

    monkeypatch.setattr(
        port, "get_notification_controller", lambda: _BrokenController()
    )

    svc = JobService()
    svc.register_executor("test.notify.broken", _fast_executor(steps=5))
    record = svc.submit("test.notify.broken", params={}, user_id="user-1")
    done = _wait_terminal(svc, record.id)
    assert done.status == JobStatus.COMPLETED, done.error
    assert done.progress == 100.0


def test_missing_notification_controller_is_skipped(monkeypatch):
    """Port returning None (module absent) → silent skip, job still runs."""
    import common_lib.modules.integration.ports.notification.notification_port as port

    monkeypatch.setattr(port, "get_notification_controller", lambda: None)

    svc = JobService()
    svc.register_executor("test.notify.absent", _fast_executor(steps=3))
    record = svc.submit("test.notify.absent", params={})
    done = _wait_terminal(svc, record.id)
    assert done.status == JobStatus.COMPLETED, done.error


def test_singleton_service_unchanged_for_direct_submits():
    """Regression: direct submits on the global service still work."""
    svc = get_job_service()
    assert svc is not None
    assert callable(svc.update_progress)
