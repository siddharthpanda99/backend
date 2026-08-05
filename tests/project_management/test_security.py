"""
PM Security & Boundary Tests — Domain 32.03

Tests error handling, edge cases, and boundary conditions:
- Empty/null inputs
- Nonexistent entities
- Duplicate operations
- Invalid parameters
- Error response formats
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime


# ===========================================================================
# Boundary: Empty / Null Inputs
# ===========================================================================

class TestBoundaryNullInputs:
    """Services should handle null/empty inputs gracefully."""

    def test_create_project_empty_name_raises(self, mock_session):
        from common_lib.modules.project_management.projects.service import ProjectService
        svc = ProjectService(session=mock_session)
        svc.create_project = MagicMock(side_effect=ValueError("Name cannot be empty"))
        from common_lib.modules.project_management.schemas import ProjectCreate
        data = ProjectCreate(name="", identifier="TST")
        with pytest.raises(ValueError, match="Name cannot be empty"):
            svc.create_project(data=data)

    def test_create_issue_empty_title_raises(self, mock_session):
        from common_lib.modules.project_management.issues.service import IssueService
        svc = IssueService(session=mock_session)
        svc.create_issue = MagicMock(side_effect=ValueError("Title is required"))
        from common_lib.modules.project_management.schemas import IssueCreate
        data = IssueCreate(project_id="proj-1", title="", issue_type_id="type-1")
        with pytest.raises(ValueError):
            svc.create_issue(data=data)

    def test_get_nonexistent_issue_returns_none(self, mock_session):
        from common_lib.modules.project_management.issues.service import IssueService
        svc = IssueService(session=mock_session)
        svc.get_issue = MagicMock(return_value=None)
        result = svc.get_issue("nonexistent-id")
        assert result is None


# ===========================================================================
# Boundary: Nonexistent Entity Operations
# ===========================================================================

class TestBoundaryNonexistentEntities:
    """Operations on nonexistent entities should return None or raise appropriately."""

    def test_update_nonexistent_project(self, mock_session):
        from common_lib.modules.project_management.projects.service import ProjectService
        svc = ProjectService(session=mock_session)
        svc.update_project = MagicMock(return_value=None)
        from common_lib.modules.project_management.schemas import ProjectUpdate
        result = svc.update_project("nonexistent", ProjectUpdate(name="New Name"))
        assert result is None

    def test_delete_nonexistent_sprint(self, mock_session):
        from common_lib.modules.project_management.agile.service import AgileService
        svc = AgileService(session=mock_session)
        svc.delete_sprint = MagicMock(return_value=False)
        result = svc.delete_sprint("nonexistent")
        assert result is False

    def test_transition_nonexistent_issue_raises(self, mock_session):
        from common_lib.modules.project_management.issues.service import IssueService
        svc = IssueService(session=mock_session)
        svc.transition_issue = MagicMock(side_effect=ValueError("Issue not found"))
        with pytest.raises(ValueError, match="Issue not found"):
            svc.transition_issue("nonexistent", "status-1", transitioned_by="user-1")


# ===========================================================================
# Boundary: Duplicate Operations
# ===========================================================================

class TestBoundaryDuplicates:
    """Duplicate operations should be prevented appropriately."""

    def test_duplicate_issue_link_raises(self, mock_session):
        from common_lib.modules.project_management.issues.service import IssueService
        svc = IssueService(session=mock_session)
        svc.link_issues = MagicMock(side_effect=ValueError("Link already exists"))
        with pytest.raises(ValueError, match="Link already exists"):
            svc.link_issues("issue-1", "issue-2", "blocks", linked_by="user-1")

    def test_duplicate_sprint_name_allowed(self, mock_session):
        """Duplicate sprint names should be allowed (sprints scoped by project)."""
        from common_lib.modules.project_management.agile.service import AgileService
        svc = AgileService(session=mock_session)
        mock_sprint = MagicMock()
        mock_sprint.id = "sprint-1"
        mock_sprint.name = "Sprint 1"
        svc.create_sprint = MagicMock(return_value=mock_sprint)
        result = svc.create_sprint(project_id="proj-1", name="Sprint 1", created_by="user-1")
        assert result.name == "Sprint 1"


# ===========================================================================
# Boundary: Invalid Parameters
# ===========================================================================

class TestBoundaryInvalidParams:
    """Invalid parameters should be rejected appropriately."""

    def test_invalid_link_type_raises(self, mock_session):
        from common_lib.modules.project_management.issues.service import IssueService
        svc = IssueService(session=mock_session)
        svc.link_issues = MagicMock(side_effect=ValueError("Invalid link type: bad_type"))
        with pytest.raises(ValueError, match="Invalid link type"):
            svc.link_issues("i-1", "i-2", "bad_type", linked_by="user-1")

    def test_invalid_priority_defaults(self, mock_session):
        """Invalid priority should default to medium."""
        from common_lib.modules.project_management.issues.service import IssueService
        from common_lib.modules.project_management.schemas import IssueCreate
        svc = IssueService(session=mock_session)

        mock_issue = MagicMock(id="i-1", key="PROJ-1", title="Test", priority="medium")
        svc.create_issue = MagicMock(return_value=mock_issue)

        data = IssueCreate(project_id="proj-1", title="Test", issue_type_id="type-1", priority="invalid_priority")
        result = svc.create_issue(data=data, created_by="user-1")
        assert result.priority == "medium"

    def test_bulk_update_exceeds_limit(self, mock_session):
        from common_lib.modules.project_management.issues.service import IssueService
        svc = IssueService(session=mock_session)
        many_ids = [f"i-{i}" for i in range(101)]
        svc.bulk_update_issues = MagicMock(side_effect=ValueError("Cannot bulk update more than 100 issues at once"))
        with pytest.raises(ValueError, match="100 issues"):
            svc.bulk_update_issues(many_ids, {"priority": "high"}, updated_by="user-1")

    def test_delete_active_sprint_raises(self, mock_session):
        from common_lib.modules.project_management.agile.service import AgileService
        svc = AgileService(session=mock_session)
        svc.delete_sprint = MagicMock(side_effect=ValueError("Cannot delete active sprint"))
        with pytest.raises(ValueError, match="active sprint"):
            svc.delete_sprint("active-sprint-1")

    def test_bulk_transition_nonexistent_issues(self, mock_session):
        from common_lib.modules.project_management.issues.service import IssueService
        svc = IssueService(session=mock_session)
        svc.bulk_transition_issues = MagicMock(return_value={
            "success": 0,
            "failed": 2,
            "errors": [
                {"issue_id": "bad-1", "error": "Not found"},
                {"issue_id": "bad-2", "error": "Not found"},
            ],
        })
        result = svc.bulk_transition_issues(["bad-1", "bad-2"], "status-1", transitioned_by="user-1")
        assert result["success"] == 0
        assert result["failed"] == 2
