from __future__ import annotations

from fastapi.testclient import TestClient

PREFIX = "/api/v1/governance/approval-policies"


class TestApprovalPolicyList:
    def test_01_list_empty(self, client: TestClient) -> None:
        resp = client.get(PREFIX)
        assert resp.status_code == 200
        assert resp.json() == []


class TestApprovalPolicyCreate:
    def test_02_create_policy(self, client: TestClient) -> None:
        resp = client.post(
            PREFIX,
            json={
                "approval_policy_id": "policy-1",
                "name": "High Risk Approval",
                "description": "Requires VP approval for high-risk actions",
                "trigger_conditions": [{"field": "risk_score", "op": ">", "value": 80}],
                "approvers": {"users": ["vp-1", "vp-2"], "min_approvals": 1},
                "timeout": {"seconds": 300},
                "escalation": {"escalate_after": 120, "escalate_to": "cto"},
                "trigger_ids": [],
                "hook_ids": [],
            },
        )
        assert resp.status_code == 200
        d = resp.json()
        assert d["approval_policy_id"] == "policy-1"
        assert d["name"] == "High Risk Approval"

    def test_03_create_duplicate_policy(self, client: TestClient) -> None:
        resp = client.post(
            PREFIX,
            json={
                "approval_policy_id": "policy-1",
                "name": "Duplicate",
            },
        )
        assert resp.status_code == 409


