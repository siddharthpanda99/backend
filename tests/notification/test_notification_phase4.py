"""
Tests for Phase 4 notification submodules: campaigns, rules, scheduling, interactive.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timedelta
from sqlmodel import Session, create_engine, SQLModel

_MODELS = []


def _collect_models():
    global _MODELS
    if not _MODELS:
        from common_lib.modules.notification.campaigns.models import Campaign, CampaignRecipient
        from common_lib.modules.notification.rules.models import NotificationRule, Segment
        from common_lib.modules.notification.scheduling.models import ScheduledNotification, RecurringSchedule
        from common_lib.modules.notification.interactive.models import InteractiveAction, ActionCallback
        _MODELS = [Campaign, CampaignRecipient, NotificationRule, Segment,
                   ScheduledNotification, RecurringSchedule, InteractiveAction, ActionCallback]
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
# Campaigns
# ===========================================================================

class TestCampaignsSubmodule:
    """Test campaigns/ — broadcast campaign management."""

    def test_create_campaign(self, session):
        from common_lib.modules.notification.campaigns.service import CampaignService
        svc = CampaignService(session)
        result = svc.create_campaign("Summer Sale", "tpl-1", audience_scope="all", total_count=5000)
        assert result["name"] == "Summer Sale"
        assert result["status"] == "draft"
        assert result["total_count"] == 5000

    def test_get_campaign(self, session):
        from common_lib.modules.notification.campaigns.service import CampaignService
        svc = CampaignService(session)
        created = svc.create_campaign("Test", "tpl-1")
        result = svc.get_campaign(created["id"])
        assert result is not None
        assert result["name"] == "Test"

    def test_get_campaign_not_found(self, session):
        from common_lib.modules.notification.campaigns.service import CampaignService
        svc = CampaignService(session)
        assert svc.get_campaign("nonexistent") is None

    def test_list_campaigns(self, session):
        from common_lib.modules.notification.campaigns.service import CampaignService
        svc = CampaignService(session)
        svc.create_campaign("A", "tpl-1")
        svc.create_campaign("B", "tpl-2")
        results = svc.list_campaigns()
        assert len(results) >= 2

    def test_update_status_pause(self, session):
        from common_lib.modules.notification.campaigns.service import CampaignService
        svc = CampaignService(session)
        created = svc.create_campaign("Pause Test", "tpl-1")
        result = svc.update_status(created["id"], "paused")
        assert result["status"] == "paused"

    def test_update_status_cancel(self, session):
        from common_lib.modules.notification.campaigns.service import CampaignService
        svc = CampaignService(session)
        created = svc.create_campaign("Cancel Test", "tpl-1")
        result = svc.update_status(created["id"], "cancelled")
        assert result["status"] == "cancelled"

    def test_record_progress(self, session):
        from common_lib.modules.notification.campaigns.service import CampaignService
        svc = CampaignService(session)
        created = svc.create_campaign("Progress Test", "tpl-1", total_count=100)
        result = svc.record_progress(created["id"], sent=50, failed=2)
        assert result["sent"] == 50
        assert result["failed"] == 2

    def test_get_progress(self, session):
        from common_lib.modules.notification.campaigns.service import CampaignService
        svc = CampaignService(session)
        created = svc.create_campaign("Progress", "tpl-1", total_count=100)
        svc.record_progress(created["id"], sent=75)
        progress = svc.get_progress(created["id"])
        assert progress["sent"] == 75
        assert progress["progress_pct"] == 75.0

    def test_add_recipient(self, session):
        from common_lib.modules.notification.campaigns.service import CampaignService
        svc = CampaignService(session)
        created = svc.create_campaign("Recip Test", "tpl-1")
        result = svc.add_recipient(created["id"], "user-1", channel="email")
        assert result["recipient_id"] == "user-1"
        assert result["status"] == "pending"


# ===========================================================================
# Rules
# ===========================================================================

class TestRulesSubmodule:
    """Test rules/ — condition evaluation, segments."""

    def test_create_rule(self, session):
        from common_lib.modules.notification.rules.service import RuleService
        svc = RuleService(session)
        result = svc.create_rule("high_priority", "issue.created",
                                  [{"field": "priority", "operator": "equals", "value": "critical"}])
        assert result["name"] == "high_priority"
        assert result["event_type"] == "issue.created"

    def test_list_rules(self, session):
        from common_lib.modules.notification.rules.service import RuleService
        svc = RuleService(session)
        svc.create_rule("r1", "type.a", [{"field": "x", "operator": "equals", "value": 1}])
        svc.create_rule("r2", "type.b", [{"field": "y", "operator": "equals", "value": 2}])
        rules = svc.list_rules()
        assert len(rules) >= 2

    def test_evaluate_match_all(self, session):
        from common_lib.modules.notification.rules.service import RuleService
        svc = RuleService(session)
        svc.create_rule("critical_alert", "alert.system",
                          [{"field": "priority", "operator": "equals", "value": "critical"},
                           {"field": "source", "operator": "equals", "value": "monitor"}],
                          match_all=True)
        matches = svc.evaluate("alert.system", {"priority": "critical", "source": "monitor"})
        assert len(matches) == 1

    def test_evaluate_no_match(self, session):
        from common_lib.modules.notification.rules.service import RuleService
        svc = RuleService(session)
        svc.create_rule("critical_alert", "alert.system",
                          [{"field": "priority", "operator": "equals", "value": "critical"}])
        matches = svc.evaluate("alert.system", {"priority": "low"})
        assert len(matches) == 0

    def test_evaluate_wrong_event_type(self, session):
        from common_lib.modules.notification.rules.service import RuleService
        svc = RuleService(session)
        svc.create_rule("critical_alert", "alert.system",
                          [{"field": "priority", "operator": "equals", "value": "critical"}])
        matches = svc.evaluate("other.type", {"priority": "critical"})
        assert len(matches) == 0

    def test_delete_rule(self, session):
        from common_lib.modules.notification.rules.service import RuleService
        svc = RuleService(session)
        created = svc.create_rule("to_delete", "test", [{"field": "x", "operator": "equals", "value": 1}])
        assert svc.delete_rule(created["id"]) is True
        assert svc.delete_rule("nonexistent") is False

    def test_create_segment(self, session):
        from common_lib.modules.notification.rules.service import RuleService
        svc = RuleService(session)
        result = svc.create_segment("EU Users", {"region": "EU"}, recipient_ids=["u1", "u2"])
        assert result["name"] == "EU Users"
        assert result["recipient_count"] == 2

    def test_list_segments(self, session):
        from common_lib.modules.notification.rules.service import RuleService
        svc = RuleService(session)
        svc.create_segment("SegA", {})
        svc.create_segment("SegB", {})
        segs = svc.list_segments()
        assert len(segs) >= 2

    def test_update_segment_recipients(self, session):
        from common_lib.modules.notification.rules.service import RuleService
        svc = RuleService(session)
        created = svc.create_segment("Test", {}, recipient_ids=["u1"])
        assert svc.update_segment_recipients(created["id"], ["u1", "u2", "u3"]) is True
        recipients = svc.get_segment_recipients(created["id"])
        assert len(recipients) == 3


# ===========================================================================
# Scheduling
# ===========================================================================

class TestSchedulingSubmodule:
    """Test scheduling/ — schedule management, dispatch, recurring."""

    def test_schedule_notification(self, session):
        from common_lib.modules.notification.scheduling.service import SchedulingService
        svc = SchedulingService(session)
        future = datetime.utcnow() + timedelta(hours=1)
        result = svc.schedule_notification("reminder", "user-1", "tpl-1", future)
        assert result["status"] == "pending"
        assert "id" in result

    def test_cancel_scheduled(self, session):
        from common_lib.modules.notification.scheduling.service import SchedulingService
        svc = SchedulingService(session)
        future = datetime.utcnow() + timedelta(hours=1)
        created = svc.schedule_notification("test", "u1", "tpl-1", future)
        assert svc.cancel_scheduled(created["id"]) is True

    def test_cancel_not_found(self, session):
        from common_lib.modules.notification.scheduling.service import SchedulingService
        svc = SchedulingService(session)
        assert svc.cancel_scheduled("nonexistent") is False

    def test_dispatch_due(self, session):
        from common_lib.modules.notification.scheduling.service import SchedulingService
        svc = SchedulingService(session)
        past = datetime.utcnow() - timedelta(minutes=30)
        svc.schedule_notification("reminder", "user-1", "tpl-1", past)
        dispatched = svc.dispatch_due(limit=10)
        assert len(dispatched) >= 1

    def test_dispatch_due_not_yet(self, session):
        from common_lib.modules.notification.scheduling.service import SchedulingService
        svc = SchedulingService(session)
        future = datetime.utcnow() + timedelta(hours=24)
        svc.schedule_notification("reminder", "user-1", "tpl-1", future)
        dispatched = svc.dispatch_due(limit=10)
        # Should NOT dispatch future items
        assert len(dispatched) == 0

    def test_list_pending(self, session):
        from common_lib.modules.notification.scheduling.service import SchedulingService
        svc = SchedulingService(session)
        future = datetime.utcnow() + timedelta(hours=1)
        svc.schedule_notification("test", "u1", "tpl-1", future)
        pending = svc.list_pending()
        assert len(pending) >= 1

    def test_get_due_count(self, session):
        from common_lib.modules.notification.scheduling.service import SchedulingService
        svc = SchedulingService(session)
        past = datetime.utcnow() - timedelta(minutes=30)
        svc.schedule_notification("test", "u1", "tpl-1", past)
        count = svc.get_due_count()
        assert count >= 1

    def test_create_recurring(self, session):
        from common_lib.modules.notification.scheduling.service import SchedulingService
        svc = SchedulingService(session)
        result = svc.create_recurring("daily_digest", "digest", "tpl-1",
                                       schedule_type="cron", cron_expression="0 8 * * *")
        assert result["name"] == "daily_digest"
        assert result["schedule_type"] == "cron"

    def test_list_recurring(self, session):
        from common_lib.modules.notification.scheduling.service import SchedulingService
        svc = SchedulingService(session)
        svc.create_recurring("r1", "digest", "tpl-1", schedule_type="cron", cron_expression="0 8 * * *")
        svc.create_recurring("r2", "digest", "tpl-1", schedule_type="interval", interval_seconds=3600)
        results = svc.list_recurring()
        assert len(results) >= 2

    def test_pause_resume_recurring(self, session):
        from common_lib.modules.notification.scheduling.service import SchedulingService
        svc = SchedulingService(session)
        created = svc.create_recurring("pause_test", "digest", "tpl-1",
                                        schedule_type="cron", cron_expression="0 8 * * *")
        assert svc.pause_recurring(created["id"]) is True
        assert svc.resume_recurring(created["id"]) is True


# ===========================================================================
# Interactive
# ===========================================================================

class TestInteractiveSubmodule:
    """Test interactive/ — action buttons, callbacks, stats."""

    def test_create_action(self, session):
        from common_lib.modules.notification.interactive.service import InteractiveService
        svc = InteractiveService(session)
        result = svc.create_action("notif-1", "Approve", action_type="button", style="primary")
        assert result["label"] == "Approve"
        assert result["action_type"] == "button"

    def test_create_action_with_url(self, session):
        from common_lib.modules.notification.interactive.service import InteractiveService
        svc = InteractiveService(session)
        result = svc.create_action("notif-1", "View Details", action_type="link", url="https://example.com")
        assert result["action_type"] == "link"

    def test_get_actions(self, session):
        from common_lib.modules.notification.interactive.service import InteractiveService
        svc = InteractiveService(session)
        svc.create_action("notif-1", "Approve")
        svc.create_action("notif-1", "Reject", style="danger")
        actions = svc.get_actions("notif-1")
        assert len(actions) == 2

    def test_record_callback(self, session):
        from common_lib.modules.notification.interactive.service import InteractiveService
        svc = InteractiveService(session)
        created = svc.create_action("notif-1", "Approve")
        result = svc.record_callback(
            created["action_id"], "notif-1", "user-1", status="clicked"
        )
        assert result["status"] == "clicked"
        assert result["action_id"] == created["action_id"]

    def test_get_callbacks(self, session):
        from common_lib.modules.notification.interactive.service import InteractiveService
        svc = InteractiveService(session)
        created = svc.create_action("notif-1", "Approve")
        svc.record_callback(created["action_id"], "notif-1", "user-1")
        svc.record_callback(created["action_id"], "notif-1", "user-2")
        callbacks = svc.get_callbacks("notif-1")
        assert len(callbacks) == 2

    def test_get_action_stats(self, session):
        from common_lib.modules.notification.interactive.service import InteractiveService
        svc = InteractiveService(session)
        created = svc.create_action("notif-1", "Approve")
        svc.record_callback(created["action_id"], "notif-1", "user-1", status="clicked")
        svc.record_callback(created["action_id"], "notif-1", "user-2", status="confirmed")
        svc.record_callback(created["action_id"], "notif-1", "user-3", status="dismissed")
        stats = svc.get_action_stats("notif-1")
        assert stats["total_callbacks"] == 3
        assert stats["by_status"]["clicked"] == 1
        assert stats["by_status"]["confirmed"] == 1
        assert stats["by_status"]["dismissed"] == 1
