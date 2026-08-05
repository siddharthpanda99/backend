"""
Tests for newly added PM @node wrappers.

Covers: labels, components, watcher, activity, saved_filters,
time_tracking, and kanban node wrappers.

Each test verifies the wrapper returns the expected dict shape
and handles errors gracefully.
"""

import pytest
from unittest.mock import MagicMock, patch
from sqlmodel import Session


# ── Helper: mock session fixture ─────────────────────────────────────────

@pytest.fixture
def mock_session():
    """Create a mock SQLModel Session."""
    return MagicMock(spec=Session)


@pytest.fixture(autouse=True)
def patch_get_session(mock_session):
    """Patch _get_session to return our mock session."""
    with patch("common_lib.modules.project_management.nodes._get_session", return_value=mock_session):
        yield


# ── Labels ───────────────────────────────────────────────────────────────

class TestLabelsNodes:
    """Test label node wrappers."""

    def test_create_label_success(self, mock_session):
        from common_lib.modules.project_management.labels.nodes import create_label
        mock_label = MagicMock()
        mock_label.id = "label-1"
        mock_label.name = "bug"
        mock_label.project_id = "proj-1"

        with patch("common_lib.modules.project_management.labels.service.LabelService.create_label", return_value=mock_label):
            result = create_label(project_id="proj-1", name="bug", color="#ff0000")
            assert result["id"] == "label-1"
            assert result["name"] == "bug"

    def test_list_labels_success(self, mock_session):
        from common_lib.modules.project_management.labels.nodes import list_labels
        mock_label = MagicMock()
        mock_label.model_dump.return_value = {"id": "l-1", "name": "bug"}

        with patch("common_lib.modules.project_management.labels.service.LabelService.list_labels", return_value=[mock_label]):
            result = list_labels(project_id="proj-1")
            assert result["total"] == 1
            assert len(result["labels"]) == 1

    def test_update_label_not_found(self, mock_session):
        from common_lib.modules.project_management.labels.nodes import update_label
        with patch("common_lib.modules.project_management.labels.service.LabelService.update_label", return_value=None):
            result = update_label(label_id="nonexistent", name="new-name")
            assert "error" in result

    def test_delete_label_success(self, mock_session):
        from common_lib.modules.project_management.labels.nodes import delete_label
        with patch("common_lib.modules.project_management.labels.service.LabelService.delete_label", return_value=True):
            result = delete_label(label_id="label-1")
            assert result["success"] is True


# ── Components ───────────────────────────────────────────────────────────

class TestComponentsNodes:
    """Test component node wrappers."""

    def test_create_component_success(self, mock_session):
        from common_lib.modules.project_management.components.nodes import create_component
        mock_comp = MagicMock()
        mock_comp.id = "comp-1"
        mock_comp.name = "Backend"
        mock_comp.project_id = "proj-1"

        with patch("common_lib.modules.project_management.components.service.ComponentService.create_component", return_value=mock_comp):
            result = create_component(project_id="proj-1", name="Backend")
            assert result["id"] == "comp-1"
            assert result["name"] == "Backend"

    def test_list_components_success(self, mock_session):
        from common_lib.modules.project_management.components.nodes import list_components
        mock_comp = MagicMock()
        mock_comp.model_dump.return_value = {"id": "c-1", "name": "Backend"}

        with patch("common_lib.modules.project_management.components.service.ComponentService.list_components", return_value=[mock_comp]):
            result = list_components(project_id="proj-1")
            assert result["total"] == 1


# ── Watcher ──────────────────────────────────────────────────────────────

class TestWatcherNodes:
    """Test watcher node wrappers."""

    def test_add_watcher_success(self, mock_session):
        from common_lib.modules.project_management.watcher.nodes import add_watcher
        with patch("common_lib.modules.project_management.watcher.service.WatcherService.add_watcher", return_value=True):
            result = add_watcher(issue_id="issue-1", user_id="user-1")
            assert result["success"] is True

    def test_remove_watcher_success(self, mock_session):
        from common_lib.modules.project_management.watcher.nodes import remove_watcher
        with patch("common_lib.modules.project_management.watcher.service.WatcherService.remove_watcher", return_value=True):
            result = remove_watcher(issue_id="issue-1", user_id="user-1")
            assert result["success"] is True

    def test_list_watchers_success(self, mock_session):
        from common_lib.modules.project_management.watcher.nodes import list_watchers
        with patch("common_lib.modules.project_management.watcher.service.WatcherService.list_watchers", return_value=["user-1", "user-2"]):
            result = list_watchers(issue_id="issue-1")
            assert result["count"] == 2

    def test_is_watching_true(self, mock_session):
        from common_lib.modules.project_management.watcher.nodes import is_watching
        with patch("common_lib.modules.project_management.watcher.service.WatcherService.is_watching", return_value=True):
            result = is_watching(issue_id="issue-1", user_id="user-1")
            assert result["is_watching"] is True


