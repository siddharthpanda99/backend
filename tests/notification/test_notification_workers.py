"""
Tests for Notification Workers — DeliveryWorker, RetryWorker, BroadcastWorker, CleanupWorker.

Uses SQLite in-memory database with clean SQLModel metadata import.
"""

from __future__ import annotations

import asyncio
import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from sqlmodel import Session, create_engine, SQLModel


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def setup_db():
    """Create tables in an in-memory SQLite database using isolated metadata."""
    from sqlalchemy import MetaData, Table, Column, String, Integer, Float, Boolean, DateTime, JSON, Text

    meta = MetaData()

    # WorkerTask
    Table("notification_worker_tasks", meta,
        Column("id", String, primary_key=True),
        Column("worker_type", String, default=""),
        Column("queue_name", String, default="immediate"),
        Column("task_type", String, default=""),
        Column("payload", JSON, default=dict),
        Column("status", String, default="pending"),
        Column("priority", Integer, default=0),
        Column("attempt_count", Integer, default=0),
        Column("max_attempts", Integer, default=3),
        Column("last_error", String, nullable=True),
        Column("scheduled_for", DateTime, nullable=True),
        Column("started_at", DateTime, nullable=True),
        Column("completed_at", DateTime, nullable=True),
        Column("created_at", DateTime),
        Column("updated_at", DateTime),
    )

    # BroadcastJob
    Table("notification_broadcast_jobs", meta,
        Column("id", String, primary_key=True),
        Column("campaign_id", String),
        Column("status", String, default="pending"),
        Column("total_recipients", Integer, default=0),
        Column("processed_count", Integer, default=0),
        Column("success_count", Integer, default=0),
        Column("failed_count", Integer, default=0),
        Column("throttle_rate", Integer, default=100),
        Column("batch_size", Integer, default=50),
        Column("error", String, nullable=True),
        Column("started_at", DateTime, nullable=True),
        Column("completed_at", DateTime, nullable=True),
        Column("created_at", DateTime),
        Column("updated_at", DateTime),
    )

    # CleanupPolicy
    Table("notification_cleanup_policies", meta,
        Column("id", String, primary_key=True),
        Column("name", String),
        Column("target", String),
        Column("retention_days", Integer, default=90),
        Column("batch_size", Integer, default=500),
        Column("enabled", Boolean, default=True),
        Column("schedule_cron", String, default="0 3 * * *"),
        Column("last_run_at", DateTime, nullable=True),
        Column("created_at", DateTime),
        Column("updated_at", DateTime),
    )

    # RealtimeConnection (used by CleanupWorker._prune_device_tokens)
    Table("notification_realtime_connections", meta,
        Column("id", String, primary_key=True),
        Column("connection_id", String),
        Column("channel", String),
        Column("connection_type", String),
        Column("user_id", String, nullable=True),
        Column("extra_metadata", String, nullable=True),
        Column("connected_at", DateTime),
        Column("disconnected_at", DateTime, nullable=True),
    )

    # WorkerHeartbeat
    Table("notification_worker_heartbeats", meta,
        Column("id", String, primary_key=True),
        Column("worker_id", String),
        Column("worker_type", String),
        Column("hostname", String),
        Column("status", String),
        Column("current_task_id", String, nullable=True),
        Column("tasks_processed", Integer, default=0),
        Column("tasks_failed", Integer, default=0),
        Column("last_heartbeat", DateTime),
        Column("started_at", DateTime),
    )

    # DeliveryAttempt (used by CleanupWorker and DeliveryWorker)
    Table("notification_delivery_attempts", meta,
        Column("id", String, primary_key=True),
        Column("event_id", String),
        Column("subscriber_id", String),
        Column("channel", String),
        Column("status", String),
        Column("attempt_number", Integer, default=1),
        Column("status_code", Integer, nullable=True),
        Column("response_body", Text, nullable=True),
        Column("error", String, nullable=True),
        Column("latency_ms", Float, nullable=True),
        Column("created_at", DateTime),
    )

    # DeadLetterEntry (used by CleanupWorker._archive_dlq and RetryWorker)
    Table("notification_dlq_entries", meta,
        Column("id", String, primary_key=True),
        Column("event_id", String),
        Column("event_type", String),
        Column("topic", String),
        Column("payload", JSON),
        Column("error", String),
        Column("attempts", Integer, default=0),
        Column("last_attempt_at", DateTime, nullable=True),
        Column("status", String, default="failed"),
        Column("created_at", DateTime),
    )

    # RetryPolicy (used by DeliveryWorker)
    Table("notification_retry_policies", meta,
        Column("id", String, primary_key=True),
        Column("name", String),
        Column("max_attempts", Integer, default=3),
        Column("base_delay_seconds", Float, default=1.0),
        Column("max_delay_seconds", Float, default=60.0),
        Column("backoff_multiplier", Float, default=2.0),
        Column("jitter", Boolean, default=True),
        Column("active", Boolean, default=True),
        Column("created_at", DateTime),
    )

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    meta.create_all(engine)

    session = Session(engine)
    yield session
    session.close()


