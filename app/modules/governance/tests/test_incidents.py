from __future__ import annotations

from fastapi.testclient import TestClient

PREFIX = "/api/v1/governance/incidents"


class TestIncidentCreate:
    def test_01_create_incident(self, client: TestClient) -> None:
        resp = client.post(
            PREFIX,
            json={
                "incident_type": "security_breach",
                "severity": "high",
                "agent_id": "agent-001",
                "description": "Unauthorized access detected",
            },
        )
        assert resp.status_code == 200
        d = resp.json()
        assert d["agent_id"] == "agent-001"
        assert d["severity"] == "high"
        assert d["status"] == "open"

    def test_02_create_another(self, client: TestClient) -> None:
        resp = client.post(
            PREFIX,
            json={
                "incident_type": "policy_violation",
                "severity": "medium",
                "agent_id": "agent-002",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["incident_type"] == "policy_violation"


class TestIncidentList:
    def test_03_list_incidents(self, client: TestClient) -> None:
        resp = client.get(PREFIX)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 2

    def test_04_list_contains_all(self, client: TestClient) -> None:
        resp = client.get(PREFIX)
        agents = [i["agent_id"] for i in resp.json()]
        assert "agent-001" in agents
        assert "agent-002" in agents


class TestIncidentStatusTransition:
    def test_05_contain_incident(self, client: TestClient) -> None:
        resp = client.get(PREFIX)
        incident_id = resp.json()[0]["incident_id"]

        resp = client.post(f"{PREFIX}/{incident_id}/contain")
        assert resp.status_code == 200
        assert resp.json()["status"] == "contained"

    def test_06_remediate_incident(self, client: TestClient) -> None:
        resp = client.get(PREFIX)
        incident_id = resp.json()[0]["incident_id"]

        resp = client.post(f"{PREFIX}/{incident_id}/remediated")
        assert resp.status_code == 200
        assert resp.json()["status"] == "remediated"
        assert resp.json()["remediated_at"] is not None

    def test_07_close_incident(self, client: TestClient) -> None:
        resp = client.get(PREFIX)
        incident_id = resp.json()[1]["incident_id"]

        resp = client.post(f"{PREFIX}/{incident_id}/closed")
        assert resp.status_code == 200
        assert resp.json()["status"] == "closed"

    def test_08_update_nonexistent_incident(self, client: TestClient) -> None:
        resp = client.post(f"{PREFIX}/99999/closed")
        assert resp.status_code == 404
