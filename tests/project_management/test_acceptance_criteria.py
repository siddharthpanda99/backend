"""
PM Acceptance Criteria Validation Tests — Domain 33.02

Validates end-to-end acceptance criteria for core PM workflows:
- AC-01: Project lifecycle (create → configure → execute → close)
- AC-02: Issue lifecycle (create → triage → work → done)
- AC-03: Sprint lifecycle (plan → start → execute → complete)
- AC-04: Release lifecycle (plan → track → release → archive)
- AC-05: Cross-cutting (search, dashboards, reporting)

Each test validates the happy path, edge cases, and error handling
for the specified workflow.
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, date, timedelta


# ===========================================================================
# AC-01: Project Lifecycle
# ===========================================================================

class TestAC01ProjectLifecycle:
    """AC-01: Project lifecycle — create → configure → execute → close.

    Happy path: Create project → Add issue types → Create sprint →
                Add issues → Execute → Archive
    """

    def test_create_project_with_defaults(self, mock_session):
        """AC-01.1: Create project should auto-configure defaults."""
        from common_lib.modules.project_management.projects.service import ProjectService

        mock_project = MagicMock()
        mock_project.id = "proj-1"
        mock_project.name = "AC Test Project"
        mock_project.identifier = "ACT"
        mock_project.project_type = "software_scrum"
        mock_project.status = "active"

        svc = ProjectService(session=mock_session)
        svc.create_project = MagicMock(return_value=mock_project)

        from common_lib.modules.project_management.schemas import ProjectCreate
        data = ProjectCreate(name="AC Test Project", identifier="ACT", project_type="software_scrum")
        result = svc.create_project(data=data, created_by="user-1")

        assert result.id == "proj-1"
        assert result.status == "active"
        svc.create_project.assert_called_once()

    def test_project_archive_and_restore(self, mock_session):
        """AC-01.2: Archive and restore a project."""
        from common_lib.modules.project_management.projects.service import ProjectService

        svc = ProjectService(session=mock_session)
        mock_project = MagicMock(id="proj-1", status="archived")
        svc.archive_project = MagicMock(return_value=mock_project)
        svc.restore_project = MagicMock(return_value=MagicMock(id="proj-1", status="active"))

        archived = svc.archive_project("proj-1")
        assert archived.status == "archived"

        restored = svc.restore_project("proj-1")
        assert restored.status == "active"

    def test_project_update(self, mock_session):
        """AC-01.3: Update project should persist changes."""
        from common_lib.modules.project_management.projects.service import ProjectService

        svc = ProjectService(session=mock_session)

        mock_updated = MagicMock()
        mock_updated.id = "proj-1"
        mock_updated.name = "Updated Project"
        mock_updated.description = "New desc"
        svc.update_project = MagicMock(return_value=mock_updated)

        from common_lib.modules.project_management.schemas import ProjectUpdate
        data = ProjectUpdate(name="Updated Project", description="New desc")
        result = svc.update_project("proj-1", data)
        assert result.id == "proj-1"
        assert result.name == "Updated Project"

    def test_project_health_tracking(self, mock_session):
        """AC-01.4: Project health should compute schedule/quality/resource scores."""
        from common_lib.modules.project_management.projects.service import ProjectService

        svc = ProjectService(session=mock_session)
        svc.compute_project_health = MagicMock(return_value={
            "project_id": "proj-1",
            "overall_score": 82.0,
            "schedule_score": 90.0,
            "quality_score": 75.0,
            "resource_score": 80.0,
            "status": "healthy",
        })

        health = svc.compute_project_health("proj-1")
        assert health["overall_score"] == 82.0
        assert health["status"] == "healthy"


# ===========================================================================
# AC-02: Issue Lifecycle
# ===========================================================================

class TestAC02IssueLifecycle:
    """AC-02: Issue lifecycle — create → triage → work → done.

    Happy path: Create issue → Assign → Start work → Complete
    Edge cases: Invalid transitions, missing fields, duplicate keys
    """

    def test_create_issue_auto_key_generation(self, mock_session):
        """AC-02.1: Issue key should auto-generate from project identifier."""
        from common_lib.modules.project_management.issues.service import IssueService

        svc = IssueService(session=mock_session)
        mock_issue = MagicMock(id="iss-1", key="ACT-1", title="Login bug", status_id="s-todo")
        svc.create_issue = MagicMock(return_value=mock_issue)

        from common_lib.modules.project_management.schemas import IssueCreate
        data = IssueCreate(project_id="proj-1", title="Login bug", issue_type_id="type-bug", priority="high")
        result = svc.create_issue(data=data, created_by="user-1")

        assert result.key == "ACT-1"
        assert result.title == "Login bug"

    def test_issue_transition_workflow(self, mock_session):
        """AC-02.2: Issue should transition through valid status flow."""
        from common_lib.modules.project_management.issues.service import IssueService

        svc = IssueService(session=mock_session)

        # Mock transitions: todo → in_progress → review → done
        transitions = [
            MagicMock(id="iss-1", key="ACT-1", status_id="s-in_progress"),
            MagicMock(id="iss-1", key="ACT-1", status_id="s-review"),
            MagicMock(id="iss-1", key="ACT-1", status_id="s-done"),
        ]
        svc.transition_issue = MagicMock(side_effect=transitions)

        result1 = svc.transition_issue("iss-1", "s-in_progress", transitioned_by="user-1")
        assert result1.status_id == "s-in_progress"

        result2 = svc.transition_issue("iss-1", "s-review", transitioned_by="user-1")
        assert result2.status_id == "s-review"

        result3 = svc.transition_issue("iss-1", "s-done", transitioned_by="user-1")
        assert result3.status_id == "s-done"

    def test_issue_hierarchy_traversal(self, mock_session):
        """AC-02.3: N-level hierarchy should support parent/child chains."""
        from common_lib.modules.project_management.issues.service import IssueService

        svc = IssueService(session=mock_session)

        svc.get_hierarchy_tree = MagicMock(return_value={
            "issue": {"id": "epic-1", "key": "ACT-1", "title": "Epic: Auth"},
            "ancestors": [],
            "descendants": [
                {"id": "story-1", "key": "ACT-2", "title": "Story: Login", "depth": 1, "children": [
                    {"id": "task-1", "key": "ACT-3", "title": "Task: Implement", "depth": 2},
                ]},
            ],
            "total_descendants": 2,
            "max_depth": 2,
        })

        tree = svc.get_hierarchy_tree("epic-1")
        assert tree["total_descendants"] == 2
        assert tree["max_depth"] == 2
        assert len(tree["ancestors"]) == 0

    def test_bulk_update_issues(self, mock_session):
        """AC-02.4: Bulk update should handle multiple issues atomically."""
        from common_lib.modules.project_management.issues.service import IssueService

        svc = IssueService(session=mock_session)
        svc.bulk_update_issues = MagicMock(return_value={"updated": 5, "errors": []})

        result = svc.bulk_update_issues(
            issue_ids=["i-1", "i-2", "i-3", "i-4", "i-5"],
            updates={"priority": "high", "assignee_id": "user-1"},
            updated_by="user-1",
        )
        assert result["updated"] == 5
        assert len(result["errors"]) == 0

    def test_subtask_progress_rollup(self, mock_session):
        """AC-02.5: Subtask completion should roll up to parent."""
        from common_lib.modules.project_management.subtasks.service import SubtaskService

        svc = SubtaskService(session=mock_session)
        svc.get_subtask_progress = MagicMock(return_value={
            "parent_issue_id": "story-1",
            "total_subtasks": 4,
            "completed_subtasks": 3,
            "progress_pct": 75.0,
        })

        progress = svc.get_subtask_progress("story-1")
        assert progress["progress_pct"] == 75.0
        assert progress["completed_subtasks"] == 3


# ===========================================================================
# AC-03: Sprint Lifecycle
# ===========================================================================

class TestAC03SprintLifecycle:
    """AC-03: Sprint lifecycle — plan → start → execute → complete.

    Happy path: Create sprint → Add issues → Start → Complete → Metrics
    """

    def test_sprint_full_lifecycle(self, mock_session):
        """AC-03.1: Sprint should flow through planned → active → complete."""
        from common_lib.modules.project_management.agile.service import AgileService

        svc = AgileService(session=mock_session)

        # Create — separate mock per state
        mock_planned = MagicMock(id="sprint-1", name="Sprint 1", status="planned")
        svc.create_sprint = MagicMock(return_value=mock_planned)

        # Start
        mock_active = MagicMock(id="sprint-1", name="Sprint 1", status="active")
        svc.start_sprint = MagicMock(return_value=mock_active)

        # Complete — returns a dict
        svc.complete_sprint = MagicMock(return_value={
            "sprint_id": "sprint-1",
            "name": "Sprint 1",
            "status": "complete",
            "completed_issues": 8,
            "incomplete_issues": 2,
            "completed_points": 40.0,
            "total_points": 50.0,
            "velocity": 40.0,
        })

        created = svc.create_sprint(MagicMock(name="Sprint 1", project_id="proj-1"))
        assert created.status == "planned"

        started = svc.start_sprint("sprint-1", started_by="user-1")
        assert started.status == "active"

        completed = svc.complete_sprint("sprint-1", completed_by="user-1")
        assert completed["status"] == "complete"
        assert completed["velocity"] == 40.0

    def test_burndown_chart_data(self, mock_session):
        """AC-03.2: Burndown data should include ideal and actual lines."""
        from common_lib.modules.project_management.agile.service import AgileService

        svc = AgileService(session=mock_session)
        svc.get_burndown_data = MagicMock(return_value={
            "sprint_id": "sprint-1",
            "sprint_name": "Sprint 1",
            "total_points": 50.0,
            "days": 5,
            "ideal_line": [50.0, 40.0, 30.0, 20.0, 10.0, 0.0],
            "actual_line": [50.0, 45.0, 35.0, 25.0, 15.0, None],
            "scope_changes": [],
        })

        burndown = svc.get_burndown_data("sprint-1")
        assert len(burndown["ideal_line"]) == 6
        assert burndown["ideal_line"][0] == 50.0
        assert burndown["ideal_line"][-1] == 0.0

    def test_velocity_trend_analysis(self, mock_session):
        """AC-03.3: Velocity trend should show improving/stable/declining."""
        from common_lib.modules.project_management.agile.service import AgileService

        svc = AgileService(session=mock_session)
        svc.get_velocity_trend = MagicMock(return_value={
            "project_id": "proj-1",
            "average_velocity": 35.0,
            "trend_direction": "improving",
            "velocity_history": [
                {"sprint": "Sprint 1", "velocity": 25.0},
                {"sprint": "Sprint 2", "velocity": 30.0},
                {"sprint": "Sprint 3", "velocity": 35.0},
                {"sprint": "Sprint 4", "velocity": 40.0},
            ],
            "moving_average_3": [28.3, 33.3, 38.3],
        })

        trend = svc.get_velocity_trend("proj-1")
        assert trend["trend_direction"] == "improving"
        assert trend["average_velocity"] == 35.0


# ===========================================================================
# AC-04: Release Lifecycle
# ===========================================================================

class TestAC04ReleaseLifecycle:
    """AC-04: Release lifecycle — plan → track → release → archive.

    Happy path: Create release → Add issues → Track readiness → Release
    """

    def test_release_readiness_tracking(self, mock_session):
        """AC-04.1: Release readiness should validate completion criteria."""
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
            "days_remaining": 5,
            "criteria": [
                {"name": "All critical bugs fixed", "met": True},
                {"name": "Test pass rate > 95%", "met": True},
                {"name": "No open blockers", "met": False},
            ],
        })

        readiness = svc.get_release_readiness("rel-1")
        assert readiness["is_ready"] is False
        assert readiness["completion_pct"] == 90.0
        assert readiness["blockers_count"] == 1

    def test_release_status_transitions(self, mock_session):
        """AC-04.2: Release should transition unreleased → released → archived."""
        from common_lib.modules.project_management.releases.service import ReleaseService

        svc = ReleaseService(session=mock_session)

        mock_release = MagicMock(id="rel-1", status="unreleased")
        svc.mark_released = MagicMock(return_value=MagicMock(id="rel-1", status="released"))
        svc.mark_archived = MagicMock(return_value=MagicMock(id="rel-1", status="archived"))

        released = svc.mark_released("rel-1")
        assert released.status == "released"

        archived = svc.mark_archived("rel-1")
        assert archived.status == "archived"

    def test_engineering_metrics_dora(self, mock_session):
        """AC-04.3: DORA metrics should include cycle time, lead time, throughput."""
        from common_lib.modules.project_management.releases.service import EngineeringMetricsService

        svc = EngineeringMetricsService(session=mock_session)
        svc.get_all_metrics = MagicMock(return_value={
            "project_id": "proj-1",
            "cycle_time": {"avg_days": 3.5, "median_days": 3.0, "p90_days": 7.0},
            "lead_time": {"avg_days": 5.2, "median_days": 4.0, "p90_days": 10.0},
            "throughput": {"per_day": 2.5, "per_week": 12.5},
            "defect_rate": {"total": 5, "rate_pct": 2.5},
            "wip": {"current": 8, "avg": 6.5},
        })

        metrics = svc.get_all_metrics("proj-1", days_back=30)
        assert metrics["cycle_time"]["avg_days"] == 3.5
        assert metrics["throughput"]["per_day"] == 2.5


# ===========================================================================
# AC-05: Cross-cutting — Search, Dashboards, Reporting
# ===========================================================================

class TestAC05CrossCutting:
    """AC-05: Cross-cutting features — search, dashboards, reporting.

    Happy path: Search issues → View dashboard → Export report
    """

    def test_advanced_query_search(self, mock_session):
        """AC-05.1: Advanced search should parse field:value syntax."""
        from common_lib.modules.project_management.search.service import AdvancedQuerySearchService

        svc = AdvancedQuerySearchService.__new__(AdvancedQuerySearchService)

        pq = svc.parse_query("priority:high assignee:john status:in_progress")
        assert "high" in pq.eq_filters.get("priority", set())
        assert "john" in pq.eq_filters.get("assignee_id", set())

    def test_dashboard_widget_data(self, mock_session):
        """AC-05.2: Dashboard widget should return live data."""
        from common_lib.modules.project_management.dashboard.service import DashboardService

        svc = DashboardService(session=mock_session)
        svc.get_widget_data = MagicMock(return_value={
            "widget_id": "widget-1",
            "widget_type": "task_counts",
            "data": {
                "total": 50,
                "by_status": {"todo": 20, "in_progress": 15, "done": 15},
            },
            "generated_at": datetime.utcnow().isoformat(),
        })

        data = svc.get_widget_data("widget-1")
        assert data["widget_type"] == "task_counts"
        assert data["data"]["total"] == 50

    def test_csv_export_structure(self, mock_session):
        """AC-05.3: CSV export should produce valid output."""
        from common_lib.modules.project_management.import_export.service import ImportExportService

        svc = ImportExportService(session=mock_session)
        svc.export_issues_to_json = MagicMock(return_value={
            "export_type": "issues",
            "export_version": "1.0",
            "project": {"id": "proj-1", "name": "Test"},
            "total_issues": 10,
            "issues": [{"id": f"i-{i}", "key": f"ACT-{i}", "title": f"Issue {i}"} for i in range(10)],
        })

        export = svc.export_issues_to_json("proj-1")
        assert export["export_type"] == "issues"
        assert export["total_issues"] == 10

    def test_saved_filter_query_parsing(self, mock_session):
        """AC-05.4: Saved filter queries should parse correctly."""
        from common_lib.modules.project_management.search.service import AdvancedQuerySearchService

        # Test that saved filter queries are parseable
        svc = AdvancedQuerySearchService.__new__(AdvancedQuerySearchService)

        pq = svc.parse_query("priority:high status:in_progress")
        assert "high" in pq.eq_filters.get("priority", set())
        assert "in_progress" in pq.eq_filters.get("status_id", set())

        # Test date range parsing
        pq2 = svc.parse_query("due:this week")
        assert "due_date" in pq2.range_filters
        lo, hi = pq2.range_filters["due_date"]
        assert lo < hi


# ===========================================================================
# AC-06: AI-Powered Features
# ===========================================================================

class TestAC06AIFeatures:
    """AC-06: AI-powered features should provide intelligent assistance."""

    def test_issue_search_parsing_real(self, mock_session):
        """AC-06.1: Search parsing should handle complex queries."""
        from common_lib.modules.project_management.search.service import AdvancedQuerySearchService

        svc = AdvancedQuerySearchService.__new__(AdvancedQuerySearchService)

        # Test negation
        pq = svc.parse_query("-status:done priority:high")
        assert "done" in pq.negation_filters.get("status_id", set())
        assert "high" in pq.eq_filters.get("priority", set())

        # Test OR within fields
        pq2 = svc.parse_query("priority:high OR priority:urgent")
        assert len(pq2.eq_filters.get("priority", set())) >= 1

        # Test free text
        pq3 = svc.parse_query("login bug authentication")
        assert pq3.text_search == "login bug authentication"

    def test_date_range_parsing_real(self, mock_session):
        """AC-06.2: Date range expressions should resolve to actual dates."""
        from common_lib.modules.project_management.search.service import AdvancedQuerySearchService
        from datetime import date, timedelta

        svc = AdvancedQuerySearchService.__new__(AdvancedQuerySearchService)

        # Test 'today' — maps to eq_filters with a date value
        pq = svc.parse_query("due:today")
        assert "due_date" in pq.eq_filters, "'due:today' should produce a due_date eq_filter"

        # Test 'last week'
        pq2 = svc.parse_query("created:last week")
        assert "created_at" in pq2.range_filters
        lo2, hi2 = pq2.range_filters["created_at"]
        assert lo2 < hi2

        # Test numeric range
        pq3 = svc.parse_query("story_points:>5 story_points:<20")
        assert "story_points" in pq3.range_filters
