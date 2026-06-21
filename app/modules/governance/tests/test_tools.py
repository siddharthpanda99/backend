from __future__ import annotations

from fastapi.testclient import TestClient

PREFIX = "/api/v1/governance/tools"


class TestToolList:
    def test_01_list_empty(self, client: TestClient) -> None:
        resp = client.get(PREFIX)
        assert resp.status_code == 200
        assert resp.json() == []


class TestToolCreate:
    def test_02_create_tool(self, client: TestClient) -> None:
        resp = client.post(
            PREFIX,
            json={
                "tool_id": "email-sender",
                "name": "Email Sender",
                "description": "Sends email notifications",
                "risk_level": "low",
                "category": "communication",
            },
        )
        assert resp.status_code == 200
        d = resp.json()
        assert d["tool_id"] == "email-sender"
        assert d["enabled"] is True

    def test_03_create_another_tool(self, client: TestClient) -> None:
        resp = client.post(
            PREFIX,
            json={
                "tool_id": "data-exporter",
                "name": "Data Exporter",
                "risk_level": "high",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["risk_level"] == "high"


class TestToolRead:
    def test_04_get_existing_tool(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/email-sender")
        assert resp.status_code == 200
        assert resp.json()["tool_id"] == "email-sender"

    def test_05_get_nonexistent_tool(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/nonexistent-tool")
        assert resp.status_code == 404

    def test_06_list_tools(self, client: TestClient) -> None:
        resp = client.get(PREFIX)
        tool_ids = [t["tool_id"] for t in resp.json()]
        assert "email-sender" in tool_ids
        assert "data-exporter" in tool_ids


class TestToolUpdate:
    def test_07_update_tool(self, client: TestClient) -> None:
        resp = client.put(
            f"{PREFIX}/email-sender",
            json={"name": "Email Sender v2", "risk_level": "medium"},
        )
        assert resp.status_code == 200
        d = resp.json()
        assert d["name"] == "Email Sender v2"
        assert d["risk_level"] == "medium"

    def test_08_update_nonexistent(self, client: TestClient) -> None:
        resp = client.put(
            f"{PREFIX}/nonexistent",
            json={"name": "Ghost"},
        )
        assert resp.status_code == 404


class TestToolValidate:
    def test_09_validate_tool(self, client: TestClient) -> None:
        resp = client.post(
            f"{PREFIX}/email-sender/validate",
            json={"agent_id": "test-agent"},
        )
        assert resp.status_code == 200
        assert resp.json()["valid"] is True

    def test_10_validate_nonexistent(self, client: TestClient) -> None:
        resp = client.post(
            f"{PREFIX}/nonexistent/validate",
            json={"agent_id": "test"},
        )
        assert resp.status_code == 404

    def test_11_get_tool_risk(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/email-sender/risk")
        assert resp.status_code == 200
        assert resp.json()["risk_level"] == "medium"
