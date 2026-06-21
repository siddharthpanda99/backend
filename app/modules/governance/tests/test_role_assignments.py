from __future__ import annotations

from fastapi.testclient import TestClient

PREFIX = "/api/v1/governance/role-assignments"


class TestAssignmentCreate:
    def test_01_create_assignment(self, client: TestClient) -> None:
        resp = client.post(
            PREFIX,
            json={
                "principal_type": "agent",
                "principal_id": "agent-alpha",
                "role": "editor",
                "granted_by": "admin-user",
            },
        )
        assert resp.status_code == 200
        d = resp.json()
        assert d["principal_id"] == "agent-alpha"
        assert d["role"] == "editor"
        assert d["principal_type"] == "agent"

    def test_02_create_second_assignment(self, client: TestClient) -> None:
        resp = client.post(
            PREFIX,
            json={
                "principal_id": "agent-beta",
                "role": "viewer",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["role"] == "viewer"

    def test_03_create_assignment_with_expiry(self, client: TestClient) -> None:
        resp = client.post(
            PREFIX,
            json={
                "principal_id": "agent-gamma",
                "role": "temp-access",
                "granted_by": "admin",
                "expires_at": "2026-12-31T23:59:59",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["expires_at"] is not None


class TestAssignmentList:
    def test_04_list_assignments(self, client: TestClient) -> None:
        resp = client.get(PREFIX)
        assert resp.status_code == 200
        assert len(resp.json()) >= 3

    def test_05_list_contains_all(self, client: TestClient) -> None:
        resp = client.get(PREFIX)
        principals = [a["principal_id"] for a in resp.json()]
        assert "agent-alpha" in principals
        assert "agent-beta" in principals
        assert "agent-gamma" in principals


class TestAgentRoles:
    def test_06_get_agent_roles(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/agent/agent-alpha")
        assert resp.status_code == 200
        d = resp.json()
        assert d["agent_id"] == "agent-alpha"
        assert "editor" in d["roles"]

    def test_07_get_agent_no_roles(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/agent/unknown-agent")
        assert resp.status_code == 200
        assert resp.json()["roles"] == []


class TestAssignmentRevoke:
    def test_08_revoke_assignment(self, client: TestClient) -> None:
        resp = client.get(PREFIX)
        data = resp.json()
        alpha_assignments = [a for a in data if a["principal_id"] == "agent-alpha"]
        assign_id = alpha_assignments[0]["id"]

        resp = client.delete(f"{PREFIX}/{assign_id}")
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_09_revoke_nonexistent(self, client: TestClient) -> None:
        resp = client.delete(f"{PREFIX}/99999")
        assert resp.status_code == 404

    def test_10_verify_removed_from_roles(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/agent/agent-alpha")
        assert "editor" not in resp.json()["roles"]