class TestApprovalPolicyRead:
    def test_04_get_policy(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/policy-1")
        assert resp.status_code == 200
        assert resp.json()["approval_policy_id"] == "policy-1"

    def test_05_get_nonexistent_policy(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/nonexistent")
        assert resp.status_code == 404

    def test_06_list_policies(self, client: TestClient) -> None:
        resp = client.post(
            PREFIX,
            json={"approval_policy_id": "policy-2", "name": "Policy Two"},
        )
        assert resp.status_code == 200
        resp = client.get(PREFIX)
        ids = [p["approval_policy_id"] for p in resp.json()]
        assert "policy-1" in ids
        assert "policy-2" in ids


class TestApprovalPolicyUpdate:
    def test_07_update_policy(self, client: TestClient) -> None:
        resp = client.put(
            f"{PREFIX}/policy-1",
            json={"name": "High Risk Approval v2", "timeout": {"seconds": 600}},
        )
        assert resp.status_code == 200
        d = resp.json()
        assert d["name"] == "High Risk Approval v2"
        assert d["timeout"]["seconds"] == 600

    def test_08_update_nonexistent_policy(self, client: TestClient) -> None:
        resp = client.put(
            f"{PREFIX}/nonexistent",
            json={"name": "Ghost"},
        )
        assert resp.status_code == 404


class TestApprovalPolicyDelete:
    def test_09_delete_policy(self, client: TestClient) -> None:
        resp = client.delete(f"{PREFIX}/policy-2")
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"

    def test_10_delete_nonexistent_policy(self, client: TestClient) -> None:
        resp = client.delete(f"{PREFIX}/policy-2")
        assert resp.status_code == 404

    def test_11_verify_deleted(self, client: TestClient) -> None:
        resp = client.get(PREFIX)
        ids = [p["approval_policy_id"] for p in resp.json()]
        assert "policy-2" not in ids
        assert "policy-1" in ids


class TestTriggerCRUD:
    def test_12_list_triggers_empty(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/triggers")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_13_create_trigger(self, client: TestClient) -> None:
        resp = client.post(
            f"{PREFIX}/triggers",
            json={
                "id": "trigger-1",
                "name": "High Risk Trigger",
                "description": "Fires on high risk score",
                "conditions": {"risk_min": 80},
            },
        )
        assert resp.status_code == 200
        d = resp.json()
        assert d["id"] == "trigger-1"
        assert d["name"] == "High Risk Trigger"

    def test_14_create_duplicate_trigger(self, client: TestClient) -> None:
        resp = client.post(
            f"{PREFIX}/triggers",
            json={"id": "trigger-1", "name": "Duplicate"},
        )
        assert resp.status_code == 409

    def test_15_get_trigger(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/triggers/trigger-1")
        assert resp.status_code == 200
        assert resp.json()["id"] == "trigger-1"

    def test_16_get_nonexistent_trigger(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/triggers/nonexistent")
        assert resp.status_code == 404

    def test_17_update_trigger(self, client: TestClient) -> None:
        resp = client.put(
            f"{PREFIX}/triggers/trigger-1",
            json={"name": "Trigger v2", "conditions": {"risk_min": 90}},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Trigger v2"

    def test_18_update_nonexistent_trigger(self, client: TestClient) -> None:
        resp = client.put(
            f"{PREFIX}/triggers/nonexistent",
            json={"name": "Ghost"},
        )
        assert resp.status_code == 404

    def test_19_delete_trigger(self, client: TestClient) -> None:
        resp = client.delete(f"{PREFIX}/triggers/trigger-1")
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"

    def test_20_delete_nonexistent_trigger(self, client: TestClient) -> None:
        resp = client.delete(f"{PREFIX}/triggers/nonexistent")
        assert resp.status_code == 404


class TestHookCRUD:
    def test_21_list_hooks_empty(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/hooks")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_22_create_hook(self, client: TestClient) -> None:
        resp = client.post(
            f"{PREFIX}/hooks",
            json={
                "id": "hook-1",
                "name": "Notify Hook",
                "description": "Sends notification on approval",
                "approvers": {"users": ["admin"]},
                "timeout": {"seconds": 60},
            },
        )
        assert resp.status_code == 200
        d = resp.json()
        assert d["id"] == "hook-1"
        assert d["name"] == "Notify Hook"

    def test_23_create_duplicate_hook(self, client: TestClient) -> None:
        resp = client.post(
            f"{PREFIX}/hooks",
            json={"id": "hook-1", "name": "Duplicate"},
        )
        assert resp.status_code == 409

    def test_24_get_hook(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/hooks/hook-1")
        assert resp.status_code == 200
        assert resp.json()["id"] == "hook-1"

    def test_25_get_nonexistent_hook(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/hooks/nonexistent")
        assert resp.status_code == 404

    def test_26_update_hook(self, client: TestClient) -> None:
        resp = client.put(
            f"{PREFIX}/hooks/hook-1",
            json={"name": "Hook v2", "escalation": {"escalate_to": "manager"}},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Hook v2"

    def test_27_update_nonexistent_hook(self, client: TestClient) -> None:
        resp = client.put(
            f"{PREFIX}/hooks/nonexistent",
            json={"name": "Ghost"},
        )
        assert resp.status_code == 404

    def test_28_delete_hook(self, client: TestClient) -> None:
        resp = client.delete(f"{PREFIX}/hooks/hook-1")
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"

    def test_29_delete_nonexistent_hook(self, client: TestClient) -> None:
        resp = client.delete(f"{PREFIX}/hooks/nonexistent")
        assert resp.status_code == 404


class TestInterceptorCRUD:
    def test_30_list_interceptors_empty(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/interceptors")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_31_create_interceptor(self, client: TestClient) -> None:
        resp = client.post(
            f"{PREFIX}/interceptors",
            json={
                "id": "interceptor-1",
                "name": "Audit Interceptor",
                "description": "Logs all policy evaluations",
                "priority": 100,
                "policy_id": "policy-1",
                "conditions": [{"field": "action", "op": "eq", "value": "execute"}],
                "action": "chain",
                "enabled": True,
                "triggers": [],
                "hooks": [],
                "approvers": {},
                "timeout": {},
                "escalation": {},
            },
        )
        assert resp.status_code == 200
        d = resp.json()
        assert d["id"] == "interceptor-1"
        assert d["name"] == "Audit Interceptor"

    def test_32_create_duplicate_interceptor(self, client: TestClient) -> None:
        resp = client.post(
            f"{PREFIX}/interceptors",
            json={"id": "interceptor-1", "name": "Duplicate"},
        )
        assert resp.status_code == 409

    def test_33_get_interceptor(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/interceptors/interceptor-1")
        assert resp.status_code == 200
        assert resp.json()["id"] == "interceptor-1"

    def test_34_get_nonexistent_interceptor(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/interceptors/nonexistent")
        assert resp.status_code == 404

    def test_35_update_interceptor(self, client: TestClient) -> None:
        resp = client.put(
            f"{PREFIX}/interceptors/interceptor-1",
            json={"name": "Interceptor v2", "priority": 50},
        )
        assert resp.status_code == 200
        d = resp.json()
        assert d["name"] == "Interceptor v2"
        assert d["priority"] == 50

    def test_36_update_nonexistent_interceptor(self, client: TestClient) -> None:
        resp = client.put(
            f"{PREFIX}/interceptors/nonexistent",
            json={"name": "Ghost"},
        )
        assert resp.status_code == 404

    def test_37_delete_interceptor(self, client: TestClient) -> None:
        resp = client.delete(f"{PREFIX}/interceptors/interceptor-1")
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"

    def test_38_delete_nonexistent_interceptor(self, client: TestClient) -> None:
        resp = client.delete(f"{PREFIX}/interceptors/nonexistent")
        assert resp.status_code == 404