# ═══════════════════════════════════════════════════════════════════════
# WorkerTaskService
# ═══════════════════════════════════════════════════════════════════════


class TestWorkerTaskService:
    def test_enqueue_and_dequeue(self, setup_db):
        session = setup_db
        from common_lib.modules.notification.workers.service import WorkerTaskService
        svc = WorkerTaskService(session=session)

        result = svc.enqueue(
            worker_type="delivery", queue_name="immediate",
            task_type="delivery_dispatch",
            payload={"event_id": "evt_1", "subscriber_id": "sub_1"},
            priority=5,
        )
        assert result["status"] == "pending"
        assert result["queue"] == "immediate"

        tasks = svc.dequeue("delivery", "immediate", limit=10)
        assert len(tasks) == 1
        assert tasks[0]["task_type"] == "delivery_dispatch"
        assert tasks[0]["payload"]["event_id"] == "evt_1"

    def test_enqueue_with_schedule(self, setup_db):
        session = setup_db
        from common_lib.modules.notification.workers.service import WorkerTaskService
        svc = WorkerTaskService(session=session)

        future = datetime.utcnow() + timedelta(hours=1)
        svc.enqueue(
            worker_type="delivery", queue_name="immediate",
            task_type="delayed_dispatch",
            payload={}, scheduled_for=future,
        )

        # Should NOT be dequeued yet (future scheduled_for)
        tasks = svc.dequeue("delivery", "immediate", limit=10)
        assert len(tasks) == 0

    def test_complete_task(self, setup_db):
        session = setup_db
        from common_lib.modules.notification.workers.service import WorkerTaskService
        svc = WorkerTaskService(session=session)

        result = svc.enqueue("test", "q", "test_type", {})
        assert svc.complete(result["id"]) is True
        assert svc.complete("nonexistent") is False

    def test_fail_task_exhausts(self, setup_db):
        session = setup_db
        from common_lib.modules.notification.workers.service import WorkerTaskService
        svc = WorkerTaskService(session=session)

        # Create task with max_attempts=1 so first failure exhausts
        result = svc.enqueue("test", "q", "test_type", {}, max_attempts=1)

        # Fail it immediately → should exhaust (attempt_count 0 >= max_attempts 1? No - wait)
        # With max_attempts=1: enqueue has attempt_count=0, fail checks 0 >= 1 → False → pending
        # So we need max_attempts=0 to fail immediately, but that's unrealistic.
        # Better approach: dequeue first (increments to 1), then fail
        tasks = svc.dequeue("test", "q", limit=10)
        assert len(tasks) == 1

        # Now fail it → attempt_count=1 >= max_attempts=1 → should exhaust
        svc.fail(tasks[0]["id"], "error_final")
        from common_lib.modules.notification.workers.models import WorkerTask
        from sqlmodel import select
        task = session.exec(select(WorkerTask).where(WorkerTask.id == result["id"])).one()
        assert task.status == "failed"

    def test_list_tasks_filters(self, setup_db):
        session = setup_db
        from common_lib.modules.notification.workers.service import WorkerTaskService
        svc = WorkerTaskService(session=session)

        svc.enqueue("delivery", "immediate", "type_a", {})
        svc.enqueue("retry", "retry", "type_b", {})
        svc.enqueue("broadcast", "broadcast", "type_c", {})

        delivery_tasks = svc.list_tasks(worker_type="delivery")
        assert len(delivery_tasks) == 1

        retry_tasks = svc.list_tasks(queue_name="retry")
        assert len(retry_tasks) == 1

        all_tasks = svc.list_tasks()
        assert len(all_tasks) == 3

    def test_count_pending(self, setup_db):
        session = setup_db
        from common_lib.modules.notification.workers.service import WorkerTaskService
        svc = WorkerTaskService(session=session)

        svc.enqueue("delivery", "immediate", "d1", {})
        svc.enqueue("delivery", "immediate", "d2", {})
        svc.enqueue("retry", "retry", "r1", {})

        assert svc.count_pending() == 3
        assert svc.count_pending(worker_type="delivery") == 2
        assert svc.count_pending(worker_type="retry") == 1
        assert svc.count_pending(worker_type="cleanup") == 0


