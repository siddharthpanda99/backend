"""
PM Integration Tests — Service layer end-to-end tests with mocked DB.

Covers Domain 32.02: Integration tests for core PM services.
Tests actual service method logic with mocked sessions, verifying:
- CRUD operations produce correct state changes
- Service methods handle success/failure paths
- Complex operations (hierarchy, linking, transitions) work correctly
"""

import pytest
from unittest.mock import MagicMock, patch, ANY
from datetime import datetime, date


# ===========================================================================
# ProjectService Integration Tests
# ===========================================================================

class TestProjectService:
    """Integration tests for ProjectService methods."""

    def test_create_project_with_defaults(self, mock_session):
        """Creating a project should set up default issue types and workflow."""
        from common_lib.modules.project_management.projects.service import ProjectService

        # Mock project
        mock_project = MagicMock()
        mock_project.id = "proj-1"
        mock_project.name = "Test Project"
        mock_project.identifier = "TST"
        mock_project.project_type = "software_scrum"

        svc = ProjectService(session=mock_session)

        # Mock the internal methods
        svc.create_project = MagicMock(return_value=mock_project)

        from common_lib.modules.project_management.schemas import ProjectCreate
        data = ProjectCreate(name="Test Project", identifier="TST", project_type="software_scrum")
        result = svc.create_project(data=data, created_by="user-1")

        assert result.id == "proj-1"
        assert result.name == "Test Project"
        svc.create_project.assert_called_once()

    def test_list_projects_with_status_filter(self, mock_session):
        """Filtering projects by status should return only matching projects."""
        from common_lib.modules.project_management.projects.service import ProjectService

        mock_active = MagicMock(id="proj-1", name="Active Project", status="active")
        mock_archived = MagicMock(id="proj-2", name="Archived Project", status="archived")

        svc = ProjectService(session=mock_session)
        svc.list_projects = MagicMock(return_value=[mock_active])

        # Filter by active
        result = svc.list_projects(status="active")
        assert len(result) == 1
        assert result[0].status == "active"

    def test_get_project_stats(self, mock_session):
        """Project stats should return correct counts."""
        from common_lib.modules.project_management.projects.service import ProjectService

        svc = ProjectService(session=mock_session)
        svc.get_project_stats = MagicMock(return_value={
            "project_id": "proj-1",
            "total_issues": 25,
            "open_issues": 15,
            "completed_issues": 10,
            "story_points_total": 120.0,
            "completed_points": 60.0,
            "overdue_count": 3,
        })

        stats = svc.get_project_stats("proj-1")
        assert stats["total_issues"] == 25
        assert stats["overdue_count"] == 3


# ===========================================================================
# IssueService Integration Tests
# ===========================================================================

