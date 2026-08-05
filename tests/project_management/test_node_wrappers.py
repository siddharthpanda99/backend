"""
Comprehensive tests for all @node wrappers in project_management/nodes.py.

Uses mocked services to avoid cross-module DB import issues.
CRUD wrappers patch at the actual import source (service.py module).
AI wrappers patch ProjectManagementAIService directly.
"""

import pytest
from unittest.mock import patch, MagicMock


# ===========================================================================
# AI-Powered @node Wrappers (9 tests)
# ===========================================================================

class TestCategorizeIssue:
    def test_categorize_returns_result(self, mock_ai_service):
        from common_lib.modules.project_management.nodes import categorize_issue
        result = categorize_issue(title="Login page crashes on submit", description="When users try to login")
        assert "issue_type" in result
        assert result["issue_type"] == "Bug"
        assert result["priority"] == "high"
        mock_ai_service.categorize_issue.assert_called_once()

    def test_categorize_error_returns_error_dict(self, mock_ai_service):
        from common_lib.modules.project_management.nodes import categorize_issue
        mock_ai_service.categorize_issue.side_effect = RuntimeError("LLM timeout")
        result = categorize_issue(title="Test")
        assert "error" in result
        assert "LLM timeout" in result["error"]


class TestSuggestAssignee:
    def test_suggest_assignee_returns_result(self, mock_ai_service):
        from common_lib.modules.project_management.nodes import suggest_assignee
        result = suggest_assignee(title="Fix login bug", team_members=[{"id": "user-123"}])
        assert result["recommended_assignee"] == "user-123"
        mock_ai_service.suggest_assignee.assert_called_once()

    def test_suggest_assignee_error(self, mock_ai_service):
        from common_lib.modules.project_management.nodes import suggest_assignee
        mock_ai_service.suggest_assignee.side_effect = ValueError("No team members")
        result = suggest_assignee(title="Test")
        assert "error" in result


class TestSummarizeIssue:
    def test_summarize_issue_returns_result(self, mock_ai_service):
        from common_lib.modules.project_management.nodes import summarize_issue
        result = summarize_issue(title="Login broken", status="In Progress", priority="high")
        assert "summary" in result
        assert "key_points" in result
        mock_ai_service.summarize_issue.assert_called_once()

    def test_summarize_issue_error(self, mock_ai_service):
        from common_lib.modules.project_management.nodes import summarize_issue
        mock_ai_service.summarize_issue.side_effect = Exception("Service unavailable")
        result = summarize_issue(title="Test")
        assert "error" in result


class TestSummarizeSprint:
    def test_summarize_sprint_returns_result(self, mock_ai_service):
        from common_lib.modules.project_management.nodes import summarize_sprint
        result = summarize_sprint(sprint_name="Sprint 1", committed_points=20, completed_points=16)
        assert "summary" in result
        assert "action_items" in result
        mock_ai_service.summarize_sprint.assert_called_once()

    def test_summarize_sprint_error(self, mock_ai_service):
        from common_lib.modules.project_management.nodes import summarize_sprint
        mock_ai_service.summarize_sprint.side_effect = RuntimeError("DB error")
        result = summarize_sprint(sprint_name="Test")
        assert "error" in result


class TestPredictComplexity:
    def test_predict_complexity_returns_result(self, mock_ai_service):
        from common_lib.modules.project_management.nodes import predict_complexity
        result = predict_complexity(title="Implement payment integration")
        assert "estimated_points" in result
        assert "estimated_hours" in result
        assert "risks" in result
        mock_ai_service.predict_complexity.assert_called_once()

    def test_predict_complexity_error(self, mock_ai_service):
        from common_lib.modules.project_management.nodes import predict_complexity
        mock_ai_service.predict_complexity.side_effect = Exception("Model not available")
        result = predict_complexity(title="Test")
        assert "error" in result


class TestVelocityAnalysis:
    def test_velocity_analysis_returns_result(self, mock_ai_service):
        from common_lib.modules.project_management.nodes import velocity_analysis
        result = velocity_analysis(project_name="Test", sprint_history=[{"name": "S1", "completed_points": 20}])
        assert "average_velocity" in result
        assert "velocity_trend" in result
        mock_ai_service.analyze_velocity.assert_called_once()

    def test_velocity_analysis_error(self, mock_ai_service):
        from common_lib.modules.project_management.nodes import velocity_analysis
        mock_ai_service.analyze_velocity.side_effect = Exception("Insufficient data")
        result = velocity_analysis()
        assert "error" in result