# ═══════════════════════════════════════════════════════════════════════
# DeliveryWorker
# ═══════════════════════════════════════════════════════════════════════


class TestDeliveryWorker:
    def test_delivery_worker_enqueue_and_run(self, setup_db):
        session = setup_db
        from common_lib.modules.notification.workers.service import DeliveryWorker, WorkerTaskService

        # Enqueue a delivery task
        task_svc = WorkerTaskService(session=session)
        task_svc.enqueue(
            worker_type="delivery", queue_name="immediate",
            task_type="delivery_dispatch",
            payload={"event_id": "evt_1", "subscriber_id": "sub_1", "channel": "email"},
        )

        # Run the delivery worker
        worker = DeliveryWorker(session=session)
        result = asyncio.run(worker.run_once(limit=5))

        assert result["processed"] >= 1
        assert result["total"] >= 1

    def test_delivery_stats(self, setup_db):
        session = setup_db
        from common_lib.modules.notification.workers.service import DeliveryWorker

        worker = DeliveryWorker(session=session)
        stats = worker.get_stats()
        assert stats["worker_type"] == "delivery"
        assert stats["queue"] == "immediate"

    def test_delivery_missing_event_id(self, setup_db):
        session = setup_db
        from common_lib.modules.notification.workers.service import DeliveryWorker, WorkerTaskService

        task_svc = WorkerTaskService(session=session)
        task_svc.enqueue(
            worker_type="delivery", queue_name="immediate",
            task_type="delivery_dispatch",
            payload={"subscriber_id": "sub_1"},  # missing event_id
        )

        worker = DeliveryWorker(session=session)
        result = asyncio.run(worker.run_once(limit=5))
        assert result["failed"] >= 1  # should fail gracefully


# ═══════════════════════════════════════════════════════════════════════
# RetryWorker
# ═══════════════════════════════════════════════════════════════════════


class TestRetryWorker:
    def test_retry_worker_enqueue_and_run(self, setup_db):
        session = setup_db
        from common_lib.modules.notification.workers.service import RetryWorker, WorkerTaskService

        task_svc = WorkerTaskService(session=session)
        task_svc.enqueue(
            worker_type="retry", queue_name="retry",
            task_type="delivery_retry",
            payload={
                "event_id": "evt_1", "subscriber_id": "sub_1",
                "channel": "email", "error": "timeout",
            },
            max_attempts=3,
        )

        worker = RetryWorker(session=session)
        result = asyncio.run(worker.run_once(limit=5))

        assert result["processed"] >= 1
        assert result["total"] >= 1


# ═══════════════════════════════════════════════════════════════════════
# BroadcastWorker
# ═══════════════════════════════════════════════════════════════════════


