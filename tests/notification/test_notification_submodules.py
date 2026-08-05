"""
Comprehensive tests for all notification submodules.

Tests use SQLite in-memory database with only notification tables created.
"""

from __future__ import annotations

import pytest
from unittest.mock import patch
from sqlmodel import Session, create_engine, SQLModel


_NOTIFICATION_MODELS = []


def _collect_notification_models():
    """Collect all notification models and register them with SQLModel.metadata."""
    global _NOTIFICATION_MODELS
    if not _NOTIFICATION_MODELS:
        from common_lib.modules.notification.core.models import NotificationTopic, EventSchema
        from common_lib.modules.notification.publisher.models import PublishedEvent
        from common_lib.modules.notification.subscriber.models import EventSubscription
        from common_lib.modules.notification.bus.models import BusTopic, ConsumerGroup
        from common_lib.modules.notification.delivery.models import (
            DeliveryAttempt, DeadLetterEntry, RetryPolicy,
        )
        from common_lib.modules.notification.templates.models import NotificationTemplate
        from common_lib.modules.notification.event_store.models import StoredEvent
        from common_lib.modules.notification.throttle.models import RateLimitConfig
        from common_lib.modules.notification.webhooks.models import WebhookEndpoint
        from common_lib.modules.notification.center.models import NotificationInbox, NotificationDigest
        from common_lib.modules.notification.preferences.models import (
            UserNotificationPreference, TeamNotificationPreference, QuietHoursSchedule,
        )
        from common_lib.modules.notification.mentions.models import MentionNotification
        from common_lib.modules.notification.channels.models import ChannelConfig
        from common_lib.modules.notification.realtime.models import RealtimeConnection
        _NOTIFICATION_MODELS = [NotificationTopic, EventSchema, PublishedEvent, EventSubscription,
                                BusTopic, ConsumerGroup, DeliveryAttempt, DeadLetterEntry,
                                RetryPolicy, NotificationTemplate, StoredEvent, RateLimitConfig,
                                WebhookEndpoint, NotificationInbox, NotificationDigest,
                                UserNotificationPreference, TeamNotificationPreference,
                                QuietHoursSchedule, MentionNotification, ChannelConfig, RealtimeConnection]
    return _NOTIFICATION_MODELS


