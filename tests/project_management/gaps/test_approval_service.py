"""Tests for Approvals (FC §1.17)."""

import pytest
from sqlmodel import Session, create_engine, SQLModel
from common_lib.modules.project_management.approvals.service import ApprovalService
from common_lib.modules.project_management.approvals.models import (
    ApprovalWorkflow, ApprovalRequest, ApprovalStep, ApprovalHistory,
)


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


class TestApprovalWorkflows:
    def test_create_workflow(self, session):
        svc = ApprovalService(session)
        steps = [{"order": 0, "role_required": "admin"}]
        result = svc.create_workflow("Single Approval", workflow_type="single", steps=steps)
        assert result["name"] == "Single Approval"
        assert result["workflow_type"] == "single"

    def test_list_workflows(self, session):
        svc = ApprovalService(session)
        svc.create_workflow("WF 1")
        svc.create_workflow("WF 2")
        workflows = svc.list_workflows()
        assert len(workflows) >= 2

    def test_get_workflow(self, session):
        svc = ApprovalService(session)
        created = svc.create_workflow("Test WF")
        result = svc.get_workflow(created["id"])
        assert result["name"] == "Test WF"

    def test_delete_workflow(self, session):
        svc = ApprovalService(session)
        created = svc.create_workflow("Delete Me")
        assert svc.delete_workflow(created["id"]) is True
        assert svc.get_workflow(created["id"]) is None


class TestApprovalRequests:
    def test_create_request(self, session):
        svc = ApprovalService(session)
        steps = [{"order": 0, "role_required": "admin"}]
        wf = svc.create_workflow("Test", steps=steps)
        req = svc.create_request(workflow_id=wf["id"], issue_id="issue-1",
                                 requested_by="user-1")
        assert req["issue_id"] == "issue-1"
        assert req["status"] == "pending"
        assert len(req["steps"]) == 1

    def test_approve_step(self, session):
        svc = ApprovalService(session)
        steps = [{"order": 0, "role_required": "admin"}]
        wf = svc.create_workflow("Test", steps=steps)
        req = svc.create_request(wf["id"], "issue-1")
        step_id = req["steps"][0]["id"]
        result = svc.approve_step(step_id, approver_id="admin", comment="Looks good")
        assert result["status"] == "approved"
        assert result["steps"][0]["status"] == "approved"

    def test_reject_step(self, session):
        svc = ApprovalService(session)
        steps = [{"order": 0, "role_required": "admin"}]
        wf = svc.create_workflow("Test", steps=steps)
        req = svc.create_request(wf["id"], "issue-1")
        step_id = req["steps"][0]["id"]
        result = svc.reject_step(step_id, approver_id="admin", comment="Not ready")
        assert result["status"] == "rejected"

    def test_request_changes(self, session):
        svc = ApprovalService(session)
        steps = [{"order": 0, "role_required": "admin"}]
        wf = svc.create_workflow("Test", steps=steps)
        req = svc.create_request(wf["id"], "issue-1")
        step_id = req["steps"][0]["id"]
        result = svc.request_changes(step_id, approver_id="admin", comment="Needs revision")
        assert result["status"] == "changes_requested"

    def test_get_history(self, session):
        svc = ApprovalService(session)
        steps = [{"order": 0, "role_required": "admin"}]
        wf = svc.create_workflow("Test", steps=steps)
        req = svc.create_request(wf["id"], "issue-1")
        step_id = req["steps"][0]["id"]
        svc.approve_step(step_id, "admin")
        history = svc.get_history(req["id"])
        assert len(history) == 2  # created + approved

    def test_sequential_approval(self, session):
        svc = ApprovalService(session)
        steps = [
            {"order": 0, "role_required": "manager"},
            {"order": 1, "role_required": "director"},
        ]
        wf = svc.create_workflow("Sequential", workflow_type="sequential", steps=steps)
        req = svc.create_request(wf["id"], "issue-1")
        # Approve first step
        result = svc.approve_step(req["steps"][0]["id"], approver_id="manager")
        assert result["steps"][0]["status"] == "approved"
        # Approve second step
        result = svc.approve_step(req["steps"][1]["id"], approver_id="director")
        assert result["status"] == "approved"
