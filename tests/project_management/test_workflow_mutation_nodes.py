"""
Tests for the PM workflow/automation mutation @node wrappers.

Covers: create_workflow, update_workflow, delete_workflow,
create_workflow_status, update_workflow_status, delete_workflow_status,
create_workflow_transition, update_workflow_transition,
delete_workflow_transition, validate_workflow, clone_workflow, and
instantiate_automation_template.

Each test verifies the wrapper returns the expected dict shape and
handles errors gracefully.
"""

import pytest
from unittest.mock import MagicMock, patch
from sqlmodel import Session


@pytest.fixture
def mock_session():
    """Create a mock SQLModel Session."""
    return MagicMock(spec=Session)


@pytest.fixture(autouse=True)
def patch_get_session(mock_session):
    """Patch _get_session to return our mock session."""
    with patch(
        "common_lib.modules.project_management.workflows.nodes._get_session",
        return_value=mock_session,
    ):
        yield


def _mock_wf(**overrides):
    wf = MagicMock()
    wf.id = overrides.get("id", "wf-1")
    wf.project_id = overrides.get("project_id", "proj-1")
    wf.name = overrides.get("name", "Default Workflow")
    wf.description = overrides.get("description", None)
    wf.is_default = overrides.get("is_default", True)
    wf.model_dump.return_value = {
        "id": wf.id,
        "project_id": wf.project_id,
        "name": wf.name,
        "description": wf.description,
        "is_default": wf.is_default,
    }
    return wf


def _mock_status(**overrides):
    st = MagicMock()
    st.id = overrides.get("id", "st-1")
    st.workflow_id = overrides.get("workflow_id", "wf-1")
    st.name = overrides.get("name", "To Do")
    st.category = overrides.get("category", "todo")
    st.color = overrides.get("color", "#64748B")
    st.sort_order = overrides.get("sort_order", 0)
    st.model_dump.return_value = {
        "id": st.id,
        "workflow_id": st.workflow_id,
        "name": st.name,
        "category": st.category,
        "color": st.color,
        "sort_order": st.sort_order,
    }
    return st


def _mock_transition(**overrides):
    tr = MagicMock()
    tr.id = overrides.get("id", "tr-1")
    tr.workflow_id = overrides.get("workflow_id", "wf-1")
    tr.name = overrides.get("name", "Start Work")
    tr.from_status_id = overrides.get("from_status_id", "st-1")
    tr.to_status_id = overrides.get("to_status_id", "st-2")
    tr.model_dump.return_value = {
        "id": tr.id,
        "workflow_id": tr.workflow_id,
        "name": tr.name,
        "from_status_id": tr.from_status_id,
        "to_status_id": tr.to_status_id,
    }
    return tr


# ── Workflow CRUD ───────────────────────────────────────────────────────

class TestWorkflowCrudNodes:
    """Test workflow create/update/delete wrappers."""

    def test_create_workflow_success(self, mock_session):
        from common_lib.modules.project_management.workflows.nodes import create_workflow

        with patch(
            "common_lib.modules.project_management.workflows.service.WorkflowService.create_workflow",
            return_value=_mock_wf(),
        ):
            result = create_workflow(project_id="proj-1", name="Default Workflow")
            assert result["success"] is True
            assert result["data"]["id"] == "wf-1"
            assert result["data"]["name"] == "Default Workflow"

    def test_create_workflow_error(self, mock_session):
        from common_lib.modules.project_management.workflows.nodes import create_workflow

        with patch(
            "common_lib.modules.project_management.workflows.service.WorkflowService.create_workflow",
            side_effect=RuntimeError("boom"),
        ):
            result = create_workflow(project_id="proj-1", name="X")
            assert result["success"] is False
            assert "boom" in result["error"]

    def test_update_workflow_success(self, mock_session):
        from common_lib.modules.project_management.workflows.nodes import update_workflow

        with patch(
            "common_lib.modules.project_management.workflows.service.WorkflowService.update_workflow",
            return_value=_mock_wf(name="Renamed"),
        ):
            result = update_workflow(workflow_id="wf-1", name="Renamed")
            assert result["success"] is True
            assert result["data"]["name"] == "Renamed"

    def test_update_workflow_only_changed_fields(self, mock_session):
        """Optional params that are None must not be sent to the service."""
        from common_lib.modules.project_management.workflows.nodes import update_workflow

        with patch(
            "common_lib.modules.project_management.workflows.service.WorkflowService.update_workflow",
            return_value=_mock_wf(),
        ) as mock_update:
            update_workflow(workflow_id="wf-1", name="Renamed")
            _, kwargs = mock_update.call_args
            data = kwargs.get("data") or mock_update.call_args[0][1]
            assert "name" in data
            assert "description" not in data

    def test_delete_workflow_success(self, mock_session):
        from common_lib.modules.project_management.workflows.nodes import delete_workflow

        with patch(
            "common_lib.modules.project_management.workflows.service.WorkflowService.delete_workflow",
            return_value=None,
        ):
            result = delete_workflow(workflow_id="wf-1")
            assert result["success"] is True
            assert result["deleted"] is True


# ── Status CRUD ──────────────────────────────────────────────────────────

