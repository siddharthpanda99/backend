from __future__ import annotations

from fastapi.testclient import TestClient

PREFIX = "/api/v1/governance/workflows"


class TestWorkflowList:
    def test_01_list_empty(self, client: TestClient) -> None:
        resp = client.get(PREFIX)
        assert resp.status_code == 200
        assert resp.json() == []


class TestWorkflowCreate:
    def test_02_create_workflow(self, client: TestClient) -> None:
        resp = client.post(
            PREFIX,
            json={
                "workflow_id": "wf-001",
                "name": "Data Export",
                "version": "1.0.0",
                "owner": "team-a",
                "department": "engineering",
                "risk_level": "high",
                "status": "draft",
                "steps": [
                    {"id": "step-1", "name": "Validate", "type": "validation"},
                    {"id": "step-2", "name": "Export", "type": "action"},
                ],
            },
        )
        assert resp.status_code == 200
        d = resp.json()
        assert d["workflow_id"] == "wf-001"
        assert d["name"] == "Data Export"

    def test_03_create_duplicate(self, client: TestClient) -> None:
        resp = client.post(
            PREFIX,
            json={"workflow_id": "wf-001", "name": "Duplicate"},
        )
        assert resp.status_code == 409

    def test_04_create_another(self, client: TestClient) -> None:
        resp = client.post(
            PREFIX,
            json={"workflow_id": "wf-002", "name": "Report Gen"},
        )
        assert resp.status_code == 200


class TestWorkflowRead:
    def test_05_get_workflow(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/wf-001")
        assert resp.status_code == 200
        assert resp.json()["workflow_id"] == "wf-001"

    def test_06_get_nonexistent(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/nonexistent")
        assert resp.status_code == 404

    def test_07_list_all(self, client: TestClient) -> None:
        resp = client.get(PREFIX)
        ids = [w["workflow_id"] for w in resp.json()]
        assert "wf-001" in ids
        assert "wf-002" in ids


class TestWorkflowValidate:
    def test_08_validate_workflow(self, client: TestClient) -> None:
        resp = client.post(f"{PREFIX}/wf-001/validate")
        assert resp.status_code == 200
        d = resp.json()
        assert d["valid"] is True
        assert d["step_count"] == 2

    def test_09_validate_nonexistent(self, client: TestClient) -> None:
        resp = client.post(f"{PREFIX}/nonexistent/validate")
        assert resp.status_code == 404

    def test_10_validate_empty_steps(self, client: TestClient) -> None:
        resp = client.post(f"{PREFIX}/wf-002/validate")
        assert resp.status_code == 200
        assert resp.json()["valid"] is False


class TestWorkflowTransition:
    def test_11_validate_transition_valid(self, client: TestClient) -> None:
        resp = client.post(
            f"{PREFIX}/wf-001/transition",
            json={"from_step": "step-1", "to_step": "step-2"},
        )
        assert resp.status_code == 200
        d = resp.json()
        assert d["valid"] is True
        assert d["from_step_valid"] is True
        assert d["to_step_valid"] is True

    def test_12_validate_transition_invalid(self, client: TestClient) -> None:
        resp = client.post(
            f"{PREFIX}/wf-001/transition",
            json={"from_step": "step-x", "to_step": "step-y"},
        )
        assert resp.status_code == 200
        assert resp.json()["valid"] is False

    def test_13_validate_transition_nonexistent(self, client: TestClient) -> None:
        resp = client.post(
            f"{PREFIX}/nonexistent/transition",
            json={"from_step": "a", "to_step": "b"},
        )
        assert resp.status_code == 404


class TestWorkflowLineage:
    def test_14_start_lineage(self, client: TestClient) -> None:
        resp = client.post(
            f"{PREFIX}/lineage",
            json={
                "workflow_execution_id": "exec-001",
                "workflow_id": "wf-001",
                "version": "1.0.0",
                "initiated_by": "agent-001",
            },
        )
        assert resp.status_code == 200
        d = resp.json()
        assert d["workflow_execution_id"] == "exec-001"
        assert d["status"] == "running"

    def test_15_start_duplicate_lineage(self, client: TestClient) -> None:
        resp = client.post(
            f"{PREFIX}/lineage",
            json={
                "workflow_execution_id": "exec-001",
                "workflow_id": "wf-001",
            },
        )
        assert resp.status_code == 409

    def test_16_record_step(self, client: TestClient) -> None:
        resp = client.post(
            f"{PREFIX}/lineage/step",
            json={
                "execution_id": "exec-001",
                "step": {"id": "step-1", "status": "completed", "duration_ms": 1200},
            },
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_17_record_step_nonexistent(self, client: TestClient) -> None:
        resp = client.post(
            f"{PREFIX}/lineage/step",
            json={"execution_id": "exec-x", "step": {}},
        )
        assert resp.status_code == 404

    def test_18_get_lineage(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/lineage/exec-001")
        assert resp.status_code == 200
        d = resp.json()
        assert d["workflow_execution_id"] == "exec-001"
        assert len(d["steps"]) == 1

    def test_19_get_lineage_nonexistent(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/lineage/exec-x")
        assert resp.status_code == 404

    def test_20_complete_lineage(self, client: TestClient) -> None:
        resp = client.post(f"{PREFIX}/lineage/exec-001/complete")
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_21_complete_lineage_verify_status(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/lineage/exec-001")
        assert resp.json()["status"] == "completed"

    def test_22_complete_lineage_nonexistent(self, client: TestClient) -> None:
        resp = client.post(f"{PREFIX}/lineage/exec-x/complete")
        assert resp.status_code == 404
