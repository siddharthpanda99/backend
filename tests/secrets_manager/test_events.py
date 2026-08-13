"""Tests for Secrets Manager Events submodule (SSOT §19)."""

from __future__ import annotations

from common_lib.modules.secrets_manager.events.service import EventService


class TestEventService:
    """Test event emission, alert rules, and subscriptions."""

    def test_emit_event(self, db):
        svc = EventService(session=db)
        result = svc.emit(
            event_type="secret.created",
            actor_id="user-1",
            resource_id="sec-001",
            resource_name="api-key",
        )
        assert result["event_type"] == "secret.created"
        assert "id" in result
        assert result["alerts_triggered"] == []

    def test_emit_event_with_metadata(self, db):
        svc = EventService(session=db)
        result = svc.emit(
            event_type="lease.created",
            actor_id="system",
            metadata={"ttl": 3600, "role": "db-readonly"},
        )
        assert result["event_type"] == "lease.created"

    def test_query_events_empty(self, db):
        svc = EventService(session=db)
        result = svc.query_events()
        assert result["total"] == 0
        assert result["items"] == []

    def test_query_events(self, db):
        svc = EventService(session=db)
        svc.emit(event_type="secret.created", actor_id="user-1")
        svc.emit(event_type="secret.deleted", actor_id="user-1")
        result = svc.query_events()
        assert result["total"] == 2

    def test_query_events_filter_by_type(self, db):
        svc = EventService(session=db)
        svc.emit(event_type="secret.created")
        svc.emit(event_type="secret.deleted")
        result = svc.query_events(event_type="secret.created")
        assert result["total"] == 1
        assert result["items"][0]["event_type"] == "secret.created"

    def test_query_events_filter_by_actor(self, db):
        svc = EventService(session=db)
        svc.emit(event_type="secret.created", actor_id="alice")
        svc.emit(event_type="secret.deleted", actor_id="bob")
        result = svc.query_events(actor_id="alice")
        assert result["total"] == 1

    def test_create_alert_rule(self, db):
        svc = EventService(session=db)
        result = svc.create_alert_rule(
            name="Rotation Failure Alert",
            event_type="rotation.failed",
            severity="critical",
            description="Alert when a secret rotation fails",
        )
        assert result["name"] == "Rotation Failure Alert"
        assert result["event_type"] == "rotation.failed"

    def test_list_alert_rules(self, db):
        svc = EventService(session=db)
        svc.create_alert_rule(name="Alert-A", event_type="secret.created")
        svc.create_alert_rule(name="Alert-B", event_type="secret.deleted")
        rules = svc.list_alert_rules()
        assert len(rules) == 2

    def test_alert_rule_triggers_on_event(self, db):
        svc = EventService(session=db)
        svc.create_alert_rule(
            name="Auth-Failure-Alert",
            event_type="auth.login.failure",
            severity="warning",
        )
        result = svc.emit(event_type="auth.login.failure", actor_id="user-1")
        assert len(result["alerts_triggered"]) == 1
        assert result["alerts_triggered"][0]["severity"] == "warning"

    def test_toggle_alert_rule(self, db):
        svc = EventService(session=db)
        rule = svc.create_alert_rule(name="Toggle-Test", event_type="secret.created")
        assert svc.toggle_alert_rule(rule["id"], enabled=False) is True
        assert svc.toggle_alert_rule("nonexistent", enabled=True) is False

    def test_create_subscription(self, db):
        svc = EventService(session=db)
        result = svc.create_subscription(
            name="webhook-1",
            webhook_url="https://hooks.example.com/events",
            event_types=["secret.created", "secret.deleted"],
        )
        assert result["name"] == "webhook-1"
        assert "id" in result

    def test_list_subscriptions(self, db):
        svc = EventService(session=db)
        svc.create_subscription(name="sub-1", webhook_url="https://hook1.example.com")
        svc.create_subscription(name="sub-2", webhook_url="https://hook2.example.com")
        subs = svc.list_subscriptions()
        assert len(subs) == 2

    def test_sign_event_payload(self, db):
        svc = EventService(session=db)
        sig = svc.sign_event_payload({"event": "test"}, "my-secret-key")
        assert sig.startswith("sha256=")
        assert len(sig) > 50