class TestWorkflowStatusNodes:
    """Test workflow status create/update/delete wrappers."""

    def test_create_workflow_status_success(self, mock_session):
        from common_lib.modules.project_management.workflows.nodes import create_workflow_status

        with patch(
            "common_lib.modules.project_management.workflows.service.WorkflowService.create_status",
            return_value=_mock_status(),
        ):
            result = create_workflow_status(workflow_id="wf-1", name="To Do")
            assert result["success"] is True
            assert result["data"]["name"] == "To Do"

    def test_update_workflow_status_success(self, mock_session):
        from common_lib.modules.project_management.workflows.nodes import update_workflow_status

        with patch(
            "common_lib.modules.project_management.workflows.service.WorkflowService.update_status",
            return_value=_mock_status(name="In Review", category="in_progress"),
        ):
            result = update_workflow_status(
                status_id="st-1", name="In Review", category="in_progress"
            )
            assert result["success"] is True
            assert result["data"]["name"] == "In Review"

    def test_update_workflow_status_error(self, mock_session):
        from common_lib.modules.project_management.workflows.nodes import update_workflow_status

        with patch(
            "common_lib.modules.project_management.workflows.service.WorkflowService.update_status",
            side_effect=RuntimeError("status gone"),
        ):
            result = update_workflow_status(status_id="missing")
            assert result["success"] is False

    def test_delete_workflow_status_success(self, mock_session):
        from common_lib.modules.project_management.workflows.nodes import delete_workflow_status

        with patch(
            "common_lib.modules.project_management.workflows.service.WorkflowService.delete_status",
            return_value=None,
        ):
            result = delete_workflow_status(status_id="st-1")
            assert result["success"] is True
            assert result["deleted"] is True


# ── Transition CRUD ─────────────────────────────────────────────────────

class TestWorkflowTransitionNodes:
    """Test workflow transition create/update/delete wrappers."""

    def test_create_workflow_transition_success(self, mock_session):
        from common_lib.modules.project_management.workflows.nodes import create_workflow_transition

        with patch(
            "common_lib.modules.project_management.workflows.service.WorkflowService.create_transition",
            return_value=_mock_transition(),
        ):
            result = create_workflow_transition(
                workflow_id="wf-1", name="Start Work",
                from_status_id="st-1", to_status_id="st-2",
            )
            assert result["success"] is True
            assert result["data"]["name"] == "Start Work"

    def test_update_workflow_transition_success(self, mock_session):
        from common_lib.modules.project_management.workflows.nodes import update_workflow_transition

        with patch(
            "common_lib.modules.project_management.workflows.service.WorkflowService.update_transition",
            return_value=_mock_transition(name="Restart Work"),
        ):
            result = update_workflow_transition(transition_id="tr-1", name="Restart Work")
            assert result["success"] is True
            assert result["data"]["name"] == "Restart Work"

    def test_delete_workflow_transition_success(self, mock_session):
        from common_lib.modules.project_management.workflows.nodes import delete_workflow_transition

        with patch(
            "common_lib.modules.project_management.workflows.service.WorkflowService.delete_transition",
            return_value=None,
        ):
            result = delete_workflow_transition(transition_id="tr-1")
            assert result["success"] is True
            assert result["deleted"] is True


# ── Validate / Clone / Automation ───────────────────────────────────────

class TestWorkflowOpsNodes:
    """Test validate, clone, and automation template wrappers."""

    def test_validate_workflow_valid(self, mock_session):
        from common_lib.modules.project_management.workflows.nodes import validate_workflow

        with patch(
            "common_lib.modules.project_management.workflows.service.WorkflowService.validate_workflow",
            return_value={"valid": True, "errors": []},
        ):
            result = validate_workflow(workflow_id="wf-1")
            assert result["success"] is True
            assert result["valid"] is True

    def test_validate_workflow_invalid(self, mock_session):
        from common_lib.modules.project_management.workflows.nodes import validate_workflow

        with patch(
            "common_lib.modules.project_management.workflows.service.WorkflowService.validate_workflow",
            return_value={"valid": False, "errors": ["Workflow has no statuses"]},
        ):
            result = validate_workflow(workflow_id="wf-1")
            assert result["success"] is True
            assert result["valid"] is False
            assert "no statuses" in result["errors"][0]

    def test_clone_workflow_success(self, mock_session):
        from common_lib.modules.project_management.workflows.nodes import clone_workflow

        with patch(
            "common_lib.modules.project_management.workflows.service.WorkflowService.clone_workflow",
            return_value=_mock_wf(id="wf-2", name="Copy of Default Workflow"),
        ):
            result = clone_workflow(workflow_id="wf-1", new_project_id="proj-2")
            assert result["success"] is True
            assert result["data"]["id"] == "wf-2"

    def test_instantiate_automation_template_success(self, mock_session):
        import uuid

        import common_lib.modules.project_management.workflows.nodes as wf_nodes
        from common_lib.modules.project_management.workflows.nodes import (
            instantiate_automation_template,
        )

        source = MagicMock(
            name="Auto-transition", description=None, category="custom",
            is_global=True, trigger_type="issue_created", trigger_config=None,
            condition_config=None, actions={"action": "transition"},
            parameters_schema={"param": "x"}, tags={}, icon=None, color="#6366F1",
            created_by="user", use_count=0,
        )
        mock_session.get.return_value = source
        mock_session.add = MagicMock()
        mock_session.commit = MagicMock()

        mock_copy = MagicMock()
        mock_copy.id = "t-copy-1"
        mock_copy.name = "Auto-transition (proj-2)"
        mock_copy.project_id = "proj-2"
        mock_copy.model_dump.return_value = {
            "id": "t-copy-1",
            "name": "Auto-transition (proj-2)",
            "project_id": "proj-2",
        }
        mock_session.refresh = MagicMock()

        with patch.object(uuid, "uuid4", return_value="t-copy-1"):
            with patch.object(
                wf_nodes, "_automation_model", return_value=MagicMock(return_value=mock_copy)
            ):
                result = instantiate_automation_template(
                    template_id="t-1", project_id="proj-2"
                )
            assert result["success"] is True
            assert result["data"]["id"] == "t-copy-1"