# ── Activity ─────────────────────────────────────────────────────────────

class TestActivityNodes:
    """Test activity node wrappers."""

    def test_get_activity_feed_success(self, mock_session):
        from common_lib.modules.project_management.activity.nodes import get_activity_feed
        expected = {"items": [], "total": 0, "has_more": False}
        with patch("common_lib.modules.project_management.activity.service.ActivityService.get_activity_feed", return_value=expected):
            result = get_activity_feed(project_id="proj-1")
            assert result["total"] == 0
            assert result["has_more"] is False

    def test_get_activity_feed_with_filters(self, mock_session):
        from common_lib.modules.project_management.activity.nodes import get_activity_feed
        expected = {"items": [{"id": "a-1"}], "total": 1, "has_more": False}
        with patch("common_lib.modules.project_management.activity.service.ActivityService.get_activity_feed", return_value=expected):
            result = get_activity_feed(issue_id="issue-1", actor_id="user-1", action="created", limit=10)
            assert result["total"] == 1


# ── Saved Filters ────────────────────────────────────────────────────────

class TestSavedFilterNodes:
    """Test saved filter node wrappers."""

    def test_create_saved_filter_success(self, mock_session):
        from common_lib.modules.project_management.saved_filters.nodes import create_saved_filter
        mock_filter = MagicMock()
        mock_filter.id = "f-1"
        mock_filter.name = "My Bugs"
        mock_filter.project_id = "proj-1"

        with patch("common_lib.modules.project_management.saved_filters.service.SavedFilterService.create_filter", return_value=mock_filter):
            result = create_saved_filter(
                project_id="proj-1", user_id="user-1", name="My Bugs",
                filter_config={"status": "To Do"},
            )
            assert result["id"] == "f-1"
            assert result["name"] == "My Bugs"

    def test_list_saved_filters_success(self, mock_session):
        from common_lib.modules.project_management.saved_filters.nodes import list_saved_filters
        mock_filter = MagicMock()
        mock_filter.model_dump.return_value = {"id": "f-1", "name": "My Filters"}

        with patch("common_lib.modules.project_management.saved_filters.service.SavedFilterService.list_filters", return_value=[mock_filter]):
            result = list_saved_filters(project_id="proj-1")
            assert result["total"] == 1

    def test_get_saved_filter_not_found(self, mock_session):
        from common_lib.modules.project_management.saved_filters.nodes import get_saved_filter
        with patch("common_lib.modules.project_management.saved_filters.service.SavedFilterService.get_filter", return_value=None):
            result = get_saved_filter(filter_id="nonexistent")
            assert "error" in result

    def test_update_saved_filter_success(self, mock_session):
        from common_lib.modules.project_management.saved_filters.nodes import update_saved_filter
        mock_filter = MagicMock()
        mock_filter.id = "f-1"
        mock_filter.name = "Updated"

        with patch("common_lib.modules.project_management.saved_filters.service.SavedFilterService.update_filter", return_value=mock_filter):
            result = update_saved_filter(filter_id="f-1", name="Updated")
            assert result["id"] == "f-1"


# ── Time Tracking ────────────────────────────────────────────────────────

class TestTimeTrackingNodes:
    """Test time tracking node wrappers."""

    def test_log_time_success(self, mock_session):
        from common_lib.modules.project_management.time_tracking.nodes import log_time
        mock_entry = MagicMock()
        mock_entry.id = "te-1"
        mock_entry.minutes = 60
        mock_entry.issue_id = "issue-1"

        with patch("common_lib.modules.project_management.time_tracking.service.TimeTrackingService.log_time", return_value=mock_entry):
            result = log_time(issue_id="issue-1", user_id="user-1", minutes=60)
            assert result["id"] == "te-1"
            assert result["minutes"] == 60

    def test_start_timer_success(self, mock_session):
        from common_lib.modules.project_management.time_tracking.nodes import start_timer
        from datetime import datetime
        mock_entry = MagicMock()
        mock_entry.id = "te-1"
        mock_entry.start_time = datetime(2026, 1, 1, 12, 0, 0)
        mock_entry.is_running = True

        with patch("common_lib.modules.project_management.time_tracking.service.TimeTrackingService.start_timer", return_value=mock_entry):
            result = start_timer(issue_id="issue-1")
            assert result["is_running"] is True
            assert result["id"] == "te-1"

    def test_stop_timer_not_found(self, mock_session):
        from common_lib.modules.project_management.time_tracking.nodes import stop_timer
        with patch("common_lib.modules.project_management.time_tracking.service.TimeTrackingService.stop_timer", return_value=None):
            result = stop_timer(entry_id="nonexistent")
            assert "error" in result

    def test_get_time_report_success(self, mock_session):
        from common_lib.modules.project_management.time_tracking.nodes import get_time_report
        expected = {"total_minutes": 120, "billable_minutes": 60}
        with patch("common_lib.modules.project_management.time_tracking.service.TimeTrackingService.get_time_report", return_value=expected):
            result = get_time_report(issue_id="issue-1")
            assert result["total_minutes"] == 120

    def test_delete_time_entry_success(self, mock_session):
        from common_lib.modules.project_management.time_tracking.nodes import delete_time_entry
        with patch("common_lib.modules.project_management.time_tracking.service.TimeTrackingService.delete_entry", return_value=True):
            result = delete_time_entry(entry_id="te-1")
            assert result["success"] is True


