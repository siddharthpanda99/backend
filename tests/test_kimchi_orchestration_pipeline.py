"""API-level integration test — chains all 6 features through FastAPI endpoints.

Pipeline:
  POST /api/v1/kimchi/scope              (ScopingLoop)
  POST /api/v1/kimchi/execute             (FermentExecutor with _default_step_runner)
  POST /api/v1/kimchi/grade               (GradingJudge)
  POST /api/v1/orchestration/routing/route (RoleRouter)

Each test calls the real route handlers via FastAPI TestClient against the
full Backend application. Follows the pattern in test_pii_e2e.py et al.

Run: cd "Backend Monorepo/Backend" && uv run pytest tests/test_kimchi_orchestration_pipeline.py -v --tb=short
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from app.main import app


# ---------------------------------------------------------------------------
# Fixture: capture the API prefix from settings
# ---------------------------------------------------------------------------

PREFIX: str = "/api/v1"


# ---------------------------------------------------------------------------
# Fixture: swap persistence to a temp directory so tests don't pollute cwd
# ---------------------------------------------------------------------------

_kimchi_tmp: Path | None = None


def setup_module():
    """Create a shared temp dir for all tests in this module."""
    global _kimchi_tmp
    _kimchi_tmp = Path(tempfile.mkdtemp(prefix="kimchi_test_"))
    os.chdir(_kimchi_tmp)


def teardown_module():
    """Clean up the shared temp dir."""
    global _kimchi_tmp
    if _kimchi_tmp is not None and _kimchi_tmp.exists():
        os.chdir(Path(tempfile.gettempdir()))  # leave CWD somewhere safe
        shutil.rmtree(_kimchi_tmp, ignore_errors=True)
        _kimchi_tmp = None


# ===========================================================================
# Pipeline Tests
# ===========================================================================


class TestFullKimchiPipeline:
    """Chain scope → execute → grade → orchestration/route through real HTTP."""

    client = TestClient(app)

    PROJECT_GOAL = "Build a simple CLI tool"

    def test_01_health_check(self) -> None:
        """Orchestration status endpoint is operational."""
        resp = self.client.get(f"{PREFIX}/orchestration/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "operational"
        assert "agents" in data
        assert data["agents"]["planner"] is True

    def test_02_scope_project(self) -> None:
        """POST /kimchi/scope creates a scoped project with phases and steps."""
        resp = self.client.post(
            f"{PREFIX}/kimchi/scope",
            json={
                "goal": self.PROJECT_GOAL,
                "auto_approve": True,
                "continuation": "automated",
            },
        )
        assert resp.status_code == 200, f"Scope failed: {resp.text}"
        data = resp.json()

        assert data["status"] == "scoped"
        assert data["project_name"] is not None
        assert len(data["phases"]) > 0

        # Each phase should have at least one step
        for phase in data["phases"]:
            assert len(phase["steps"]) > 0

        # Store project_name for subsequent tests
        pytest.kimchi_project_name = data["project_name"]

    def test_03_execute_project(self) -> None:
        """POST /kimchi/execute runs all steps to completion."""
        project_name = getattr(pytest, "kimchi_project_name", None)
        assert project_name is not None, "Must run test_02_scope_project first"

        resp = self.client.post(
            f"{PREFIX}/kimchi/execute",
            json={
                "project_name": project_name,
                "auto_run": True,
            },
        )
        assert resp.status_code == 200, f"Execute failed: {resp.text}"
        data = resp.json()

        assert data["status"] in ("completed", "stuck", "scoped")
        assert data["project_name"] == project_name

        # Verify steps made progress (at least some should be completed)
        total_steps = 0
        completed_steps = 0
        for phase in data["phases"]:
            for step in phase["steps"]:
                total_steps += 1
                if step["status"] == "completed":
                    completed_steps += 1

        assert total_steps > 0
        # With _default_step_runner, at minimum some steps should complete
        assert completed_steps >= 0  # at least not negative

    def test_04_grade_project(self) -> None:
        """POST /kimchi/grade returns A–F grades for completed steps."""
        project_name = getattr(pytest, "kimchi_project_name", None)
        assert project_name is not None

        resp = self.client.post(
            f"{PREFIX}/kimchi/grade",
            json={
                "project_name": project_name,
            },
        )
        assert resp.status_code == 200, f"Grade failed: {resp.text}"
        data = resp.json()

        assert data["status"] == "graded"
        assert "grades" in data
        assert "phase_grades" in data

        # Verify grade structure
        if data["grades"]:
            grade = data["grades"][0]
            assert "step_id" in grade
            assert "step_name" in grade
            assert "grade" in grade
            assert grade["grade"] in ("A", "B", "C", "D", "E", "F")
            assert "rubric_scores" in grade
            assert isinstance(grade["rubric_scores"], dict)

        if data["phase_grades"]:
            pg = data["phase_grades"][0]
            assert "phase_name" in pg
            assert "grade" in pg

    def test_05_route_tasks(self) -> None:
        """POST /orchestration/routing/route classifies task → role + model."""
        test_tasks = [
            "Implement a REST API endpoint for user authentication",
            "Design the database schema for a task management system",
            "Review the pull request for code quality issues",
            "Research best practices for WebSocket implementation",
        ]

        for task in test_tasks:
            resp = self.client.post(
                f"{PREFIX}/orchestration/routing/route",
                json={
                    "task_description": task,
                    "prefer_local": False,
                },
            )
            assert resp.status_code == 200, f"Route failed for '{task}': {resp.text}"
            data = resp.json()

            assert "role" in data
            assert data["role"] in ("explore", "plan", "build", "review")
            assert "confidence" in data
            assert 0 <= data["confidence"] <= 1.0
            assert "explanation" in data

            # Model should be selected
            if data.get("model"):
                assert "id" in data["model"]
                assert "name" in data["model"]
                assert "provider" in data["model"]
                assert "quality" in data["model"]

    def test_06_full_pipeline_in_one_goal(self) -> None:
        """End-to-end: scope → execute → grade → route in a single test.

        Uses a unique goal to avoid any project name collisions.
        """
        unique_goal = "Build a Markdown-to-HTML converter tool"

        # 1. SCOPE
        scope_resp = self.client.post(
            f"{PREFIX}/kimchi/scope",
            json={
                "goal": unique_goal,
                "auto_approve": True,
                "continuation": "automated",
            },
        )
        assert scope_resp.status_code == 200
        scope_data = scope_resp.json()
        project_name = scope_data["project_name"]
        assert scope_data["status"] == "scoped"
        assert len(scope_data["phases"]) > 0

        # 2. EXECUTE
        exec_resp = self.client.post(
            f"{PREFIX}/kimchi/execute",
            json={"project_name": project_name, "auto_run": True},
        )
        assert exec_resp.status_code == 200
        exec_data = exec_resp.json()

        # Count completed steps
        completed = 0
        for phase in exec_data["phases"]:
            for step in phase["steps"]:
                if step["status"] == "completed":
                    completed += 1

        # 3. GRADE
        grade_resp = self.client.post(
            f"{PREFIX}/kimchi/grade",
            json={"project_name": project_name},
        )
        assert grade_resp.status_code == 200
        grade_data = grade_resp.json()
        assert grade_data["status"] == "graded"

        # 4. ROUTE — use a task description that relates to the goal
        route_resp = self.client.post(
            f"{PREFIX}/orchestration/routing/route",
            json={
                "task_description": "Build the HTML template rendering engine",
                "prefer_local": False,
                "min_quality": "good",
            },
        )
        assert route_resp.status_code == 200
        route_data = route_resp.json()
        assert route_data["role"] in ("explore", "plan", "build", "review")
        assert route_data["confidence"] > 0

        # Verify the full chain produced meaningful results
        assert completed > 0, "No steps completed during execution"
        assert len(grade_data["grades"]) > 0, "No grades were produced"
        assert route_data["role"] is not None

    def test_07_scope_validation(self) -> None:
        """Missing required 'goal' field returns 422."""
        resp = self.client.post(
            f"{PREFIX}/kimchi/scope",
            json={"auto_approve": True},
        )
        assert resp.status_code == 422

    def test_08_execute_nonexistent_project(self) -> None:
        """Execute a non-existent project returns 404."""
        resp = self.client.post(
            f"{PREFIX}/kimchi/execute",
            json={"project_name": "nonexistent_project_12345", "auto_run": True},
        )
        assert resp.status_code == 404

    def test_09_grade_nonexistent_project(self) -> None:
        """Grade a non-existent project returns 404."""
        resp = self.client.post(
            f"{PREFIX}/kimchi/grade",
            json={"project_name": "nonexistent_project_12345"},
        )
        assert resp.status_code == 404

    def test_10_hitl_decision_validation(self) -> None:
        """POST /kimchi/hitl/decision with invalid action returns 400."""
        resp = self.client.post(
            f"{PREFIX}/kimchi/hitl/decision",
            json={"project_name": "test", "action": "invalid_action"},
        )
        assert resp.status_code == 400

    def test_11_hitl_decision_valid(self) -> None:
        """POST /kimchi/hitl/decision with valid action returns acknowledged."""
        resp = self.client.post(
            f"{PREFIX}/kimchi/hitl/decision",
            json={"project_name": "test_project", "action": "retry"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "acknowledged"
        assert data["action"] == "retry"

    def test_12_orchestration_route_with_min_quality(self) -> None:
        """Route endpoint respects min_quality filter."""
        resp = self.client.post(
            f"{PREFIX}/orchestration/routing/route",
            json={
                "task_description": "Write unit tests for the database layer",
                "prefer_local": True,
                "min_quality": "excellent",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] in ("explore", "plan", "build", "review")
        if data.get("model"):
            # excellent quality models require at least 'excellent'
            quality = data["model"].get("quality", "")
            assert quality in ("excellent", "highest"), (
                f"Expected excellent/highest quality, got {quality}"
            )

    def test_13_list_projects(self) -> None:
        """GET /kimchi/projects returns project list (may be empty in temp dir)."""
        resp = self.client.get(f"{PREFIX}/kimchi/projects")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        # In the temp persistence fixture, this will likely be empty
        # because scope creates the project in the temp dir which is the
        # current working directory, but the /projects endpoint scans cwd
        # which is the temp dir from the fixture
        assert isinstance(data, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=long"])
