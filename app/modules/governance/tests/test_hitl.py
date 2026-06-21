from __future__ import annotations

from fastapi.testclient import TestClient

PREFIX = "/api/v1/governance/hitl"


class TestRequestCRUD:
    def test_01_list_empty(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/requests")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_02_create_request(self, client: TestClient) -> None:
        resp = client.post(
            f"{PREFIX}/requests",
            json={
                "approval_policy_id": "policy-1",
                "agent_id": "agent-001",
                "action": "execute",
                "tool": "data-exporter",
                "risk_score": 85,
                "justification": "Need to export sensitive data",
                "route_to": "vp-approver",
                "source": "manual",
                "session_id": "sess-123",
                "trace_id": "trace-abc",
                "tool_input": {"format": "csv", "include_all": True},
            },
        )
        assert resp.status_code == 200
        d = resp.json()
        assert d["status"] == "pending"
        assert d["agent_id"] == "agent-001"
        assert d["risk_score"] == 85
        assert d["id"] != ""

    def test_03_create_another_request(self, client: TestClient) -> None:
        resp = client.post(
            f"{PREFIX}/requests",
            json={
                "agent_id": "agent-002",
                "action": "delete",
                "tool": "file-manager",
                "risk_score": 95,
            },
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "pending"

    def test_04_list_requests(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/requests")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    def test_05_get_request(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/requests")
        req_id = resp.json()[0]["id"]
        resp = client.get(f"{PREFIX}/requests/{req_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == req_id

    def test_06_get_nonexistent_request(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/requests/nonexistent-id")
        assert resp.status_code == 404


class TestRequestStateMachine:
    def test_07_approve_request(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/requests")
        req_id = resp.json()[0]["id"]
        resp = client.post(
            f"{PREFIX}/requests/{req_id}/approve",
            json={"decided_by": "admin", "notes": "Approved by VP"},
        )
        assert resp.status_code == 200
        d = resp.json()
        assert d["status"] == "approved"
        assert d["decided_by"] == "admin"

    def test_08_approve_already_decided(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/requests")
        req_id = resp.json()[0]["id"]
        resp = client.post(
            f"{PREFIX}/requests/{req_id}/approve",
            json={"decided_by": "admin", "notes": ""},
        )
        assert resp.status_code == 409

    def test_09_deny_request(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/requests")
        items = resp.json()
        pending = [i for i in items if i["status"] == "pending"]
        assert len(pending) >= 1
        req_id = pending[0]["id"]
        resp = client.post(
            f"{PREFIX}/requests/{req_id}/deny",
            json={"decided_by": "compliance", "notes": "Violates policy"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "denied"

    def test_10_modify_request(self, client: TestClient) -> None:
        resp = client.post(
            f"{PREFIX}/requests",
            json={"agent_id": "agent-003", "tool_input": {"original": True}},
        )
        req_id = resp.json()["id"]
        resp = client.post(
            f"{PREFIX}/requests/{req_id}/modify",
            json={
                "decided_by": "reviewer",
                "tool_input": {"modified": True, "safe": True},
                "notes": "Sanitized input",
            },
        )
        assert resp.status_code == 200
        d = resp.json()
        assert d["status"] == "modified"
        assert d["modified_tool_input"]["modified"] is True

    def test_11_execute_approved_request(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/requests")
        items = resp.json()
        approved = [i for i in items if i["status"] == "approved"]
        assert len(approved) >= 1
        req_id = approved[0]["id"]
        resp = client.post(
            f"{PREFIX}/requests/{req_id}/execute",
            json={"outcome": "Completed successfully"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "executed"

    def test_12_execute_not_approved(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/requests")
        items = resp.json()
        denied = [i for i in items if i["status"] == "denied"]
        assert len(denied) >= 1
        req_id = denied[0]["id"]
        resp = client.post(
            f"{PREFIX}/requests/{req_id}/execute",
            json={"outcome": "Should fail"},
        )
        assert resp.status_code == 409

    def test_13_add_feedback(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/requests")
        req_id = resp.json()[0]["id"]
        resp = client.post(
            f"{PREFIX}/requests/{req_id}/feedback",
            json={"rating": "good", "comment": "Well handled"},
        )
        assert resp.status_code == 200
        d = resp.json()
        assert d["feedback_rating"] == "good"
        assert d["feedback_comment"] == "Well handled"

    def test_14_invalid_feedback_rating(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/requests")
        req_id = resp.json()[0]["id"]
        resp = client.post(
            f"{PREFIX}/requests/{req_id}/feedback",
            json={"rating": "invalid", "comment": ""},
        )
        assert resp.status_code == 422

    def test_15_feedback_nonexistent(self, client: TestClient) -> None:
        resp = client.post(
            f"{PREFIX}/requests/nonexistent-id/feedback",
            json={"rating": "good", "comment": ""},
        )
        assert resp.status_code == 404


class TestOverrideCRUD:
    def test_16_list_overrides_empty(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/overrides")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_17_create_override(self, client: TestClient) -> None:
        resp = client.post(
            f"{PREFIX}/overrides",
            json={
                "target": "agent-007",
                "target_type": "agent",
                "action": "pause",
                "reason": "Security incident detected",
                "authorized_by": "admin",
                "incident_id": "inc-001",
            },
        )
        assert resp.status_code == 200
        d = resp.json()
        assert d["target"] == "agent-007"
        assert d["action"] == "pause"

    def test_18_list_overrides_after_create(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/overrides")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["target"] == "agent-007"


class TestReload:
    def test_19_reload(self, client: TestClient) -> None:
        resp = client.post(f"{PREFIX}/reload")
        assert resp.status_code == 200
        d = resp.json()
        assert d["status"] == "success"