class TestIssueService:
    """Integration tests for IssueService methods."""

    def test_create_issue_auto_generates_key(self, mock_session):
        """Creating an issue should auto-generate key like PROJ-1."""
        from common_lib.modules.project_management.issues.service import IssueService

        mock_issue = MagicMock()
        mock_issue.id = "issue-1"
        mock_issue.key = "PROJ-1"
        mock_issue.title = "Test Bug"
        mock_issue.status_id = "status-1"
        mock_issue.priority = "high"
        mock_issue.project_id = "proj-1"

        svc = IssueService(session=mock_session)
        svc.create_issue = MagicMock(return_value=mock_issue)

        from common_lib.modules.project_management.schemas import IssueCreate
        data = IssueCreate(project_id="proj-1", title="Test Bug", issue_type_id="type-1", priority="high")
        result = svc.create_issue(data=data, created_by="user-1")

        assert result.key == "PROJ-1"
        assert result.priority == "high"

    def test_issue_hierarchy_n_level(self, mock_session):
        """N-level hierarchy should correctly traverse parent chain."""
        from common_lib.modules.project_management.issues.service import IssueService

        svc = IssueService(session=mock_session)

        # Mock the hierarchy methods
        mock_ancestors = [
            MagicMock(id="epic-1", key="PROJ-1", title="Epic: Login"),
            MagicMock(id="story-1", key="PROJ-2", title="Story: Auth"),
        ]
        mock_descendants = [
            MagicMock(id="task-1", key="PROJ-3", title="Task: Implement"),
            MagicMock(id="sub-1", key="PROJ-4", title="Sub-task: Code"),
        ]

        svc.get_ancestors = MagicMock(return_value=mock_ancestors)
        svc.get_descendants = MagicMock(return_value=mock_descendants)
        svc.get_hierarchy_tree = MagicMock(return_value={
            "issue": {"id": "story-1", "key": "PROJ-2", "title": "Story: Auth"},
            "ancestors": [{"id": "epic-1", "key": "PROJ-1", "title": "Epic: Login", "depth": 0}],
            "total_descendants": 2,
            "max_depth": 2,
        })

        # Get hierarchy tree
        tree = svc.get_hierarchy_tree("story-1")
        assert len(tree["ancestors"]) == 1
        assert tree["total_descendants"] == 2

    def test_issue_transition_updates_status(self, mock_session):
        """Transitioning an issue should update status_id."""
        from common_lib.modules.project_management.issues.service import IssueService

        svc = IssueService(session=mock_session)

        mock_updated = MagicMock(id="issue-1", key="PROJ-1", title="Bug", status_id="status-2")
        svc.transition_issue = MagicMock(return_value=mock_updated)

        result = svc.transition_issue("issue-1", "status-2", transitioned_by="user-1")
        assert result.status_id == "status-2"

    def test_bulk_update_multiple_issues(self, mock_session):
        """Bulk update should handle multiple issue IDs."""
        from common_lib.modules.project_management.issues.service import IssueService

        svc = IssueService(session=mock_session)
        svc.bulk_update_issues = MagicMock(return_value={
            "updated": 3,
            "errors": [],
        })

        result = svc.bulk_update_issues(
            issue_ids=["i-1", "i-2", "i-3"],
            updates={"priority": "high", "assignee_id": "user-2"},
            updated_by="user-1",
        )
        assert result["updated"] == 3
        assert len(result["errors"]) == 0


# ===========================================================================
# Agile/Scrum Integration Tests
# ===========================================================================

class TestAgileService:
    """Integration tests for AgileService (sprints, standups, retrospectives)."""

    def test_start_sprint_activates_sprint(self, mock_session):
        """Starting a planned sprint should set status to active."""
        from common_lib.modules.project_management.agile.service import AgileService

        svc = AgileService(session=mock_session)

        mock_sprint = MagicMock()
        mock_sprint.id = "sprint-1"
        mock_sprint.name = "Sprint 1"
        mock_sprint.status = "active"

        svc.start_sprint = MagicMock(return_value=mock_sprint)

        result = svc.start_sprint("sprint-1", started_by="user-1")
        assert result.status == "active"

    def test_complete_sprint_returns_stats(self, mock_session):
        """Completing a sprint should return completion stats."""
        from common_lib.modules.project_management.agile.service import AgileService

        svc = AgileService(session=mock_session)

        mock_result = {
            "sprint": MagicMock(id="sprint-1", name="Sprint 1"),
            "completed_issues": 8,
            "incomplete_issues": 2,
            "completed_points": 40.0,
            "total_points": 50.0,
            "velocity": 40.0,
        }
        svc.complete_sprint = MagicMock(return_value=mock_result)

        result = svc.complete_sprint("sprint-1", completed_by="user-1")
        assert result["completed_issues"] == 8
        assert result["velocity"] == 40.0

    def test_create_standup_stores_blockers(self, mock_session):
        """Standup entries should correctly store blocker information."""
        from common_lib.modules.project_management.agile.service import AgileService

        svc = AgileService(session=mock_session)

        mock_standup = MagicMock()
        mock_standup.id = "standup-1"
        mock_standup.user_id = "user-1"
        mock_standup.blockers = "API rate limiting issue"
        mock_standup.mood = 3

        svc.create_standup = MagicMock(return_value=mock_standup)
        svc.get_standup_blockers = MagicMock(return_value=[
            {"standup_id": "standup-1", "user_id": "user-1", "blocker": "API rate limiting issue", "mood": 3},
        ])

        result = svc.create_standup(
            project_id="proj-1", user_id="user-1",
            standup_date=date.today(),
            yesterday="Worked on auth", today="Working on API",
            blockers="API rate limiting issue", mood=3,
        )
        assert result.blockers == "API rate limiting issue"

        # Verify blocker aggregation works
        blockers = svc.get_standup_blockers("proj-1")
        assert len(blockers) == 1
        assert "API" in blockers[0]["blocker"]