# ── Kanban ───────────────────────────────────────────────────────────────

class TestKanbanNodes:
    """Test kanban board node wrappers."""

    def test_create_kanban_board_success(self, mock_session):
        from common_lib.modules.project_management.kanban.nodes import create_kanban_board
        mock_board = MagicMock()
        mock_board.id = "board-1"
        mock_board.name = "Sprint Board"
        mock_board.project_id = "proj-1"

        with patch("common_lib.modules.project_management.kanban.service.KanbanService.create_board", return_value=mock_board):
            result = create_kanban_board(project_id="proj-1", name="Sprint Board")
            assert result["id"] == "board-1"
            assert result["name"] == "Sprint Board"

    def test_get_kanban_board_not_found(self, mock_session):
        from common_lib.modules.project_management.kanban.nodes import get_kanban_board
        with patch("common_lib.modules.project_management.kanban.service.KanbanService.get_board", return_value=None):
            result = get_kanban_board(board_id="nonexistent")
            assert "error" in result

    def test_list_kanban_boards_success(self, mock_session):
        from common_lib.modules.project_management.kanban.nodes import list_kanban_boards
        mock_board = MagicMock()
        mock_board.model_dump.return_value = {"id": "b-1", "name": "Board 1"}

        with patch("common_lib.modules.project_management.kanban.service.KanbanService.list_boards", return_value=[mock_board]):
            result = list_kanban_boards(project_id="proj-1")
            assert result["total"] == 1

    def test_update_kanban_board_success(self, mock_session):
        from common_lib.modules.project_management.kanban.nodes import update_kanban_board
        mock_board = MagicMock()
        mock_board.id = "board-1"
        mock_board.name = "Updated Board"

        with patch("common_lib.modules.project_management.kanban.service.KanbanService.update_board", return_value=mock_board):
            result = update_kanban_board(board_id="board-1", name="Updated Board")
            assert result["id"] == "board-1"

    def test_delete_kanban_board_success(self, mock_session):
        from common_lib.modules.project_management.kanban.nodes import delete_kanban_board
        with patch("common_lib.modules.project_management.kanban.service.KanbanService.delete_board", return_value=True):
            result = delete_kanban_board(board_id="board-1")
            assert result["success"] is True

    def test_set_kanban_wip_limit_success(self, mock_session):
        from common_lib.modules.project_management.kanban.nodes import set_kanban_wip_limit
        mock_board = MagicMock()
        mock_board.id = "board-1"
        mock_board.wip_limits = {"To Do": 5}

        with patch("common_lib.modules.project_management.kanban.service.KanbanService.set_wip_limit", return_value=mock_board):
            result = set_kanban_wip_limit(board_id="board-1", column_name="To Do", limit=5)
            assert result["id"] == "board-1"
            assert result["wip_limits"]["To Do"] == 5

    def test_get_kanban_wip_status_success(self, mock_session):
        from common_lib.modules.project_management.kanban.nodes import get_kanban_wip_status
        expected = {"board_id": "board-1", "violations": [], "is_over_wip": False}
        with patch("common_lib.modules.project_management.kanban.service.KanbanService.get_wip_status", return_value=expected):
            result = get_kanban_wip_status(board_id="board-1")
            assert result["is_over_wip"] is False

    def test_get_cycle_time_report_success(self, mock_session):
        from common_lib.modules.project_management.kanban.nodes import get_cycle_time_report
        expected = {"project_id": "proj-1", "average_cycle_time": 3.5}
        with patch("common_lib.modules.project_management.kanban.service.KanbanService.get_cycle_time_report", return_value=expected):
            result = get_cycle_time_report(project_id="proj-1", days=30)
            assert result["average_cycle_time"] == 3.5
