from __future__ import annotations

from fastapi.testclient import TestClient

PREFIX = "/api/v1/governance/identity"


class TestIdentityCreate:
    def test_01_create_minimal(self, client: TestClient) -> None:
        resp = client.post(
            PREFIX,
            json={"agent_id": "test-agent-001", "name": "Test Agent 1"},
        )
        assert resp.status_code == 200
        d = resp.json()
        assert d["agent_id"] == "test-agent-001"
        assert d["display_name"] == "Test Agent 1"
        assert d["status"] == "inactive"

    def test_02_create_full(self, client: TestClient) -> None:
        resp = client.post(
            PREFIX,
            json={
                "agent_id": "test-agent-002",
                "name": "Full Agent",
                "owner": "admin",
                "department": "engineering",
                "agent_type": "admin",
                "status": "active",
                "capabilities": ["read", "write"],
                "compliance_tags": ["pci"],
            },
        )
        assert resp.status_code == 200
        d = resp.json()
        assert d["agent_id"] == "test-agent-002"
        assert d["display_name"] == "Full Agent"
        assert d["status"] == "active"
        assert d["capabilities"] == ["read", "write"]

    def test_03_create_duplicate(self, client: TestClient) -> None:
        resp = client.post(
            PREFIX,
            json={"agent_id": "test-agent-001", "name": "Duplicate"},
        )
        assert resp.status_code == 409

    def test_04_create_without_capabilities(self, client: TestClient) -> None:
        resp = client.post(
            PREFIX,
            json={"agent_id": "test-agent-003", "name": "No Caps"},
        )
        assert resp.status_code == 200
        assert resp.json()["capabilities"] == []


class TestIdentityRead:
    def test_05_get_existing(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/test-agent-001")
        assert resp.status_code == 200
        d = resp.json()
        assert d["agent_id"] == "test-agent-001"

    def test_06_get_non_existent(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/nonexistent-agent")
        assert resp.status_code == 404

    def test_07_list_identities(self, client: TestClient) -> None:
        resp = client.get(PREFIX)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 3

    def test_08_list_contains_seeded(self, client: TestClient) -> None:
        resp = client.get(PREFIX)
        agent_ids = [i["agent_id"] for i in resp.json()]
        assert "test-agent-001" in agent_ids
        assert "test-agent-002" in agent_ids
        assert "test-agent-003" in agent_ids


class TestIdentityUpdate:
    def test_09_update_name(self, client: TestClient) -> None:
        resp = client.put(
            f"{PREFIX}/test-agent-001",
            json={"name": "Updated Agent 1"},
        )
        assert resp.status_code == 200
        assert resp.json()["display_name"] == "Updated Agent 1"

    def test_10_update_status(self, client: TestClient) -> None:
        resp = client.put(
            f"{PREFIX}/test-agent-001",
            json={"status": "active"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "active"

    def test_11_update_capabilities(self, client: TestClient) -> None:
        resp = client.put(
            f"{PREFIX}/test-agent-001",
            json={"capabilities": ["admin", "audit"]},
        )
        assert resp.status_code == 200
        assert resp.json()["capabilities"] == ["admin", "audit"]

    def test_12_update_non_existent(self, client: TestClient) -> None:
        resp = client.put(
            f"{PREFIX}/nonexistent-agent",
            json={"name": "No One"},
        )
        assert resp.status_code == 404


class TestIdentityTransition:
    def test_13_transition_to_active(self, client: TestClient) -> None:
        resp = client.post(
            f"{PREFIX}/test-agent-003/transition",
            json={"status": "active"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "active"

    def test_14_transition_to_inactive(self, client: TestClient) -> None:
        resp = client.post(
            f"{PREFIX}/test-agent-003/transition",
            json={"status": "inactive"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "inactive"

    def test_15_transition_non_existent(self, client: TestClient) -> None:
        resp = client.post(
            f"{PREFIX}/nonexistent-agent/transition",
            json={"status": "active"},
        )
        assert resp.status_code == 404


class TestIdentityDelete:
    def test_16_delete_existing(self, client: TestClient) -> None:
        resp = client.delete(f"{PREFIX}/test-agent-003")
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_17_get_deleted(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/test-agent-003")
        assert resp.status_code == 404

    def test_18_delete_non_existent(self, client: TestClient) -> None:
        resp = client.delete(f"{PREFIX}/nonexistent-agent")
        assert resp.status_code == 404
