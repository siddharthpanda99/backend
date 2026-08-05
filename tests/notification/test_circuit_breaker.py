"""Tests for Circuit Breaker service and ProviderConfig (SSOT §22)."""

import pytest
from datetime import datetime, timedelta
from sqlmodel import Session, create_engine, SQLModel
from common_lib.modules.notification.channels.service import CircuitBreakerService
from common_lib.modules.notification.channels.models import ProviderConfig, CircuitBreakerSnapshot


# Register notification models by importing them
from common_lib.modules.notification.channels.models import ChannelConfig  # noqa: F401
from common_lib.modules.notification.delivery.models import DeliveryAttempt, DeadLetterEntry, RetryPolicy  # noqa: F401
from common_lib.modules.notification.core.models import NotificationTopic, EventSchema  # noqa: F401
from common_lib.modules.notification.center.models import NotificationInbox, NotificationDigest  # noqa: F401
from common_lib.modules.notification.preferences.models import UserNotificationPreference, TeamNotificationPreference, QuietHoursSchedule  # noqa: F401
from common_lib.modules.notification.workers.models import WorkerTask  # noqa: F401

NOTIFICATION_TABLES = [
    t for n, t in SQLModel.metadata.tables.items()
    if n.startswith("notification_")
]


@pytest.fixture
def session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine, tables=NOTIFICATION_TABLES)
    s = Session(engine)
    yield s
    s.close()


class TestProviderConfig:
    def test_create_provider_config(self, session):
        svc = CircuitBreakerService(session)
        result = svc.create_provider_config(
            name="smtp-primary",
            channel_type="email",
            provider_class="smtp",
            credential_ref="sm://providers/smtp/prod",
        )
        assert result["name"] == "smtp-primary"
        assert result["channel_type"] == "email"

    def test_list_provider_configs(self, session):
        svc = CircuitBreakerService(session)
        svc.create_provider_config("smtp-1", "email", "smtp")
        svc.create_provider_config("twilio-1", "sms", "twilio")
        configs = svc.list_provider_configs()
        assert len(configs) >= 2

    def test_list_filtered_by_channel(self, session):
        svc = CircuitBreakerService(session)
        svc.create_provider_config("smtp-1", "email", "smtp")
        svc.create_provider_config("twilio-1", "sms", "twilio")
        email_configs = svc.list_provider_configs(channel_type="email")
        assert len(email_configs) == 1
        assert email_configs[0]["channel_type"] == "email"

    def test_get_state_not_found(self, session):
        svc = CircuitBreakerService(session)
        result = svc.get_state("nonexistent")
        assert result is None

    def test_get_state_defaults(self, session):
        svc = CircuitBreakerService(session)
        cfg = svc.create_provider_config("test-provider", "email", "smtp")
        state = svc.get_state(cfg["id"])
        assert state["state"] == "closed"
        assert state["error_count"] == 0


class TestCircuitBreaker:
    def test_check_circuit_no_config(self, session):
        """No provider config = circuit allows requests."""
        svc = CircuitBreakerService(session)
        assert svc.check_circuit("nonexistent") is True

    def test_circuit_closed_allows(self, session):
        svc = CircuitBreakerService(session)
        cfg = svc.create_provider_config("test", "email", "smtp")
        assert svc.check_circuit(cfg["id"]) is True

    def test_circuit_opens_on_errors(self, session):
        svc = CircuitBreakerService(session)
        cfg = svc.create_provider_config("test", "email", "smtp")

        # Error threshold is 5 by default
        for i in range(5):
            svc.record_failure(cfg["id"], error_message=f"Error {i}")

        # Circuit should be open
        state = svc.get_state(cfg["id"])
        assert state["state"] == "open"
        assert state["error_count"] == 5

        # Circuit should block requests
        assert svc.check_circuit(cfg["id"]) is False

    def test_circuit_half_open_after_timeout(self, session):
        """After recovery_timeout, circuit transitions to half_open."""
        svc = CircuitBreakerService(session)
        cfg = svc.create_provider_config("test", "email", "smtp",
                                         config_json={"recovery_timeout_seconds": 0})

        # Override recovery timeout to 0 so it triggers immediately
        db_cfg = session.get(ProviderConfig, cfg["id"])
        db_cfg.recovery_timeout_seconds = 0
        db_cfg.current_error_count = 5
        db_cfg.circuit_state = "open"
        db_cfg.last_failure_at = datetime.utcnow() - timedelta(seconds=10)
        session.add(db_cfg)
        session.commit()

        # Check circuit should transition to half_open and allow probe
        allowed = svc.check_circuit(cfg["id"])
        assert allowed is True  # Probe request allowed

        state = svc.get_state(cfg["id"])
        assert state["state"] == "half_open"

    def test_circuit_closes_after_success(self, session):
        svc = CircuitBreakerService(session)
        cfg = svc.create_provider_config("test", "email", "smtp")

        # Open the circuit
        for i in range(5):
            svc.record_failure(cfg["id"])

        # Manually set to half_open (simulate timeout)
        db_cfg = session.get(ProviderConfig, cfg["id"])
        db_cfg.circuit_state = "half_open"
        session.add(db_cfg)
        session.commit()

        # Record a success - should close the circuit
        svc.record_success(cfg["id"])
        state = svc.get_state(cfg["id"])
        assert state["state"] == "closed"

    def test_record_success_resets_error_count(self, session):
        svc = CircuitBreakerService(session)
        cfg = svc.create_provider_config("test", "email", "smtp")
        svc.record_failure(cfg["id"])
        svc.record_success(cfg["id"])
        state = svc.get_state(cfg["id"])
        assert state["error_count"] == 0

    def test_circuit_breaker_history(self, session):
        svc = CircuitBreakerService(session)
        cfg = svc.create_provider_config("test", "email", "smtp")

        # Trigger some state changes
        for i in range(5):
            svc.record_failure(cfg["id"])

        # Check history
        history = svc.get_history(cfg["id"])
        assert len(history) >= 1
        assert history[0]["trigger"] == "error_threshold"
        assert history[0]["new_state"] == "open"

    def test_record_failure_increments_count(self, session):
        svc = CircuitBreakerService(session)
        cfg = svc.create_provider_config("test", "email", "smtp")
        result = svc.record_failure(cfg["id"], error_message="Connection timeout")
        assert result["error_count"] == 1
        assert result["state"] == "closed"

    def test_second_failure_after_reset(self, session):
        svc = CircuitBreakerService(session)
        cfg = svc.create_provider_config("test", "email", "smtp")
        svc.record_failure(cfg["id"])
        svc.record_success(cfg["id"])  # Resets error count
        svc.record_failure(cfg["id"])  # Start fresh
        state = svc.get_state(cfg["id"])
        assert state["error_count"] == 1
        assert state["state"] == "closed"

    def test_half_open_reopens_on_failure(self, session):
        """Single failure in half_open should immediately reopen the circuit."""
        svc = CircuitBreakerService(session)
        cfg = svc.create_provider_config("test", "email", "smtp")

        # Open the circuit (5 failures)
        for i in range(5):
            svc.record_failure(cfg["id"])

        # Manually set to half_open (simulate timeout recovery)
        db_cfg = session.get(ProviderConfig, cfg["id"])
        db_cfg.circuit_state = "half_open"
        db_cfg.current_error_count = 0
        session.add(db_cfg)
        session.commit()

        # A single failure in half_open should immediately reopen
        result = svc.record_failure(cfg["id"], error_message="half_open error")
        assert result["state"] == "open"

        # Circuit should now block requests
        assert svc.check_circuit(cfg["id"]) is False
