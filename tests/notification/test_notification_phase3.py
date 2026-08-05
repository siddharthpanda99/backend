"""
Tests for Phase 3 notification submodules: deduplication, routing, receipts.
"""

from __future__ import annotations

import pytest
from sqlmodel import Session, create_engine, SQLModel

_MODELS = []


def _collect_models():
    global _MODELS
    if not _MODELS:
        from common_lib.modules.notification.deduplication.models import DeduplicationRule
        from common_lib.modules.notification.routing.models import RouteRule, ChannelPriority
        from common_lib.modules.notification.receipts.models import DeliveryReceipt
        _MODELS = [DeduplicationRule, RouteRule, ChannelPriority, DeliveryReceipt]
    return _MODELS


@pytest.fixture
def session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    models = _collect_models()
    tables = [m.__table__ for m in models if hasattr(m, '__table__')]
    SQLModel.metadata.create_all(engine, tables=tables)
    with Session(engine) as s:
        yield s


# ===========================================================================
# Deduplication
# ===========================================================================

class TestDeduplicationSubmodule:
    """Test deduplication/ — dedup rules and checking."""

    def test_configure_rule(self, session):
        from common_lib.modules.notification.deduplication.service import DeduplicationService
        svc = DeduplicationService(session)
        result = svc.configure_rule("email_dedup", "email.welcome", strategy="content_hash", window_seconds=60)
        assert result["name"] == "email_dedup"

    def test_compute_fingerprint_content_hash(self, session):
        from common_lib.modules.notification.deduplication.service import DeduplicationService
        svc = DeduplicationService(session)
        fp = svc.compute_fingerprint("issue.created", {"issue_id": "123"})
        # sha256 hex digest — 16 chars (truncated), all hex chars a-f,0-9
        assert len(fp) == 16, f"Expected 16 chars, got {len(fp)}: {fp!r}"
        assert all(c in "0123456789abcdef" for c in fp), f"Non-hex char in fingerprint: {fp!r}"

    def test_compute_fingerprint_idempotency_key(self, session):
        from common_lib.modules.notification.deduplication.service import DeduplicationService
        svc = DeduplicationService(session)
        fp = svc.compute_fingerprint("issue.created", {}, correlation_id="idem-123", strategy="idempotency_key")
        assert fp == "idem:idem-123"

    def test_is_duplicate_first_call(self, session):
        from common_lib.modules.notification.deduplication.service import DeduplicationService
        svc = DeduplicationService(session)
        result = svc.is_duplicate("issue.created", {"id": "1"})
        assert result["is_duplicate"] is False

    def test_is_duplicate_second_call(self, session):
        from common_lib.modules.notification.deduplication.service import DeduplicationService
        svc = DeduplicationService(session)
        svc.is_duplicate("issue.created", {"id": "1"})
        result = svc.is_duplicate("issue.created", {"id": "1"})
        assert result["is_duplicate"] is True

    def test_list_rules(self, session):
        from common_lib.modules.notification.deduplication.service import DeduplicationService
        svc = DeduplicationService(session)
        svc.configure_rule("r1", "type.a")
        svc.configure_rule("r2", "type.b")
        rules = svc.list_rules()
        assert len(rules) >= 2

    def test_clear_cache(self, session):
        from common_lib.modules.notification.deduplication.service import DeduplicationService
        svc = DeduplicationService(session)
        svc.is_duplicate("test", {"k": "v"})
        count = svc.clear_cache()
        assert count >= 1


# ===========================================================================
# Routing
# ===========================================================================

class TestRoutingSubmodule:
    """Test routing/ — channel routing and priority."""

    def test_create_route_rule(self, session):
        from common_lib.modules.notification.routing.service import RoutingService
        svc = RoutingService(session)
        result = svc.create_route_rule("issue_alert", "issue.created", ["in_app", "email"], priority="high")
        assert result["name"] == "issue_alert"
        assert result["notification_type"] == "issue.created"

    def test_resolve_channels_with_rule(self, session):
        from common_lib.modules.notification.routing.service import RoutingService
        svc = RoutingService(session)
        svc.create_route_rule("email_alert", "alert.system", ["sms", "email"], priority="critical")
        result = svc.resolve_channels("alert.system")
        assert result["channels"] == ["sms", "email"]
        assert result["priority"] == "critical"

    def test_resolve_channels_default(self, session):
        from common_lib.modules.notification.routing.service import RoutingService
        svc = RoutingService(session)
        result = svc.resolve_channels("unknown.type")
        assert result["channels"] == ["in_app"]

    def test_set_channel_priority(self, session):
        from common_lib.modules.notification.routing.service import RoutingService
        svc = RoutingService(session)
        result = svc.set_channel_priority("tenant-1", "email", priority_order=1, provider="sendgrid")
        assert result["channel"] == "email"
        assert result["priority"] == 1

    def test_list_rules(self, session):
        from common_lib.modules.notification.routing.service import RoutingService
        svc = RoutingService(session)
        svc.create_route_rule("r1", "type.a", ["email"])
        svc.create_route_rule("r2", "type.b", ["sms"])
        rules = svc.list_rules()
        assert len(rules) >= 2

    def test_delete_rule(self, session):
        from common_lib.modules.notification.routing.service import RoutingService
        svc = RoutingService(session)
        result = svc.create_route_rule("to_delete", "test.delete", ["log"])
        assert svc.delete_rule(result["id"]) is True


# ===========================================================================
# Receipts
# ===========================================================================

class TestReceiptsSubmodule:
    """Test receipts/ — delivery receipts and engagement."""

    def test_record_delivery(self, session):
        from common_lib.modules.notification.receipts.service import ReceiptService
        svc = ReceiptService(session)
        result = svc.record_delivery("del-1", "notif-1", "email", provider_message_id="pm-123")
        assert result["delivery_id"] == "del-1"
        assert result["status"] == "delivered"

    def test_record_bounce(self, session):
        from common_lib.modules.notification.receipts.service import ReceiptService
        svc = ReceiptService(session)
        result = svc.record_bounce("del-2", "notif-1", "email", "Hard bounce: invalid address")
        assert result["status"] == "bounced"

    def test_get_receipt(self, session):
        from common_lib.modules.notification.receipts.service import ReceiptService
        svc = ReceiptService(session)
        svc.record_delivery("del-3", "notif-1", "sms")
        receipt = svc.get_receipt("del-3")
        assert receipt is not None
        assert receipt["channel"] == "sms"

    def test_mark_read(self, session):
        from common_lib.modules.notification.receipts.service import ReceiptService
        svc = ReceiptService(session)
        svc.record_delivery("del-4", "notif-1", "email")
        assert svc.record_read("del-4") is True

    def test_mark_read_not_found(self, session):
        from common_lib.modules.notification.receipts.service import ReceiptService
        svc = ReceiptService(session)
        assert svc.record_read("nonexistent") is False

    def test_get_stats(self, session):
        from common_lib.modules.notification.receipts.service import ReceiptService
        svc = ReceiptService(session)
        svc.record_delivery("d1", "n1", "email")
        svc.record_delivery("d2", "n1", "sms")
        svc.record_bounce("d3", "n1", "email", "bounce")
        stats = svc.get_stats("n1")
        assert stats["total"] == 3
        assert stats["delivered"] == 2
        assert stats["bounced"] == 1