class TestSemanticSearch:
    def test_semantic_search_returns_result(self, mock_ai_service):
        from common_lib.modules.project_management.nodes import semantic_search
        result = semantic_search(query="high priority bugs")
        assert "intent" in result
        assert "filters" in result
        assert "confidence" in result
        mock_ai_service.semantic_search.assert_called_once()

    def test_semantic_search_error(self, mock_ai_service):
        from common_lib.modules.project_management.nodes import semantic_search
        mock_ai_service.semantic_search.side_effect = Exception("Search failed")
        result = semantic_search(query="test")
        assert "error" in result


class TestAiAssistant:
    def test_assistant_returns_response(self, mock_ai_service):
        from common_lib.modules.project_management.nodes import ai_assistant
        result = ai_assistant(message="Help me create an issue")
        assert "response" in result
        assert "suggestions" in result
        mock_ai_service.assistant_chat.assert_called_once()

    def test_assistant_with_context(self, mock_ai_service):
        from common_lib.modules.project_management.nodes import ai_assistant
        context = {"current_issue": {"key": "TST-1"}}
        result = ai_assistant(message="Summarize this", context=context)
        assert "response" in result
        mock_ai_service.assistant_chat.assert_called_with(message="Summarize this", context=context)

    def test_assistant_error_returns_fallback(self, mock_ai_service):
        from common_lib.modules.project_management.nodes import ai_assistant
        mock_ai_service.assistant_chat.side_effect = Exception("LLM down")
        result = ai_assistant(message="Help")
        assert "response" in result
        assert "error" in result["response"].lower()


# ===========================================================================
# CRUD @node Wrappers — Projects (2 tests)
# ===========================================================================

class TestListProjects:
    def test_list_projects_returns_result(self):
        mock_svc = MagicMock()
        mock_svc.list_projects = MagicMock(return_value=[
            MagicMock(id="proj-1", name="Test Project", model_dump=MagicMock(return_value={"id": "proj-1", "name": "Test Project"}))
        ])
        with patch("common_lib.modules.project_management.service.ProjectService", return_value=mock_svc):
            from common_lib.modules.project_management.nodes import list_projects
            result = list_projects()
            assert "projects" in result
            assert "total" in result
            assert result["total"] >= 1

    def test_list_projects_error(self):
        mock_svc = MagicMock()
        mock_svc.list_projects.side_effect = Exception("DB error")
        with patch("common_lib.modules.project_management.service.ProjectService", return_value=mock_svc):
            from common_lib.modules.project_management.nodes import list_projects
            result = list_projects()
            assert "error" in result


class TestCreateProject:
    def test_create_project_success(self):
        mock_project = MagicMock()
        mock_project.id = "proj-new"
        mock_project.name = "New Project"
        mock_project.identifier = "NP"
        mock_svc = MagicMock()
        mock_svc.create_project = MagicMock(return_value=mock_project)
        with patch("common_lib.modules.project_management.service.ProjectService", return_value=mock_svc):
            from common_lib.modules.project_management.nodes import create_project
            result = create_project(name="New Project", identifier="NP", description="A test project")
            assert "id" in result
            assert result["name"] == "New Project"

    def test_create_project_error(self):
        mock_svc = MagicMock()
        mock_svc.create_project.side_effect = Exception("Duplicate identifier")
        with patch("common_lib.modules.project_management.service.ProjectService", return_value=mock_svc):
            from common_lib.modules.project_management.nodes import create_project
            result = create_project(name="P1", identifier="DUP")
            assert "error" in result


# ===========================================================================
# CRUD @node Wrappers — Issues (6 tests)
# ===========================================================================

class TestListIssues:
    def test_list_issues_returns_result(self):
        mock_svc = MagicMock()
        mock_svc.list_issues = MagicMock(return_value={"items": [], "total": 0, "has_more": False})
        with patch("common_lib.modules.project_management.service.IssueService", return_value=mock_svc):
            from common_lib.modules.project_management.nodes import list_issues
            result = list_issues(project_id="proj-1")
            assert "items" in result
            assert "total" in result

    def test_list_issues_error(self):
        mock_svc = MagicMock()
        mock_svc.list_issues.side_effect = Exception("DB error")
        with patch("common_lib.modules.project_management.service.IssueService", return_value=mock_svc):
            from common_lib.modules.project_management.nodes import list_issues
            result = list_issues(project_id="proj-1")
            assert "error" in result


