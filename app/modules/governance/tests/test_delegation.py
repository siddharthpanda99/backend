from __future__ import annotations

from fastapi.testclient import TestClient

PREFIX = "/api/v1/governance/delegations"


class TestDelegationCreate:
    def test_01_create_delegation(self, client: TestClient) -> None:
        resp = client.post(
            PREFIX,
            json={
                "delegation_id": "del-001",
                "delegating_agent": "agent-admin",
                "delegatee_agent": "agent-user",
                "task_id": "data-access",
                "permissions_granted": ["read"],
            },
        )
        assert resp.status_code == 200
        d = resp.json()
        assert d["delegating_agent"] == "agent-admin"
        assert d["delegatee_agent"] == "agent-user"
        assert d["revoked"] is False

    def test_02_create_another(self, client: TestClient) -> None:
        resp = client.post(
            PREFIX,
            json={
                "delegation_id": "del-002",
                "delegating_agent": "agent-lead",
                "delegatee_agent": "agent-dev",
                "task_id": "deploy",
            },
        )
        assert resp.status_code == 200


class TestDelegationList:
    def test_03_list_delegations(self, client: TestClient) -> None:
        resp = client.get(PREFIX)
        assert resp.status_code == 200
        assert len(resp.json()) >= 2

    def test_04_list_contains_all(self, client: TestClient) -> None:
        resp = client.get(PREFIX)
        delegators = [d["delegating_agent"] for d in resp.json()]
        assert "agent-admin" in delegators
        assert "agent-lead" in delegators


class TestDelegationRevoke:
    def test_05_revoke_delegation(self, client: TestClient) -> None:
        resp = client.get(PREFIX)
        del_id = resp.json()[0]["delegation_id"]

        resp = client.post(f"{PREFIX}/{del_id}/revoke")
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_06_revoke_nonexistent(self, client: TestClient) -> None:
        resp = client.post(f"{PREFIX}/99999/revoke")
        assert resp.status_code == 404


class TestDelegationCheck:
    def test_07_check_active_delegation(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/check?agent_id=agent-dev&task_id=deploy")
        assert resp.status_code == 200
        assert resp.json()["active"] is True

    def test_08_check_revoked_delegation(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/check?agent_id=agent-user&task_id=data-access")
        assert resp.status_code == 200
        assert resp.json()["active"] is False

    def test_09_check_nonexistent(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/check?agent_id=ghost&task_id=nonexistent")
        assert resp.status_code == 200
        assert resp.json()["active"] is False
