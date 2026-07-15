from __future__ import annotations

from fastapi.testclient import TestClient

PREFIX = "/api/v1/governance/rules-engine"


class TestRuleEvaluate:
    def test_evaluate_existing_rule(self, client: TestClient) -> None:
        rs_resp = client.post(
            f"{PREFIX}/rulesets",
            json={
                "name": "RS-Eval",
                "description": "",
                "conflict_strategy": "priority_wins",
            },
        )
        assert rs_resp.status_code == 200
        rs_id = rs_resp.json()["id"]

        r_resp = client.post(
            f"{PREFIX}/rules",
            json={
                "rule_set_id": rs_id,
                "name": "test-rule",
                "type": "standard",
                "condition_group": {
                    "operator": "and",
                    "conditions": [{"field": "amount", "operator": "gt", "value": 100}],
                },
                "actions": [{"type": "log", "target": "audit"}],
            },
        )
        assert r_resp.status_code == 200
        r_id = r_resp.json()["id"]

        resp = client.post(
            f"{PREFIX}/rules/{r_id}/evaluate", json={"input_data": {"amount": 200}}
        )
        assert resp.status_code == 200
        data = resp.json()

    def test_evaluate_nonexistent_rule(self, client: TestClient) -> None:
        resp = client.post(
            f"{PREFIX}/rules/nonexistent/evaluate", json={"input_data": {}}
        )
        assert resp.status_code == 404

    def test_evaluate_with_empty_input(self, client: TestClient) -> None:
        rs_resp = client.post(
            f"{PREFIX}/rulesets", json={"name": "RS-Eval2", "description": ""}
        )
        assert rs_resp.status_code == 200
        r_resp = client.post(
            f"{PREFIX}/rules",
            json={
                "rule_set_id": rs_resp.json()["id"],
                "name": "always-true",
                "type": "standard",
                "condition_group": {"operator": "and", "conditions": []},
                "actions": [],
            },
        )
        assert r_resp.status_code == 200
        r_id = r_resp.json()["id"]

        resp = client.post(f"{PREFIX}/rules/{r_id}/evaluate", json={"input_data": {}})
        assert resp.status_code == 200


class TestRuleVersions:
    def test_get_versions_empty(self, client: TestClient) -> None:
        r_resp = client.post(
            f"{PREFIX}/rules",
            json={
                "name": "version-rule",
                "type": "standard",
                "condition_group": {},
                "actions": [],
            },
        )
        assert r_resp.status_code == 200
        r_id = r_resp.json()["id"]

        resp = client.get(f"{PREFIX}/rules/{r_id}/versions")
        assert resp.status_code == 200
        data = resp.json()

    def test_get_versions_nonexistent_rule(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/rules/nonexistent/versions")
        assert resp.status_code == 404

    def test_publish_version(self, client: TestClient) -> None:
        r_resp = client.post(
            f"{PREFIX}/rules",
            json={
                "name": "publish-rule",
                "type": "standard",
                "condition_group": {},
                "actions": [{"type": "log", "target": "test"}],
            },
        )
        assert r_resp.status_code == 200
        r_id = r_resp.json()["id"]

        pub_resp = client.post(f"{PREFIX}/rules/{r_id}/versions/publish")
        assert pub_resp.status_code == 200
        pub_data = pub_resp.json()

        versions_resp = client.get(f"{PREFIX}/rules/{r_id}/versions")
        assert versions_resp.status_code == 200
        versions = versions_resp.json()

    def test_publish_nonexistent_rule(self, client: TestClient) -> None:
        resp = client.post(f"{PREFIX}/rules/nonexistent/versions/publish")
        assert resp.status_code == 404


class TestSyncToEngine:
    def test_sync_all(self, client: TestClient) -> None:
        resp = client.post(f"{PREFIX}/rules/sync")
        assert resp.status_code == 200
        data = resp.json()
        assert "synced_count" in data
        assert "message" in data

    def test_sync_with_ruleset_filter(self, client: TestClient) -> None:
        rs_resp = client.post(
            f"{PREFIX}/rulesets", json={"name": "RS-Sync", "description": ""}
        )
        assert rs_resp.status_code == 200
        rs_id = rs_resp.json()["id"]
        client.post(
            f"{PREFIX}/rules",
            json={
                "rule_set_id": rs_id,
                "name": "sync-rule",
                "type": "standard",
                "condition_group": {},
                "actions": [],
            },
        )

        resp = client.post(f"{PREFIX}/rules/sync", params={"ruleset_id": rs_id})
        assert resp.status_code == 200
        data = resp.json()
        assert data["synced_count"] >= 0


class TestConflictStrategy:
    def test_create_ruleset_with_conflict_strategy(self, client: TestClient) -> None:
        for strategy in [
            "priority_wins",
            "first_wins",
            "last_wins",
            "deny_overrides",
            "allow_overrides",
            "most_specific",
            "manual",
        ]:
            resp = client.post(
                f"{PREFIX}/rulesets",
                json={
                    "name": f"RS-{strategy}",
                    "description": "",
                    "conflict_strategy": strategy,
                },
            )
            assert resp.status_code == 200
            assert resp.json()["conflict_strategy"] == strategy

    def test_default_conflict_strategy(self, client: TestClient) -> None:
        resp = client.post(
            f"{PREFIX}/rulesets", json={"name": "RS-Default", "description": ""}
        )
        assert resp.status_code == 200
        assert resp.json()["conflict_strategy"] == "priority_wins"

    def test_update_conflict_strategy(self, client: TestClient) -> None:
        resp = client.post(
            f"{PREFIX}/rulesets", json={"name": "RS-Update", "description": ""}
        )
        assert resp.status_code == 200
        rs_id = resp.json()["id"]

        update = client.put(
            f"{PREFIX}/rulesets/{rs_id}", json={"conflict_strategy": "first_wins"}
        )
        assert update.status_code == 200
        assert update.json()["conflict_strategy"] == "first_wins"