class TestCreateIssue:
    def test_create_issue_success(self):
        mock_svc = MagicMock()
        mock_svc.create_issue = MagicMock(return_value=MagicMock(id="issue-1", key="TST-1", title="New Bug", status_id="status-1"))
        with patch("common_lib.modules.project_management.service.IssueService", return_value=mock_svc):
            from common_lib.modules.project_management.nodes import create_issue
            result = create_issue(project_id="proj-1", title="New Bug", priority="high")
            assert "id" in result
            assert result["title"] == "New Bug"
            assert "key" in result

    def test_create_issue_error(self):
        mock_svc = MagicMock()
        mock_svc.create_issue.side_effect = Exception("Invalid project")
        with patch("common_lib.modules.project_management.service.IssueService", return_value=mock_svc):
            from common_lib.modules.project_management.nodes import create_issue
            result = create_issue(project_id="invalid", title="Test")
            assert "error" in result


class TestUpdateIssue:
    def test_update_issue_title(self):
        mock_svc = MagicMock()
        mock_svc.update_issue = MagicMock(return_value=MagicMock(id="issue-1", key="TST-1", title="Updated Title"))
        with patch("common_lib.modules.project_management.service.IssueService", return_value=mock_svc):
            from common_lib.modules.project_management.nodes import update_issue
            result = update_issue(issue_id="issue-1", title="Updated Title")
            assert result["title"] == "Updated Title"
            assert result["key"] == "TST-1"

    def test_update_nonexistent_issue(self):
        mock_svc = MagicMock()
        mock_svc.update_issue.return_value = None
        with patch("common_lib.modules.project_management.service.IssueService", return_value=mock_svc):
            from common_lib.modules.project_management.nodes import update_issue
            result = update_issue(issue_id="nonexistent-id", title="Test")
            assert "error" in result


class TestTransitionIssue:
    def test_transition_issue(self):
        mock_svc = MagicMock()
        mock_svc.transition_issue = MagicMock(return_value=MagicMock(id="issue-1", key="TST-1", status_id="status-2"))
        with patch("common_lib.modules.project_management.service.IssueService", return_value=mock_svc):
            from common_lib.modules.project_management.nodes import transition_issue
            result = transition_issue(issue_id="issue-1", status_id="status-2", comment="Starting work")
            assert result["status_id"] == "status-2"

    def test_transition_nonexistent_issue(self):
        mock_svc = MagicMock()
        mock_svc.transition_issue.return_value = None
        with patch("common_lib.modules.project_management.service.IssueService", return_value=mock_svc):
            from common_lib.modules.project_management.nodes import transition_issue
            result = transition_issue(issue_id="nonexistent", status_id="status-1")
            assert "error" in result


# ===========================================================================
# CRUD @node Wrappers — Sprints (4 tests)
# ===========================================================================

class TestListSprints:
    def test_list_sprints_returns_result(self):
        mock_svc = MagicMock()
        mock_svc.list_sprints = MagicMock(return_value=[
            MagicMock(id="sprint-1", name="Sprint 1", model_dump=MagicMock(return_value={"id": "sprint-1", "name": "Sprint 1"}))
        ])
        with patch("common_lib.modules.project_management.service.SprintService", return_value=mock_svc):
            from common_lib.modules.project_management.nodes import list_sprints
            result = list_sprints(project_id="proj-1")
            assert "sprints" in result
            assert result["total"] >= 1

    def test_list_sprints_error(self):
        mock_svc = MagicMock()
        mock_svc.list_sprints.side_effect = Exception("DB error")
        with patch("common_lib.modules.project_management.service.SprintService", return_value=mock_svc):
            from common_lib.modules.project_management.nodes import list_sprints
            result = list_sprints(project_id="proj-1")
            assert "error" in result


class TestStartSprint:
    def test_start_sprint(self):
        mock_svc = MagicMock()
        mock_svc.start_sprint = MagicMock(return_value=MagicMock(id="sprint-1", name="Sprint 1", status="active"))
        with patch("common_lib.modules.project_management.service.SprintService", return_value=mock_svc):
            from common_lib.modules.project_management.nodes import start_sprint
            result = start_sprint(sprint_id="sprint-1")
            assert result["status"] == "active"

    def test_start_nonexistent_sprint(self):
        mock_svc = MagicMock()
        mock_svc.start_sprint.return_value = None
        with patch("common_lib.modules.project_management.service.SprintService", return_value=mock_svc):
            from common_lib.modules.project_management.nodes import start_sprint
            result = start_sprint(sprint_id="nonexistent")
            assert "error" in result


