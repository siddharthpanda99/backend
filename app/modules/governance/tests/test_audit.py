from __future__ import annotations

from fastapi.testclient import TestClient

PREFIX = "/api/v1/governance/audit"


class TestAuditEventCreate:
    def test_01_create_minimal_event(self, client: TestClient) -> None:
        resp = client.post(
            f"{PREFIX}/events",
            json={
                "action": "test.action",
                "agent_id": "test-agent",
            },
        )
        assert resp.status_code == 200

    def test_02_create_full_event(self, client: TestClient) -> None:
        resp = client.post(
            f"{PREFIX}/events",
            json={
                "action": "document.create",
                "agent_id": "admin-agent",
                "resource": {"type": "document", "id": "doc-001"},
                "outcome": {"status": "allowed"},
                "authz_decision": {"decision": "permit"},
                "event_type": "api",
                "severity": "medium",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["action"] == "document.create"

    def test_03_create_denied_event(self, client: TestClient) -> None:
        resp = client.post(
            f"{PREFIX}/events",
            json={
                "action": "document.delete",
                "agent_id": "unauthorized-agent",
                "outcome": {"status": "denied"},
                "severity": "high",
            },
        )
        assert resp.status_code == 200


class TestAuditEventRead:
    def test_04_list_all_events(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/events")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 3

    def test_05_list_ordered_by_date(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/events")
        events = resp.json()
        timestamps = [e["created_at"] for e in events if e.get("created_at")]
        assert timestamps == sorted(timestamps, reverse=True)

    def test_06_list_contains_created_events(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/events")
        actions = [e["action"] for e in resp.json()]
        assert "test.action" in actions
        assert "document.create" in actions
        assert "document.delete" in actions


class TestAuditEventDelete:
    def test_07_clear_all_events(self, client: TestClient) -> None:
        resp = client.delete(f"{PREFIX}/events")
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_08_list_empty_after_clear(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/events")
        assert resp.json() == []
