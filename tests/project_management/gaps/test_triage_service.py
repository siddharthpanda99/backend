"""Tests for Triage & Inbox (Module 14)."""

import pytest
from sqlmodel import Session, create_engine, SQLModel
from common_lib.modules.project_management.triage.service import TriageService
from common_lib.modules.project_management.triage.models import TriageInboxEntry, TriageAction, MyWorkItem


@pytest.fixture
def session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    # Create ALL pm_* tables to satisfy FK references
    pm_tables = [
        t for name, t in SQLModel.metadata.tables.items()
        if name.startswith("pm_")
    ]
    SQLModel.metadata.create_all(engine, tables=pm_tables)
    s = Session(engine)
    yield s
    s.close()


class TestTriageInbox:
    def test_add_to_inbox(self, session):
        svc = TriageService(session)
        result = svc.add_to_inbox(issue_id="issue-1", project_id="proj-1")
        assert result["issue_id"] == "issue-1"
        assert result["is_triaged"] is False

    def test_get_inbox(self, session):
        svc = TriageService(session)
        svc.add_to_inbox("issue-1", "proj-1")
        svc.add_to_inbox("issue-2", "proj-1")
        inbox = svc.get_inbox()
        assert len(inbox) == 2

    def test_mark_triaged(self, session):
        svc = TriageService(session)
        entry = svc.add_to_inbox("issue-1", "proj-1")
        result = svc.mark_triaged(entry["id"], triaged_by="user-1",
                                   updates={"priority_set": True, "assignee_set": True})
        assert result["is_triaged"] is True
        assert result["triaged_by"] == "user-1"

    def test_batch_triage(self, session):
        svc = TriageService(session)
        e1 = svc.add_to_inbox("issue-1", "proj-1")
        e2 = svc.add_to_inbox("issue-2", "proj-1")
        count = svc.batch_triage([e1["id"], e2["id"]], triaged_by="user-1")
        assert count == 2

    def test_mark_needs_info(self, session):
        svc = TriageService(session)
        entry = svc.add_to_inbox("issue-1", "proj-1")
        result = svc.mark_needs_info(entry["id"], requested_by="user-1")
        assert result["needs_more_info"] is True

    def test_snooze_entry(self, session):
        svc = TriageService(session)
        entry = svc.add_to_inbox("issue-1", "proj-1")
        result = svc.snooze_entry(entry["id"], snooze_hours=48)
        assert result["snoozed_until"] is not None


class TestMyWorkInbox:
    def test_add_my_work_item(self, session):
        svc = TriageService(session)
        item = svc.add_my_work_item(user_id="user-1", issue_id="issue-1",
                                    category="assignment")
        assert item["user_id"] == "user-1"
        assert item["category"] == "assignment"

    def test_get_my_work(self, session):
        svc = TriageService(session)
        svc.add_my_work_item("user-1", "issue-1", "assignment")
        svc.add_my_work_item("user-1", "issue-2", "notification")
        work = svc.get_my_work("user-1")
        assert work["total"] == 2

    def test_dismiss_item(self, session):
        svc = TriageService(session)
        item = svc.add_my_work_item("user-1", "issue-1")
        assert svc.dismiss_item(item["id"]) is True

    def test_mark_today_focus(self, session):
        svc = TriageService(session)
        item = svc.add_my_work_item("user-1", "issue-1")
        assert svc.mark_today_focus(item["id"]) is True
        work = svc.get_my_work("user-1")
        assert len(work["today_focus"]) >= 1