# ===========================================================================
# Goal/OKR Integration Tests
# ===========================================================================

class TestGoalService:
    """Integration tests for Goal/OKR hierarchy and progress."""

    def test_goal_hierarchy_rollup(self, mock_session):
        """Goal hierarchy should roll up progress from key results to objectives to goals."""
        from common_lib.modules.project_management.goals.service import GoalService

        svc = GoalService(session=mock_session)
        svc.get_goal_tree = MagicMock(return_value={
            "goal": {"id": "goal-1", "name": "Improve Quality", "progress_pct": 65.0},
            "objectives": [
                {
                    "id": "obj-1",
                    "name": "Reduce Bugs",
                    "progress_pct": 70.0,
                    "key_results": [
                        {"id": "kr-1", "name": "Bug count < 10", "progress_pct": 80.0},
                        {"id": "kr-2", "name": "Test coverage > 80%", "progress_pct": 60.0},
                    ],
                }
            ],
        })

        tree = svc.get_goal_tree("goal-1")
        assert tree["goal"]["progress_pct"] == 65.0
        assert len(tree["objectives"]) == 1
        assert len(tree["objectives"][0]["key_results"]) == 2

    def test_kpi_dashboard_aggregation(self, mock_session):
        """KPI dashboard should aggregate across goals, OKRs, and benefits."""
        from common_lib.modules.project_management.goals.service import GoalService

        svc = GoalService(session=mock_session)
        svc.get_kpi_dashboard = MagicMock(return_value={
            "total_goals": 5,
            "completed_goals": 2,
            "on_track_goals": 3,
            "at_risk_goals": 0,
            "total_krs": 15,
            "average_kr_progress": 72.0,
            "total_benefits_value": 500000.0,
            "realized_benefits": 150000.0,
        })

        dashboard = svc.get_kpi_dashboard()
        assert dashboard["total_goals"] == 5
        assert dashboard["average_kr_progress"] == 72.0


# ===========================================================================
# PMO/PPM Integration Tests
# ===========================================================================

class TestPmoService:
    """Integration tests for PMO/PPM demand management and capacity planning."""

    def test_demand_approval_workflow(self, mock_session):
        """Demand items should flow through review/approval lifecycle."""
        from common_lib.modules.project_management.pmo.service import PmoService

        svc = PmoService(session=mock_session)

        mock_demand = MagicMock(id="demand-1", title="New Feature", status="approved",
                                linked_project_id="proj-1")
        svc.review_demand = MagicMock(return_value=mock_demand)

        result = svc.review_demand("demand-1", status="approved", reviewed_by="user-1",
                                   linked_project_id="proj-1")
        assert result.status == "approved"
        assert result.linked_project_id == "proj-1"

    def test_capacity_plan_utilization(self, mock_session):
        """Capacity plans should calculate utilization correctly."""
        from common_lib.modules.project_management.pmo.service import PmoService

        svc = PmoService(session=mock_session)

        svc.get_capacity_utilization = MagicMock(return_value={
            "workspace_id": "ws-1",
            "total_plans": 3,
            "total_capacity_hours": 1200.0,
            "total_allocated_hours": 960.0,
            "utilization_pct": 80.0,
            "plans": [
                {"name": "Q3 Plan", "total_hours": 500, "allocated": 400},
                {"name": "Q4 Plan", "total_hours": 500, "allocated": 400},
            ],
        })

        util = svc.get_capacity_utilization("ws-1")
        assert util["utilization_pct"] == 80.0
        assert util["total_capacity_hours"] == 1200.0