@pytest.fixture
def session():
    """Create an in-memory SQLite session with only notification tables."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    models = _collect_notification_models()
    tables = [m.__table__ for m in models if hasattr(m, '__table__')]
    SQLModel.metadata.create_all(engine, tables=tables)
    with Session(engine) as s:
        yield s


# ===========================================================================
# Core Submodule
# ===========================================================================

class TestCoreSubmodule:
    """Test core/ — topic registry and schema registry."""

    def test_register_topic(self, session):
        from common_lib.modules.notification.core.service import TopicRegistry
        reg = TopicRegistry(session)
        result = reg.register_topic("test.topic", "A test topic")
        assert result["name"] == "test.topic"
        assert "id" in result

    def test_list_topics(self, session):
        from common_lib.modules.notification.core.service import TopicRegistry
        reg = TopicRegistry(session)
        reg.register_topic("topic.one")
        reg.register_topic("topic.two")
        topics = reg.list_topics()
        assert len(topics) == 2

    def test_register_schema(self, session):
        from common_lib.modules.notification.core.service import SchemaRegistry
        reg = SchemaRegistry(session)
        result = reg.register_schema("issue.created", required_fields=["issue_id", "project_id"])
        assert result["event_type"] == "issue.created"

    def test_validate_payload(self, session):
        from common_lib.modules.notification.core.service import SchemaRegistry
        reg = SchemaRegistry(session)
        reg.register_schema("issue.created", required_fields=["issue_id", "project_id"])
        result = reg.validate_payload("issue.created", {"issue_id": "123"})
        assert result["valid"] is False
        assert any("project_id" in e for e in result["errors"])


# ===========================================================================
# Publisher Submodule
# ===========================================================================

class TestPublisherSubmodule:
    """Test publisher/ — event publishing."""

    def test_publish_event(self, session):
        from common_lib.modules.notification.publisher.service import PublisherService
        svc = PublisherService(session)
        result = svc.publish("user.login", {"user_id": "u1"}, topic="auth")
        assert result["status"] == "published"
        assert result["event_type"] == "user.login"

    def test_bulk_publish(self, session):
        from common_lib.modules.notification.publisher.service import PublisherService
        svc = PublisherService(session)
        results = svc.bulk_publish([
            {"event_type": "e1", "payload": {"k": "v1"}},
            {"event_type": "e2", "payload": {"k": "v2"}},
        ])
        assert len(results) == 2

    def test_list_published(self, session):
        from common_lib.modules.notification.publisher.service import PublisherService
        svc = PublisherService(session)
        svc.publish("user.login", {}, topic="auth")
        svc.publish("user.logout", {}, topic="auth")
        events = svc.list_published(topic="auth")
        assert len(events) == 2

    def test_get_published(self, session):
        from common_lib.modules.notification.publisher.service import PublisherService
        svc = PublisherService(session)
        result = svc.publish("test.event", {"data": "value"})
        event = svc.get_published(result["id"])
        assert event is not None
        assert event["event_type"] == "test.event"


# ===========================================================================
# Subscriber Submodule
# ===========================================================================

class TestSubscriberSubmodule:
    """Test subscriber/ — event subscriptions."""

    def test_subscribe(self, session):
        from common_lib.modules.notification.subscriber.service import SubscriberService
        svc = SubscriberService(session)
        result = svc.subscribe("webhook_notifier", "issue.created", handler_type="webhook")
        assert result["event_type"] == "issue.created"
        assert "id" in result

    def test_list_subscriptions(self, session):
        from common_lib.modules.notification.subscriber.service import SubscriberService
        svc = SubscriberService(session)
        svc.subscribe("sub1", "issue.created")
        svc.subscribe("sub2", "issue.updated")
        subs = svc.list_subscriptions()
        assert len(subs) == 2

    def test_dispatch_finds_matching_subs(self, session):
        from common_lib.modules.notification.subscriber.service import SubscriberService
        svc = SubscriberService(session)
        svc.subscribe("sub1", "issue.created")
        results = svc.dispatch("issue.created", {"issue_id": "123"})
        assert len(results) == 1
        assert results[0]["status"] == "matched"


# ===========================================================================
# Bus Submodule
# ===========================================================================

class TestBusSubmodule:
    """Test bus/ — topics, consumer groups."""

    def test_create_topic(self, session):
        from common_lib.modules.notification.bus.service import EventBus
        bus = EventBus(session)
        result = bus.create_topic("notifications", "General notifications")
        assert result["name"] == "notifications"

    def test_list_topics(self, session):
        from common_lib.modules.notification.bus.service import EventBus
        bus = EventBus(session)
        bus.create_topic("t1")
        bus.create_topic("t2")
        topics = bus.list_topics()
        assert len(topics) == 2

    def test_create_consumer_group(self, session):
        from common_lib.modules.notification.bus.service import EventBus
        bus = EventBus(session)
        topic = bus.create_topic("events")
        cg = bus.create_consumer_group("email_workers", topic["id"])
        assert cg["name"] == "email_workers"

    def test_list_consumer_groups(self, session):
        from common_lib.modules.notification.bus.service import EventBus
        bus = EventBus(session)
        topic = bus.create_topic("events")
        bus.create_consumer_group("group1", topic["id"])
        groups = bus.list_consumer_groups(topic_id=topic["id"])
        assert len(groups) == 1


# ===========================================================================
# Delivery Submodule
# ===========================================================================

class TestDeliverySubmodule:
    """Test delivery/ — attempts, DLQ, retry policies."""

    def test_record_attempt(self, session):
        from common_lib.modules.notification.delivery.service import DeliveryService
        svc = DeliveryService(session)
        result = svc.record_attempt("evt-1", "sub-1", "webhook", status="delivered")
        assert result["status"] == "delivered"

    def test_get_attempts(self, session):
        from common_lib.modules.notification.delivery.service import DeliveryService
        svc = DeliveryService(session)
        svc.record_attempt("evt-1", "sub-1", "webhook")
        attempts = svc.get_attempts("evt-1")
        assert len(attempts) == 1

    def test_dlq_add_and_list(self, session):
        from common_lib.modules.notification.delivery.service import DeadLetterQueueService
        dlq = DeadLetterQueueService(session)
        dlq.add("evt-1", "issue.created", "global", {"key": "val"}, "Connection timeout", attempts=3)
        entries = dlq.list()
        assert len(entries) == 1
        assert entries[0]["error"] == "Connection timeout"

    def test_create_retry_policy(self, session):
        from common_lib.modules.notification.delivery.service import DeliveryService
        svc = DeliveryService(session)
        result = svc.create_retry_policy("email_retry", max_attempts=5)
        assert result["name"] == "email_retry"

    def test_compute_backoff(self, session):
        from common_lib.modules.notification.delivery.service import DeliveryService
        svc = DeliveryService(session)
        delay = svc.compute_backoff(3, base_delay=1.0)
        assert 1.5 <= delay <= 4.5


# ===========================================================================
# Templates Submodule
# ===========================================================================

class TestTemplatesSubmodule:
    """Test templates/ — template CRUD and rendering."""

    def test_create_template(self, session):
        from common_lib.modules.notification.templates.service import TemplateService
        svc = TemplateService(session)
        result = svc.create_template("welcome_email", "Hello {{name}}!", content_type="text/plain")
        assert result["name"] == "welcome_email"

    def test_render_template(self, session):
        from common_lib.modules.notification.templates.service import TemplateService
        svc = TemplateService(session)
        svc.create_template("greeting", "Hi {{name}}, welcome to {{app}}!")
        rendered = svc.render("greeting", {"name": "Alice", "app": "MyApp"})
        assert rendered["body"] == "Hi Alice, welcome to MyApp!"

    def test_render_with_subject(self, session):
        from common_lib.modules.notification.templates.service import TemplateService
        svc = TemplateService(session)
        svc.create_template("notification", "Body: {{msg}}", template_subject="Alert: {{type}}")
        rendered = svc.render("notification", {"msg": "Server down", "type": "critical"})
        assert rendered["subject"] == "Alert: critical"

    def test_list_templates(self, session):
        from common_lib.modules.notification.templates.service import TemplateService
        svc = TemplateService(session)
        svc.create_template("t1", "Body 1")
        svc.create_template("t2", "Body 2")
        templates = svc.list_templates()
        assert len(templates) == 2


# ===========================================================================
# Event Store Submodule
# ===========================================================================

class TestEventStoreSubmodule:
    """Test event_store/ — persistent event storage."""

    def test_store_event(self, session):
        from common_lib.modules.notification.event_store.service import EventStoreService
        svc = EventStoreService(session)
        result = svc.store("issue.created", {"issue_id": "123"}, topic="issues")
        assert result["event_type"] == "issue.created"

    def test_query_events(self, session):
        from common_lib.modules.notification.event_store.service import EventStoreService
        svc = EventStoreService(session)
        svc.store("e1", {"k": "v1"}, topic="t1")
        svc.store("e2", {"k": "v2"}, topic="t2")
        result = svc.query(topic="t1")
        assert len(result["events"]) == 1


# ===========================================================================
# Throttle Submodule
# ===========================================================================

class TestThrottleSubmodule:
    """Test throttle/ — rate limiting."""

    def test_configure_limit(self, session):
        from common_lib.modules.notification.throttle.service import ThrottleService
        svc = ThrottleService(session)
        result = svc.configure_limit("api_key_1", limit_per_minute=100, burst_limit=20)
        assert result["key"] == "api_key_1"

    def test_check_limit_allows(self, session):
        from common_lib.modules.notification.throttle.service import ThrottleService
        svc = ThrottleService(session)
        svc.configure_limit("test_key", limit_per_minute=60)
        result = svc.check_limit("test_key")
        assert result["allowed"] is True

    def test_list_limits(self, session):
        from common_lib.modules.notification.throttle.service import ThrottleService
        svc = ThrottleService(session)
        svc.configure_limit("k1", limit_per_minute=10)
        svc.configure_limit("k2", limit_per_minute=20)
        limits = svc.list_limits()
        assert len(limits) >= 2


# ===========================================================================
# Channels Submodule
# ===========================================================================

class TestChannelsSubmodule:
    """Test channels/ — provider registry and fallback."""

    def test_register_provider(self):
        from common_lib.modules.notification.channels.service import ChannelRegistryService
        reg = ChannelRegistryService()
        reg.register("email", DummyChannelProvider())
        providers = reg.list_providers()
        assert "email" in providers

    def test_fallback_all_fail(self):
        from common_lib.modules.notification.channels.service import (
            ChannelRegistryService, ChannelFallbackService,
        )
        reg = ChannelRegistryService()
        fallback = ChannelFallbackService(reg)
        result = fallback.send_with_fallback(["nonexistent"], "user@test.com", "Sub", "Body")
        assert result["success"] is False


class DummyChannelProvider:
    """Dummy provider for testing."""

    def send(self, recipient, subject, body, config=None):
        return {"success": True, "message_id": "mock-123"}

    def health_check(self):
        return True


# ===========================================================================
# Webhooks Submodule
# ===========================================================================

class TestWebhooksSubmodule:
    """Test webhooks/ — endpoint registration and signing."""

    def test_register_endpoint(self, session):
        from common_lib.modules.notification.webhooks.service import WebhookService
        svc = WebhookService(session)
        result = svc.register_endpoint("test_hook", "https://example.com/hook")
        assert result["name"] == "test_hook"

    def test_list_endpoints(self, session):
        from common_lib.modules.notification.webhooks.service import WebhookService
        svc = WebhookService(session)
        svc.register_endpoint("hook1", "https://example.com/1")
        svc.register_endpoint("hook2", "https://example.com/2")
        endpoints = svc.list_endpoints()
        assert len(endpoints) == 2

    def test_sign_and_verify(self):
        from common_lib.modules.notification.webhooks.service import WebhookService
        svc = WebhookService(None)
        sig = svc.sign_payload({"event": "test"}, "my-secret")
        assert svc.verify_signature({"event": "test"}, "my-secret", sig) is True
        assert svc.verify_signature({"event": "test"}, "wrong-secret", sig) is False


# ===========================================================================
# Center Submodule (Existing)
# ===========================================================================

class TestCenterSubmodule:
    """Test center/ — notification inbox."""

    def test_deliver_notification(self, session):
        from common_lib.modules.notification.center.service import NotificationCenterService
        svc = NotificationCenterService(session)
        item = svc.deliver("user-1", "Test Title", "Test Body")
        assert item.title == "Test Title"
        assert item.user_id == "user-1"

    def test_list_notifications(self, session):
        from common_lib.modules.notification.center.service import NotificationCenterService
        svc = NotificationCenterService(session)
        svc.deliver("user-1", "Title 1")
        svc.deliver("user-1", "Title 2")
        items = svc.list_notifications("user-1")
        assert len(items) == 2

    def test_mark_read(self, session):
        from common_lib.modules.notification.center.service import NotificationCenterService
        svc = NotificationCenterService(session)
        item = svc.deliver("user-1", "Title")
        assert svc.mark_read(item.id) is True

    def test_unread_count(self, session):
        from common_lib.modules.notification.center.service import NotificationCenterService
        svc = NotificationCenterService(session)
        svc.deliver("user-1", "Unread 1")
        svc.deliver("user-1", "Unread 2")
        assert svc.get_unread_count("user-1") == 2
        items = svc.list_notifications("user-1")
        svc.mark_read(items[0].id)
        assert svc.get_unread_count("user-1") == 1


# ===========================================================================
# Events Submodule (Merged)
# ===========================================================================

class TestEventsSubmodule:
    """Test events/ — PM event contracts and delivery engine."""

    def test_pm_event_registry_emit(self):
        from common_lib.modules.notification.events import PMEventType, PMEventRegistry
        payload = PMEventRegistry.emit(PMEventType.ISSUE_CREATED, {"issue_id": "123", "project_id": "p1"})
        assert payload.event_type == PMEventType.ISSUE_CREATED
        assert payload.data["issue_id"] == "123"

    def test_pm_event_contracts(self):
        from common_lib.modules.notification.events import PMEventType, PMEventRegistry
        contract = PMEventRegistry.get_contract(PMEventType.SPRINT_STARTED)
        assert "sprint_id" in contract.get("data_keys", [])

    def test_delivery_engine_sync(self):
        from common_lib.modules.notification.events import DeliveryEngine
        from unittest.mock import patch
        engine = DeliveryEngine()
        with patch("urllib.request.urlopen") as mock_urlopen:
            from urllib.error import URLError
            mock_urlopen.side_effect = URLError("mock failure")
            result = engine.deliver_sync("http://any.url", {"test": "data"})
        assert result is not None
        assert result.success is False

    def test_workflow_mapper(self):
        from common_lib.modules.notification.events import WorkflowMapper, EventWorkflowMapping
        mapper = WorkflowMapper()
        mapper.load_mappings([
            EventWorkflowMapping(event_type="pm.issue.created", workflow_id="wf-1"),
        ])
        mappings = mapper.find_mappings_for_event("pm.issue.created")
        assert len(mappings) == 1
        assert mappings[0].workflow_id == "wf-1"