class TestCompleteSprint:
    def test_complete_sprint(self):
        mock_svc = MagicMock()
        mock_svc.complete_sprint = MagicMock(return_value=MagicMock(id="sprint-1", name="Sprint 1", status="complete", completed_points=16))
        with patch("common_lib.modules.project_management.service.SprintService", return_value=mock_svc):
            from common_lib.modules.project_management.nodes import complete_sprint
            result = complete_sprint(sprint_id="sprint-1")
            assert result["status"] == "complete"
            assert result["completed_points"] == 16

    def test_complete_nonexistent_sprint(self):
        mock_svc = MagicMock()
        mock_svc.complete_sprint.return_value = None
        with patch("common_lib.modules.project_management.service.SprintService", return_value=mock_svc):
            from common_lib.modules.project_management.nodes import complete_sprint
            result = complete_sprint(sprint_id="nonexistent")
            assert "error" in result


class TestGetSprintMetrics:
    def test_get_sprint_metrics(self):
        mock_svc = MagicMock()
        mock_svc.get_sprint_metrics = MagicMock(return_value={"committed_points": 20, "completed_points": 16})
        with patch("common_lib.modules.project_management.service.SprintService", return_value=mock_svc):
            from common_lib.modules.project_management.nodes import get_sprint_metrics
            result = get_sprint_metrics(sprint_id="sprint-1")
            assert "committed_points" in result
            assert "completed_points" in result

    def test_get_sprint_metrics_error(self):
        mock_svc = MagicMock()
        mock_svc.get_sprint_metrics.side_effect = Exception("Not found")
        with patch("common_lib.modules.project_management.service.SprintService", return_value=mock_svc):
            from common_lib.modules.project_management.nodes import get_sprint_metrics
            result = get_sprint_metrics(sprint_id="nonexistent")
            assert "error" in result


# ===========================================================================
# CRUD @node Wrappers — Workflow (2 tests)
# ===========================================================================

class TestGetWorkflow:
    def test_get_workflow(self):
        mock_svc = MagicMock()
        mock_svc.get_workflow_for_project = MagicMock(return_value=MagicMock(id="wf-1", name="Default Workflow"))
        mock_svc.list_statuses = MagicMock(return_value=[
            MagicMock(id="s-1", name="To Do", model_dump=MagicMock(return_value={"id": "s-1", "name": "To Do"})),
            MagicMock(id="s-2", name="Done", model_dump=MagicMock(return_value={"id": "s-2", "name": "Done"})),
        ])
        mock_svc.list_transitions = MagicMock(return_value=[
            MagicMock(id="t-1", model_dump=MagicMock(return_value={"id": "t-1", "name": "Start"})),
        ])
        with patch("common_lib.modules.project_management.service.WorkflowService", return_value=mock_svc):
            from common_lib.modules.project_management.nodes import get_workflow
            result = get_workflow(project_id="proj-1")
            assert "workflow_id" in result
            assert "statuses" in result
            assert len(result["statuses"]) == 2

    def test_get_workflow_nonexistent_project(self):
        mock_svc = MagicMock()
        mock_svc.get_workflow_for_project.return_value = None
        with patch("common_lib.modules.project_management.service.WorkflowService", return_value=mock_svc):
            from common_lib.modules.project_management.nodes import get_workflow
            result = get_workflow(project_id="nonexistent")
            assert "error" in result


class TestGetAvailableTransitions:
    def test_get_transitions(self):
        mock_svc = MagicMock()
        mock_svc.get_available_transitions = MagicMock(return_value=[
            {"id": "t-1", "name": "Move to In Progress", "to_status_id": "s-2"}
        ])
        with patch("common_lib.modules.project_management.service.IssueService", return_value=mock_svc):
            from common_lib.modules.project_management.nodes import get_available_transitions
            result = get_available_transitions(issue_id="issue-1")
            assert "transitions" in result
            assert len(result["transitions"]) >= 1

    def test_get_transitions_error(self):
        mock_svc = MagicMock()
        mock_svc.get_available_transitions.side_effect = Exception("Not found")
        with patch("common_lib.modules.project_management.service.IssueService", return_value=mock_svc):
            from common_lib.modules.project_management.nodes import get_available_transitions
            result = get_available_transitions(issue_id="nonexistent")
            assert "error" in result


# ===========================================================================
# CRUD @node Wrappers — Additional Issue Operations (3 tests)
# ===========================================================================

