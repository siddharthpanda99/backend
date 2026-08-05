"""Project Management Node Wrapper Test Fixtures.

Uses mocked services to avoid cross-module DB import issues.
Tests call @node wrapper functions directly with mocked sessions/services.
"""

import os
import sys
import uuid
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

# Bootstrap paths
BACKEND_ROOT = Path(__file__).parent.parent.parent.resolve()
PROJECT_ROOT = BACKEND_ROOT.parent
COMMON_LIB_SRC = str(PROJECT_ROOT / "Python Libs" / "common_lib" / "src")
if COMMON_LIB_SRC not in sys.path:
    sys.path.insert(0, COMMON_LIB_SRC)
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


# ---------------------------------------------------------------------------
# Mock DB session factory (no real DB needed)
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_session():
    """Create a mock DB session that supports context manager protocol."""
    session = MagicMock()
    session.__enter__ = MagicMock(return_value=session)
    session.__exit__ = MagicMock(return_value=False)
    session.close = MagicMock()
    session.commit = MagicMock()
    session.refresh = MagicMock()
    session.add = MagicMock()
    session.flush = MagicMock()
    return session


# ---------------------------------------------------------------------------
# Mock _get_session — patch at the module level
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def patch_get_session(mock_session):
    """Patch _get_session in all submodule nodes.py so all @node wrappers use our mock DB."""
    targets = [
        "common_lib.modules.project_management.nodes._get_session",
        "common_lib.modules.project_management.nodes.ai_nodes._get_session",
        "common_lib.modules.project_management.nodes.backlog_nodes._get_session",
        "common_lib.modules.project_management.agile.nodes._get_session",
        "common_lib.modules.project_management.attachments.nodes._get_session",
        "common_lib.modules.project_management.custom_data.nodes._get_session",
        "common_lib.modules.project_management.dashboard.nodes._get_session",
        "common_lib.modules.project_management.discovery.nodes._get_session",
        "common_lib.modules.project_management.finance.nodes._get_session",
        "common_lib.modules.project_management.forms.nodes._get_session",
        "common_lib.modules.project_management.goals.nodes._get_session",
        "common_lib.modules.project_management.issues.nodes._get_session",
        "common_lib.modules.project_management.organization.nodes._get_session",
        "common_lib.modules.project_management.planning.nodes._get_session",
        "common_lib.modules.project_management.portfolio.nodes._get_session",
        "common_lib.modules.project_management.programs.nodes._get_session",
        "common_lib.modules.project_management.projects.nodes._get_session",
        "common_lib.modules.project_management.releases.nodes._get_session",
        "common_lib.modules.project_management.resources.nodes._get_session",
        "common_lib.modules.project_management.risk.nodes._get_session",
        "common_lib.modules.project_management.subtasks.nodes._get_session",
        "common_lib.modules.project_management.views.nodes._get_session",
        "common_lib.modules.project_management.workflows.nodes._get_session",
        "common_lib.modules.project_management.collaboration.nodes._get_session",
        "common_lib.modules.project_management.import_export.nodes._get_session",
        "common_lib.modules.project_management.pmo.nodes._get_session",
        "common_lib.modules.project_management.search.nodes._get_session",
        "common_lib.modules.project_management.verticals.nodes._get_session",
        "common_lib.modules.project_management.sla.nodes._get_session",
        "common_lib.modules.project_management.triage.nodes._get_session",
        "common_lib.modules.project_management.dependency_graph.nodes._get_session",
        "common_lib.modules.project_management.approvals.nodes._get_session",
        "common_lib.modules.project_management.prioritization.nodes._get_session",
    ]
    patchers = [patch(t, return_value=mock_session) for t in targets]
    for p in patchers:
        p.start()
    yield mock_session
    for p in reversed(patchers):
        p.stop()


# ---------------------------------------------------------------------------
# Mock AI service (LLM calls)
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_ai_service():
    """Mock PMAIService so AI tests don't call a real LLM."""
    svc = MagicMock()
    svc.categorize_issue = MagicMock(return_value={
        "issue_type": "Bug",
        "priority": "high",
        "labels": ["backend", "critical"],
        "components": ["api"],
        "confidence": 0.85,
        "reasoning": "Title mentions crash and error",
    })
    svc.suggest_assignee = MagicMock(return_value={
        "recommended_assignee": "user-123",
        "confidence": 0.9,
        "reasoning": "User has backend expertise",
        "alternatives": [{"user_id": "user-456", "fit_score": 0.7}],
        "workload_balance": "balanced",
    })
    svc.summarize_issue = MagicMock(return_value={
        "summary": "Login page crashes on submit.",
        "key_points": ["Authentication broken", "Affects all users"],
        "action_items": ["Fix auth flow", "Add error handling"],
        "sentiment": "negative",
        "urgency": "high",
    })
    svc.summarize_sprint = MagicMock(return_value={
        "summary": "Sprint completed 80% of points.",
        "key_points": ["16 points completed"],
        "action_items": ["Carry over 4 points"],
        "sentiment": "positive",
        "urgency": "medium",
    })
    svc.predict_complexity = MagicMock(return_value={
        "estimated_points": 5,
        "estimated_hours": 10.0,
        "confidence": 0.7,
        "complexity_factors": ["Multiple integrations"],
        "risks": ["Third-party API dependency"],
        "breakdown": [{"task": "Implement API", "estimated_hours": 6.0}],
    })
    svc.analyze_velocity = MagicMock(return_value={
        "average_velocity": 24.0,
        "velocity_trend": "stable",
        "predicted_velocity": 25.0,
        "confidence": 0.6,
        "factors": ["Consistent team size"],
        "recommendations": ["Consider adding capacity"],
        "burndown_forecast": [],
        "risks": [],
    })
    svc.semantic_search = MagicMock(return_value={
        "intent": "Find high-priority bugs",
        "keywords": ["high", "priority", "bugs"],
        "filters": {"priority": "high", "issue_type": "Bug"},
        "sort_by": "priority",
        "sort_order": "desc",
        "confidence": 0.8,
    })
    svc.assistant_chat = MagicMock(return_value={
        "response": "I can help you with that!",
        "suggestions": ["Create an issue", "View backlog"],
        "actions": [],
    })
    # Patch the AI service factory functions at their import site (ai_nodes.py).
    # ai_nodes.py does ``from nodes import get_issue_ai_service`` which creates
    # local references, so we patch ``nodes.ai_nodes.get_issue_ai_service``
    # rather than ``nodes.get_issue_ai_service``.
    patchers = [
        patch("common_lib.modules.project_management.nodes.ai_nodes.get_issue_ai_service", return_value=svc),
        patch("common_lib.modules.project_management.nodes.ai_nodes.get_sprint_ai_service", return_value=svc),
        patch("common_lib.modules.project_management.nodes.ai_nodes.get_planning_ai_service", return_value=svc),
        patch("common_lib.modules.project_management.nodes.ai_nodes.get_risk_ai_service", return_value=svc),
    ]
    for p in patchers:
        p.start()
    yield svc
    for p in reversed(patchers):
        p.stop()