class TestBroadcastWorker:
    def test_start_broadcast(self, setup_db):
        session = setup_db
        from common_lib.modules.notification.workers.service import BroadcastWorker

        worker = BroadcastWorker(session=session)
        result = worker.start_broadcast(
            campaign_id="camp_1", template_id="tmpl_1",
            recipient_ids=["user_1", "user_2", "user_3"],
            channel="email", batch_size=2,
        )

        assert result["job_id"] is not None
        assert result["campaign_id"] == "camp_1"
        assert result["total"] == 3

    def test_broadcast_progress(self, setup_db):
        session = setup_db
        from common_lib.modules.notification.workers.service import BroadcastWorker

        worker = BroadcastWorker(session=session)
        worker.start_broadcast(
            campaign_id="camp_2", template_id="tmpl_1",
            recipient_ids=["u1", "u2"], channel="email",
        )

        progress = worker.get_broadcast_progress(campaign_id="camp_2")
        assert progress is not None
        assert progress["campaign_id"] == "camp_2"
        assert progress["status"] == "running"
        assert progress["total_recipients"] == 2

    def test_broadcast_not_found(self, setup_db):
        session = setup_db
        from common_lib.modules.notification.workers.service import BroadcastWorker

        worker = BroadcastWorker(session=session)
        progress = worker.get_broadcast_progress(campaign_id="nonexistent")
        assert progress is None

    def test_pause_resume_broadcast(self, setup_db):
        session = setup_db
        from common_lib.modules.notification.workers.service import BroadcastWorker

        worker = BroadcastWorker(session=session)
        worker.start_broadcast(
            campaign_id="camp_3", template_id="tmpl_1",
            recipient_ids=["u1"], channel="email",
        )

        assert worker.pause_broadcast("camp_3") is True
        progress = worker.get_broadcast_progress("camp_3")
        assert progress["status"] == "paused"

        assert worker.resume_broadcast("camp_3") is True
        progress = worker.get_broadcast_progress("camp_3")
        assert progress["status"] == "running"

    def test_pause_nonexistent(self, setup_db):
        session = setup_db
        from common_lib.modules.notification.workers.service import BroadcastWorker

        worker = BroadcastWorker(session=session)
        assert worker.pause_broadcast("nonexistent") is False
        assert worker.resume_broadcast("nonexistent") is False


# ═══════════════════════════════════════════════════════════════════════
# CleanupWorker
# ═══════════════════════════════════════════════════════════════════════


class TestCleanupWorker:
    def test_create_cleanup_policy(self, setup_db):
        session = setup_db
        from common_lib.modules.notification.workers.models import CleanupPolicy

        policy = CleanupPolicy(
            name="archive_deliveries_90d", target="delivery_attempts",
            retention_days=90, schedule_cron="0 3 * * *",
        )
        session.add(policy)
        session.commit()
        session.refresh(policy)

        assert policy.id is not None
        assert policy.name == "archive_deliveries_90d"
        assert policy.enabled is True

    def test_cleanup_archives_old_deliveries(self, setup_db):
        session = setup_db
        from common_lib.modules.notification.delivery.models import DeliveryAttempt
        from common_lib.modules.notification.workers.service import CleanupWorker

        # Create old delivery attempts
        old_time = datetime.utcnow() - timedelta(days=200)
        for i in range(3):
            attempt = DeliveryAttempt(
                event_id=f"evt_{i}", subscriber_id="sub_1",
                channel="email", status="delivered",
                created_at=old_time,
            )
            session.add(attempt)
        session.commit()

        # Create recent delivery attempt (should NOT be archived)
        recent = DeliveryAttempt(
            event_id="evt_recent", subscriber_id="sub_1",
            channel="email", status="delivered",
            created_at=datetime.utcnow(),
        )
        session.add(recent)
        session.commit()

        worker = CleanupWorker(session=session)
        result = asyncio.run(worker._archive_deliveries({
            "retention_days": 90, "batch_size": 500,
        }))

        assert result["archived"] == 3
        assert result["target"] == "delivery_attempts"

    def test_cleanup_policy_execution(self, setup_db):
        session = setup_db
        from common_lib.modules.notification.workers.models import CleanupPolicy
        from common_lib.modules.notification.workers.service import CleanupWorker

        # Create a cleanup policy
        policy = CleanupPolicy(
            name="full_cleanup", target="all",
            retention_days=90, batch_size=500,
            enabled=True,
        )
        session.add(policy)
        session.commit()

        worker = CleanupWorker(session=session)
        # Run just the archive_deliveries (which uses DeliveryAttempt - none exist so 0 archived)
        result = asyncio.run(worker._archive_deliveries({
            "retention_days": 90, "batch_size": 500,
        }))

        assert result["archived"] == 0
        assert result["target"] == "delivery_attempts"

        # Also verify policies_updated by running full policy
        result = asyncio.run(worker._run_cleanup_policy({
            "retention_days": 90, "batch_size": 500,
        }))
        assert "results" in result