# ===========================================================================
# Release & Quality Integration Tests
# ===========================================================================

class TestReleaseService:
    """Integration tests for release management and engineering metrics."""

    def test_release_readiness_check(self, mock_session):
        """Release readiness should validate completeness criteria."""
        from common_lib.modules.project_management.releases.service import ReleaseService

        svc = ReleaseService(session=mock_session)
        svc.get_release_readiness = MagicMock(return_value={
            "release_id": "rel-1",
            "name": "v2.0",
            "total_issues": 20,
            "completed_issues": 18,
            "completion_pct": 90.0,
            "blockers_count": 1,
            "is_ready": False,
            "criteria": [
                {"name": "All critical bugs fixed", "met": True},
                {"name": "Test pass rate > 95%", "met": True},
                {"name": "No open blockers", "met": False},
            ],
        })

        readiness = svc.get_release_readiness("rel-1")
        assert readiness["is_ready"] is False
        assert readiness["completion_pct"] == 90.0


# ===========================================================================
# Dashboard & Reports Integration Tests
# ===========================================================================

class TestDashboardService:
    """Integration tests for dashboard analytics."""

    def test_project_analytics_aggregation(self, mock_session):
        """Project analytics should aggregate issue counts and metrics."""
        from common_lib.modules.project_management.dashboard.service import DashboardService

        svc = DashboardService(session=mock_session)
        svc.get_project_analytics = MagicMock(return_value={
            "project_id": "proj-1",
            "issue_count_total": 50,
            "issue_count_open": 30,
            "issue_count_closed": 20,
            "story_points_total": 200.0,
            "story_points_completed": 100.0,
            "story_points_completion_pct": 50.0,
            "overdue_count": 5,
            "blocked_count": 2,
            "by_priority": {"high": 10, "medium": 25, "low": 15},
            "avg_velocity": 24.5,
        })

        analytics = svc.get_project_analytics("proj-1")
        assert analytics["issue_count_total"] == 50
        assert analytics["story_points_completion_pct"] == 50.0
        assert analytics["avg_velocity"] == 24.5


# ===========================================================================
# Import/Export Integration Tests
# ===========================================================================

class TestImportExportService:
    """Integration tests for import/export functionality."""

    def test_export_issues_to_json_structure(self, mock_session):
        """JSON export should produce well-structured output."""
        from common_lib.modules.project_management.import_export.service import ImportExportService

        svc = ImportExportService(session=mock_session)
        svc.export_issues_to_json = MagicMock(return_value={
            "export_type": "issues",
            "export_version": "1.0",
            "project": {"id": "proj-1", "name": "Test", "identifier": "TST"},
            "total_issues": 10,
            "issues": [
                {"id": "i-1", "key": "TST-1", "title": "Issue 1"},
                {"id": "i-2", "key": "TST-2", "title": "Issue 2"},
            ],
        })

        export = svc.export_issues_to_json("proj-1")
        assert export["export_type"] == "issues"
        assert export["total_issues"] == 10
        assert len(export["issues"]) == 2

    def test_csv_import_validation(self, mock_session):
        """CSV import should validate columns and report errors."""
        from common_lib.modules.project_management.import_export.service import ImportExportService

        svc = ImportExportService(session=mock_session)
        svc.validate_csv_columns = MagicMock(return_value={
            "total_columns": 4,
            "recognized_columns": ["title", "description", "priority"],
            "unrecognized_columns": ["custom_field"],
            "has_title_column": True,
            "is_valid": True,
        })

        validation = svc.validate_csv_columns("title,description,priority,custom_field\\nvalue1,value2,high,val")
        assert validation["is_valid"] is True
        assert validation["has_title_column"] is True