# ---------------------------------------------------------------------------
# Mock service factories (no real DB needed)
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_project_service():
    """Mock ProjectService with all methods stubbed."""
    svc = MagicMock()
    svc.list_projects = MagicMock(return_value=[
        MagicMock(id="proj-1", name="Test Project", identifier="TST",
                  model_dump=MagicMock(return_value={"id": "proj-1", "name": "Test Project", "identifier": "TST"}))
    ])
    svc.create_project = MagicMock(return_value=MagicMock(
        id="proj-new", name="New Project", identifier="NP",
    ))
    svc.get_project = MagicMock(return_value=None)
    return svc


@pytest.fixture()
def mock_issue_service():
    """Mock IssueService with all methods stubbed."""
    svc = MagicMock()
    svc.list_issues = MagicMock(return_value={"items": [], "total": 0, "has_more": False})
    svc.create_issue = MagicMock(return_value=MagicMock(
        id="issue-1", key="TST-1", title="Test Issue", status_id="status-1",
    ))
    svc.update_issue = MagicMock(return_value=MagicMock(
        id="issue-1", key="TST-1", title="Updated Title",
    ))
    svc.transition_issue = MagicMock(return_value=MagicMock(
        id="issue-1", key="TST-1", status_id="status-2",
    ))
    svc.delete_issue = MagicMock(return_value=True)
    svc.add_comment = MagicMock(return_value=MagicMock(
        id="comment-1", issue_id="issue-1", body="Test comment", author_id="user-1",
    ))
    svc.list_comments = MagicMock(return_value=[])
    svc.get_available_transitions = MagicMock(return_value=[
        {"transition_id": "t-1", "name": "Move to In Progress", "to_status_id": "status-2"}
    ])
    svc.link_issues = MagicMock(return_value=MagicMock(
        id="link-1", source_issue_id="issue-1", target_issue_id="issue-2", link_type="blocks",
    ))
    svc.bulk_update = MagicMock(return_value=1)
    return svc


@pytest.fixture()
def mock_sprint_service():
    """Mock SprintService with all methods stubbed."""
    svc = MagicMock()
    svc.list_sprints = MagicMock(return_value=[
        MagicMock(id="sprint-1", name="Sprint 1",
                  model_dump=MagicMock(return_value={"id": "sprint-1", "name": "Sprint 1", "status": "planned"}))
    ])
    svc.start_sprint = MagicMock(return_value=MagicMock(
        id="sprint-1", name="Sprint 1", status="active",
    ))
    svc.complete_sprint = MagicMock(return_value=MagicMock(
        id="sprint-1", name="Sprint 1", status="complete", completed_points=16,
    ))
    svc.get_sprint_metrics = MagicMock(return_value={
        "sprint_id": "sprint-1", "name": "Sprint 1",
        "committed_points": 20, "total_points": 20, "completed_points": 16, "issue_count": 5,
    })
    return svc


@pytest.fixture()
def mock_workflow_service():
    """Mock WorkflowService with all methods stubbed."""
    svc = MagicMock()
    workflow_mock = MagicMock(id="wf-1", name="Default Workflow")
    svc.get_workflow_for_project = MagicMock(return_value=workflow_mock)
    svc.list_statuses = MagicMock(return_value=[
        MagicMock(id="s-1", name="To Do", model_dump=MagicMock(return_value={"id": "s-1", "name": "To Do", "category": "todo"})),
        MagicMock(id="s-2", name="In Progress", model_dump=MagicMock(return_value={"id": "s-2", "name": "In Progress", "category": "in_progress"})),
        MagicMock(id="s-3", name="Done", model_dump=MagicMock(return_value={"id": "s-3", "name": "Done", "category": "done"})),
    ])
    svc.list_transitions = MagicMock(return_value=[
        MagicMock(id="t-1", model_dump=MagicMock(return_value={"id": "t-1", "name": "Start"})),
    ])
    return svc
