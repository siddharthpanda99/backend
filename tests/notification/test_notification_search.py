"""
Tests for Notification Search — keyword, full-text, metadata, recipient,
status, date range, template, provider, and audit search (SSOT §29).

Uses isolated sqlalchemy.MetaData to avoid cross-module table conflicts.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timedelta
from sqlalchemy import MetaData, Table, Column, String, Integer, Float, Boolean, DateTime, JSON, Text
from sqlmodel import Session, create_engine


# ── Fixture ────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def setup_db():
    """Create search index table in an in-memory SQLite database."""
    meta = MetaData()

    Table("notification_search_index", meta,
        Column("id", String, primary_key=True),
        Column("notification_id", String),
        Column("event_id", String),
        Column("delivery_id", String, nullable=True),
        Column("tenant_id", String, nullable=True),
        Column("title", String),
        Column("subject", String, nullable=True),
        Column("body_preview", String, nullable=True),
        Column("full_text", String, nullable=True),
        Column("keywords", String, nullable=True),
        Column("notification_type", String),
        Column("category", String, nullable=True),
        Column("channel", String, nullable=True),
        Column("priority", String, nullable=True),
        Column("template_id", String, nullable=True),
        Column("template_name", String, nullable=True),
        Column("recipient_id", String, nullable=True),
        Column("recipient_email", String, nullable=True),
        Column("recipient_name", String, nullable=True),
        Column("status", String),
        Column("provider", String, nullable=True),
        Column("provider_message_id", String, nullable=True),
        Column("attempt_count", Integer, default=0),
        Column("error", String, nullable=True),
        Column("extra_metadata", JSON, nullable=True),
        Column("created_at", DateTime),
        Column("sent_at", DateTime, nullable=True),
        Column("delivered_at", DateTime, nullable=True),
        Column("read_at", DateTime, nullable=True),
        Column("updated_at", DateTime),
    )

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    meta.create_all(engine)

    session = Session(engine)
    yield session
    session.close()


def _get_svc(session):
    from common_lib.modules.notification.search.service import NotificationSearchService
    return NotificationSearchService(session=session)


def _seed_search_data(session):
    """Seed sample notification documents for search tests."""
    svc = _get_svc(session)
    now = datetime.utcnow()

    docs = [
        {
            "notification_id": "notif_001", "event_id": "evt_001",
            "title": "Password Reset Requested",
            "notification_type": "transactional", "status": "delivered",
            "recipient_id": "user_1", "recipient_email": "alice@example.com",
            "channel": "email", "priority": "high",
            "keywords": "password, security, reset",
            "created_at": now - timedelta(hours=1),
            "delivered_at": now - timedelta(minutes=55),
        },
        {
            "notification_id": "notif_002", "event_id": "evt_002",
            "title": "Task Assigned: Fix Login Bug",
            "notification_type": "workflow", "status": "delivered",
            "recipient_id": "user_2", "recipient_email": "bob@example.com",
            "channel": "in_app", "priority": "medium",
            "keywords": "task, assigned, bug",
            "created_at": now - timedelta(hours=1, minutes=50),
            "delivered_at": now - timedelta(hours=1, minutes=45),
        },
        {
            "notification_id": "notif_003", "event_id": "evt_003",
            "title": "Your invoice is ready",
            "notification_type": "billing", "status": "delivered",
            "recipient_id": "user_1", "recipient_email": "alice@example.com",
            "channel": "email", "priority": "high",
            "provider": "sendgrid",
            "keywords": "invoice, billing, payment",
            "created_at": now - timedelta(days=1),
            "delivered_at": now - timedelta(hours=23),
        },
        {
            "notification_id": "notif_004", "event_id": "evt_004",
            "title": "Sprint Planning Reminder",
            "notification_type": "workflow", "status": "pending",
            "recipient_id": "user_3", "recipient_email": "carol@example.com",
            "channel": "email", "priority": "low",
            "keywords": "sprint, planning, reminder",
            "created_at": now - timedelta(minutes=30),
        },
        {
            "notification_id": "notif_005", "event_id": "evt_005",
            "title": "Payment Failed",
            "notification_type": "billing", "status": "failed",
            "recipient_id": "user_2", "recipient_email": "bob@example.com",
            "channel": "email", "priority": "critical",
            "error": "card_declined",
            "provider": "sendgrid",
            "keywords": "payment, failed, declined",
            "template_id": "tmpl_billing_failure",
            "created_at": now - timedelta(hours=6),
        },
    ]

    for doc in docs:
        svc.index_notification(**doc)

    return svc, now


# ═══════════════════════════════════════════════════════════════════════
# Indexing
# ═══════════════════════════════════════════════════════════════════════


class TestSearchIndexing:
    def test_index_notification(self, setup_db):
        session = setup_db
        from common_lib.modules.notification.search.service import NotificationSearchService
        svc = NotificationSearchService(session=session)

        result = svc.index_notification(
            notification_id="notif_001", event_id="evt_001",
            title="Test Notification", notification_type="test",
            status="pending",
        )
        assert result["notification_id"] == "notif_001"
        assert result["indexed"] is True

    def test_update_status(self, setup_db):
        session = setup_db
        from common_lib.modules.notification.search.service import NotificationSearchService
        svc = NotificationSearchService(session=session)

        svc.index_notification("n1", "e1", "Test", "test")
        assert svc.update_status("n1", "delivered", delivered_at=datetime.utcnow()) is True
        assert svc.update_status("nonexistent", "delivered") is False

    def test_delete_index(self, setup_db):
        session = setup_db
        from common_lib.modules.notification.search.service import NotificationSearchService
        svc = NotificationSearchService(session=session)

        svc.index_notification("n1", "e1", "Test", "test")
        assert svc.delete_index("n1") is True
        assert svc.delete_index("n1") is False  # Already deleted


# ═══════════════════════════════════════════════════════════════════════
# Keyword Search
# ═══════════════════════════════════════════════════════════════════════


class TestKeywordSearch:
    def test_keyword_search_title(self, setup_db):
        session = setup_db
        svc, _ = _seed_search_data(session)

        result = svc.search_keyword("Password")
        assert result["total"] == 1
        assert result["results"][0]["notification_id"] == "notif_001"

    def test_keyword_search_keywords_field(self, setup_db):
        session = setup_db
        svc, _ = _seed_search_data(session)

        result = svc.search_keyword("sprint")
        assert result["total"] >= 1

    def test_keyword_search_recipient(self, setup_db):
        session = setup_db
        svc, _ = _seed_search_data(session)

        result = svc.search_keyword("alice")
        assert result["total"] == 2

    def test_keyword_no_match(self, setup_db):
        session = setup_db
        svc, _ = _seed_search_data(session)

        result = svc.search_keyword("zzz_nonexistent_zzz")
        assert result["total"] == 0

    def test_keyword_case_insensitive(self, setup_db):
        session = setup_db
        svc, _ = _seed_search_data(session)

        result = svc.search_keyword("PASSWORD")
        assert result["total"] == 1

    def test_keyword_partial_match(self, setup_db):
        session = setup_db
        svc, _ = _seed_search_data(session)

        result = svc.search_keyword("pay")
        assert result["total"] >= 1


# ═══════════════════════════════════════════════════════════════════════
# Multi-Dimensional Search
# ═══════════════════════════════════════════════════════════════════════


class TestMultiDimensionalSearch:
    def test_search_by_type(self, setup_db):
        session = setup_db
        svc, _ = _seed_search_data(session)

        result = svc.search_by_type("billing")
        assert result["total"] == 2

    def test_search_by_status(self, setup_db):
        session = setup_db
        svc, _ = _seed_search_data(session)

        result = svc.search_by_status("failed")
        assert result["total"] == 1
        assert result["results"][0]["notification_id"] == "notif_005"

    def test_search_by_recipient(self, setup_db):
        session = setup_db
        svc, _ = _seed_search_data(session)

        result = svc.search_by_recipient("user_1")
        assert result["total"] == 2

    def test_search_by_recipient_with_status(self, setup_db):
        session = setup_db
        svc, _ = _seed_search_data(session)

        result = svc.search(recipient_id="user_2", status="failed")
        assert result["total"] == 1
        assert result["results"][0]["notification_id"] == "notif_005"

    def test_search_by_template(self, setup_db):
        session = setup_db
        svc, _ = _seed_search_data(session)

        result = svc.search_by_template("tmpl_billing_failure")
        assert result["total"] == 1

    def test_search_by_provider(self, setup_db):
        session = setup_db
        svc, _ = _seed_search_data(session)

        result = svc.search_by_provider("sendgrid")
        assert result["total"] == 2

    def test_search_combined_filters(self, setup_db):
        session = setup_db
        svc, _ = _seed_search_data(session)

        result = svc.search(
            notification_type="billing",
            provider="sendgrid",
            status="failed",
        )
        assert result["total"] == 1
        assert result["results"][0]["notification_id"] == "notif_005"

    def test_search_all(self, setup_db):
        session = setup_db
        svc, _ = _seed_search_data(session)

        result = svc.search()
        assert result["total"] == 5


# ═══════════════════════════════════════════════════════════════════════
# Date Range Search
# ═══════════════════════════════════════════════════════════════════════


class TestDateRangeSearch:
    def test_search_last_hour(self, setup_db):
        session = setup_db
        svc, seed_now = _seed_search_data(session)

        result = svc.search_by_date_range(
            date_from=seed_now - timedelta(hours=2),
            date_to=seed_now,
        )
        assert result["total"] == 3  # notif_001, notif_002, notif_004

    def test_search_last_12_hours(self, setup_db):
        session = setup_db
        svc, seed_now = _seed_search_data(session)

        result = svc.search_by_date_range(
            date_from=seed_now - timedelta(hours=12),
            date_to=seed_now,
        )
        assert result["total"] == 4  # notif_001, notif_002, notif_004, notif_005

    def test_search_date_delivered_field(self, setup_db):
        session = setup_db
        svc, seed_now = _seed_search_data(session)

        result = svc.search_by_date_range(
            date_from=seed_now - timedelta(days=2),
            date_to=seed_now,
            date_field="delivered_at",
        )
        assert result["total"] == 3  # 3 delivered notifications


# ═══════════════════════════════════════════════════════════════════════
# Audit Search
# ═══════════════════════════════════════════════════════════════════════


class TestAuditSearch:
    def test_audit_by_event_id(self, setup_db):
        session = setup_db
        svc, _ = _seed_search_data(session)

        result = svc.search_audit(event_id="evt_003")
        assert result["total"] == 1

    def test_audit_by_notification_id(self, setup_db):
        session = setup_db
        svc, _ = _seed_search_data(session)

        result = svc.search_audit(notification_id="notif_005")
        assert result["total"] == 1

    def test_audit_pagination(self, setup_db):
        session = setup_db
        svc, _ = _seed_search_data(session)

        result = svc.search(limit=2, offset=0)
        assert len(result["results"]) == 2
        assert result["total"] == 5

        result_page2 = svc.search(limit=2, offset=2)
        assert len(result_page2["results"]) == 2


# ═══════════════════════════════════════════════════════════════════════
# Batch & Stats
# ═══════════════════════════════════════════════════════════════════════


class TestBatchAndStats:
    def test_batch_index(self, setup_db):
        session = setup_db
        svc = _get_svc(session)

        docs = [
            {"notification_id": "b1", "event_id": "e1", "title": "Batch 1",
             "notification_type": "test", "status": "pending"},
            {"notification_id": "b2", "event_id": "e2", "title": "Batch 2",
             "notification_type": "test", "status": "delivered"},
        ]
        result = svc.batch_index(docs)
        assert result["indexed"] == 2
        assert result["errors"] == 0

    def test_get_index_stats(self, setup_db):
        session = setup_db
        svc, _ = _seed_search_data(session)

        stats = svc.get_index_stats()
        assert stats["total_documents"] == 5
        assert "delivered" in stats["by_status"]
        assert stats["by_status"]["delivered"] == 3
        assert "billing" in stats["by_type"]