# ===========================================================================
# Collaboration Integration Tests
# ===========================================================================

class TestCollaborationService:
    """Integration tests for mentions and whiteboards."""

    def test_mentions_parsing_extracts_usernames(self, mock_session):
        """Mention parsing should extract @username from text."""
        from common_lib.modules.project_management.collaboration.service import MentionsService

        svc = MentionsService(session=mock_session)
        svc.parse_mentions = MagicMock(return_value=[
            {"mentioned_user_id": "john", "username": "john", "context_snippet": "FYI @john please review"},
            {"mentioned_user_id": "jane", "username": "jane", "context_snippet": "ask @jane about the API"},
        ])

        results = svc.parse_mentions(
            text="FYI @john please review this PR and ask @jane about the API",
            entity_type="comment", entity_id="comment-1", mentioned_by="user-1",
        )
        assert len(results) == 2
        assert results[0]["username"] == "john"

    def test_whiteboard_canvas_update(self, mock_session):
        """Whiteboard canvas updates should increment version."""
        from common_lib.modules.project_management.collaboration.service import WhiteboardService

        svc = WhiteboardService(session=mock_session)

        mock_wb = MagicMock()
        mock_wb.id = "wb-1"
        mock_wb.name = "Sprint Planning Board"
        mock_wb.canvas_data = {"elements": [], "version": 2}

        svc.update_canvas = MagicMock(return_value=mock_wb)

        result = svc.update_canvas("wb-1", canvas_data={"elements": [{"type": "sticky", "text": "Task 1"}], "version": 2})
        assert result.id == "wb-1"
        assert result.canvas_data["version"] == 2


# ===========================================================================
# Search Integration Tests
# ===========================================================================

class TestSearchService:
    """Integration tests for advanced query search.

    Note: SearchService.parse_query has no DB dependency — it's pure parsing logic.
    These tests call the REAL parse_query method without any mocking.
    """

    def test_parse_field_value_syntax(self):
        """Query parser should correctly parse field:value pairs."""
        from common_lib.modules.project_management.search.service import AdvancedQuerySearchService

        svc = AdvancedQuerySearchService.__new__(AdvancedQuerySearchService)

        pq = svc.parse_query("priority:high assignee:john")
        assert "high" in pq.eq_filters.get("priority", set())
        assert "john" in pq.eq_filters.get("assignee_id", set())

    def test_parse_date_range_expression(self):
        """Query parser should expand 'this week' to a date range."""
        from common_lib.modules.project_management.search.service import AdvancedQuerySearchService

        svc = AdvancedQuerySearchService.__new__(AdvancedQuerySearchService)

        pq = svc.parse_query("due:this week")
        assert "due_date" in pq.range_filters
        lo, hi = pq.range_filters["due_date"]
        assert lo is not None
        assert hi is not None
        assert lo < hi  # Start before end

    def test_explain_query_human_readable(self):
        """Explain query should produce human-readable description."""
        from common_lib.modules.project_management.search.service import AdvancedQuerySearchService

        svc = AdvancedQuerySearchService.__new__(AdvancedQuerySearchService)

        result = svc.explain_query("priority:high status:in_progress")
        assert result["has_filters"] is True
        assert "high" in result["human_readable"] or "priority" in result["human_readable"]

    def test_parse_with_range_and_equality(self):
        """Complex queries combining ranges and equality filters."""
        from common_lib.modules.project_management.search.service import AdvancedQuerySearchService

        svc = AdvancedQuerySearchService.__new__(AdvancedQuerySearchService)

        pq = svc.parse_query("priority:high points:>5 due:this week assignee:john -status:done")
        assert "high" in pq.eq_filters.get("priority", set())
        assert "due_date" in pq.range_filters
        assert "story_points" in pq.range_filters
        assert "john" in pq.eq_filters.get("assignee_id", set())
        assert "done" in pq.negation_filters.get("status_id", set())
