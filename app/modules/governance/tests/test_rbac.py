from __future__ import annotations

from fastapi.testclient import TestClient

PREFIX = "/api/v1/governance/rbac"


class TestRoles:
    def test_01_list_roles_empty(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/roles")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_02_create_role(self, client: TestClient) -> None:
        resp = client.post(
            f"{PREFIX}/roles",
            json={
                "role_id": "test-editor",
                "name": "Editor",
                "description": "Can edit resources",
                "permissions": ["read", "write"],
            },
        )
        assert resp.status_code == 200
        d = resp.json()
        assert d["role_id"] == "test-editor"
        assert d["permissions"] == ["read", "write"]
        assert d["is_builtin"] is False

    def test_03_create_duplicate_role(self, client: TestClient) -> None:
        resp = client.post(
            f"{PREFIX}/roles",
            json={"role_id": "test-editor", "name": "Editor"},
        )
        assert resp.status_code == 400

    def test_04_list_roles_after_create(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/roles")
        assert len(resp.json()) >= 1
        role_ids = [r["role_id"] for r in resp.json()]
        assert "test-editor" in role_ids

    def test_05_delete_role(self, client: TestClient) -> None:
        resp = client.delete(f"{PREFIX}/roles/test-editor")
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_06_delete_non_existent_role(self, client: TestClient) -> None:
        resp = client.delete(f"{PREFIX}/roles/nonexistent-role")
        assert resp.status_code == 404


class TestPermissions:
    def test_07_create_permission(self, client: TestClient) -> None:
        resp = client.post(
            f"{PREFIX}/permissions",
            json={
                "permission_id": "test:read",
                "name": "Test Read",
                "resource_type": "document",
                "resource_pattern": "test:*",
                "actions": ["read"],
            },
        )
        assert resp.status_code == 200
        d = resp.json()
        assert d["permission_id"] == "test:read"
        assert "test:read" in d["actions"]

    def test_08_list_permissions(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/permissions")
        assert resp.status_code == 200
        perm_ids = [p["permission_id"] for p in resp.json()]
        assert "test:read" in perm_ids

    def test_09_delete_permission(self, client: TestClient) -> None:
        resp = client.delete(f"{PREFIX}/permissions/test:read")
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_10_delete_non_existent_permission(self, client: TestClient) -> None:
        resp = client.delete(f"{PREFIX}/permissions/nonexistent-perm")
        assert resp.status_code == 404


class TestGroups:
    def test_11_create_group_empty(self, client: TestClient) -> None:
        resp = client.post(
            f"{PREFIX}/groups",
            json={
                "group_id": "test-group-empty",
                "name": "Empty Group",
                "roles": [],
            },
        )
        assert resp.status_code == 200
        assert resp.json()["group_id"] == "test-group-empty"

    def test_12_create_group_with_roles(self, client: TestClient) -> None:
        client.post(
            f"{PREFIX}/roles",
            json={
                "role_id": "group-role",
                "name": "Group Role",
                "permissions": ["read"],
            },
        )
        resp = client.post(
            f"{PREFIX}/groups",
            json={
                "group_id": "test-group-roles",
                "name": "Group With Roles",
                "roles": ["group-role"],
            },
        )
        assert resp.status_code == 200
        assert "group-role" in resp.json()["roles"]

    def test_13_list_groups(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/groups")
        assert resp.status_code == 200
        group_ids = [g["group_id"] for g in resp.json()]
        # Empty groups (no role assignments) don't appear in list
        assert "test-group-empty" not in group_ids
        assert "test-group-roles" in group_ids

    def test_14_update_group_roles(self, client: TestClient) -> None:
        resp = client.put(
            f"{PREFIX}/groups/test-group-empty",
            json={"roles": ["group-role"]},
        )
        assert resp.status_code == 200

    def test_15_update_nonexistent_group(self, client: TestClient) -> None:
        # Without providing roles, a nonexistent group returns 404
        resp = client.put(
            f"{PREFIX}/groups/nonexistent-group",
            json={"name": "Ghost"},
        )
        assert resp.status_code == 404

    def test_16_add_member_to_group(self, client: TestClient) -> None:
        resp = client.post(
            f"{PREFIX}/groups/test-group-roles/members",
            json={"agent_id": "agent-member-001"},
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_17_delete_group(self, client: TestClient) -> None:
        resp = client.delete(f"{PREFIX}/groups/test-group-empty")
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_18_get_deleted_group_not_in_list(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/groups")
        group_ids = [g["group_id"] for g in resp.json()]
        assert "test-group-empty" not in group_ids