class TestDeleteIssue:
    def test_delete_issue(self):
        mock_svc = MagicMock()
        mock_svc.delete_issue = MagicMock(return_value=True)
        with patch("common_lib.modules.project_management.service.IssueService", return_value=mock_svc):
            from common_lib.modules.project_management.nodes import delete_issue
            result = delete_issue(issue_id="issue-1")
            assert result["success"] is True
            assert result["issue_id"] == "issue-1"

    def test_delete_nonexistent_issue(self):
        mock_svc = MagicMock()
        mock_svc.delete_issue.side_effect = Exception("Issue not found")
        with patch("common_lib.modules.project_management.service.IssueService", return_value=mock_svc):
            from common_lib.modules.project_management.nodes import delete_issue
            result = delete_issue(issue_id="nonexistent")
            assert "error" in result


class TestAddComment:
    def test_add_comment(self):
        mock_svc = MagicMock()
        mock_svc.add_comment = MagicMock(return_value=MagicMock(id="comment-1", issue_id="issue-1", body="Test comment", author_id="user-1"))
        with patch("common_lib.modules.project_management.service.IssueService", return_value=mock_svc):
            from common_lib.modules.project_management.nodes import add_comment
            result = add_comment(issue_id="issue-1", body="Test comment")
            assert "id" in result
            assert result["body"] == "Test comment"

    def test_add_comment_error(self):
        mock_svc = MagicMock()
        mock_svc.add_comment.side_effect = Exception("Issue not found")
        with patch("common_lib.modules.project_management.service.IssueService", return_value=mock_svc):
            from common_lib.modules.project_management.nodes import add_comment
            result = add_comment(issue_id="nonexistent", body="Test")
            assert "error" in result


class TestListComments:
    def test_list_comments_empty(self):
        mock_svc = MagicMock()
        mock_svc.list_comments = MagicMock(return_value=[])
        with patch("common_lib.modules.project_management.service.IssueService", return_value=mock_svc):
            from common_lib.modules.project_management.nodes import list_comments
            result = list_comments(issue_id="issue-1")
            assert "comments" in result
            assert result["page_count"] == 0

    def test_list_comments_error(self):
        mock_svc = MagicMock()
        mock_svc.list_comments.side_effect = Exception("Issue not found")
        with patch("common_lib.modules.project_management.service.IssueService", return_value=mock_svc):
            from common_lib.modules.project_management.nodes import list_comments
            result = list_comments(issue_id="nonexistent")
            assert "error" in result


# ===========================================================================
# CRUD @node Wrappers — Bulk Operations (1 test)
# ===========================================================================

class TestBulkUpdateIssues:
    def test_bulk_update_priority(self):
        mock_svc = MagicMock()
        mock_svc.bulk_update = MagicMock(return_value=2)
        with patch("common_lib.modules.project_management.service.IssueService", return_value=mock_svc):
            from common_lib.modules.project_management.nodes import bulk_update_issues
            result = bulk_update_issues(issue_ids=["issue-1", "issue-2"], priority="urgent")
            assert "updated_count" in result
            assert result["updated_count"] >= 1

    def test_bulk_update_error(self):
        mock_svc = MagicMock()
        mock_svc.bulk_update.side_effect = Exception("DB error")
        with patch("common_lib.modules.project_management.service.IssueService", return_value=mock_svc):
            from common_lib.modules.project_management.nodes import bulk_update_issues
            result = bulk_update_issues(issue_ids=["issue-1"], priority="high")
            assert "error" in result


# ===========================================================================
# Link Issues @node Wrapper (1 test)
# ===========================================================================

class TestLinkIssues:
    def test_link_issues(self):
        mock_svc = MagicMock()
        mock_svc.link_issues = MagicMock(return_value=MagicMock(id="link-1", source_issue_id="issue-1", target_issue_id="issue-2", link_type="blocks"))
        with patch("common_lib.modules.project_management.service.IssueService", return_value=mock_svc):
            from common_lib.modules.project_management.nodes import link_issues
            result = link_issues(source_issue_id="issue-1", target_issue_id="issue-2", link_type="blocks")
            assert "link_id" in result
            assert result["link_type"] == "blocks"

    def test_link_issues_error(self):
        mock_svc = MagicMock()
        mock_svc.link_issues.side_effect = Exception("Duplicate link")
        with patch("common_lib.modules.project_management.service.IssueService", return_value=mock_svc):
            from common_lib.modules.project_management.nodes import link_issues
            result = link_issues(source_issue_id="issue-1", target_issue_id="issue-2", link_type="blocks")
            assert "error" in result
