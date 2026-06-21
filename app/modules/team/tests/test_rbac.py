from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from common_lib.modules.team.models import WorkspaceSetting

PREFIX = "/api/v1/team"


class TestTeamRBACConfig:
    def test_01_get_empty_rbac(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/1/rbac")
        assert resp.status_code == 200
        d = resp.json()
        assert d["roles"] == []
        assert d["navPermissions"] == {}
        assert d["apiPermissions"] == {}

    def test_02_save_full_rbac(self, client: TestClient) -> None:
        resp = client.put(
            f"{PREFIX}/1/rbac",
            json={
                "roles": [
                    {"id": "admin", "name": "Admin", "permissions": ["*"]},
                    {"id": "viewer", "name": "Viewer", "permissions": ["read"]},
                ],
                "navPermissions": {"admin": ["*"], "viewer": ["dashboard"]},
                "apiPermissions": {"admin": ["*"], "viewer": ["GET"]},
            },
        )
        assert resp.status_code == 200
        d = resp.json()
        assert len(d["roles"]) == 2
        assert d["navPermissions"]["admin"] == ["*"]
        assert d["apiPermissions"]["viewer"] == ["GET"]

    def test_03_roundtrip_rbac(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/1/rbac")
        d = resp.json()
        assert len(d["roles"]) == 2
        assert d["navPermissions"]["admin"] == ["*"]

    def test_04_get_nonexistent_team_returns_empty(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/9999/rbac")
        assert resp.status_code == 200
        d = resp.json()
        assert d["roles"] == []
        assert d["navPermissions"] == {}
        assert d["apiPermissions"] == {}

    def test_05_save_to_nonexistent_team(self, client: TestClient) -> None:
        resp = client.put(
            f"{PREFIX}/9999/rbac",
            json={
                "roles": [{"id": "custom", "name": "Custom", "permissions": ["read"]}],
            },
        )
        assert resp.status_code == 200
        d = resp.json()
        assert len(d["roles"]) == 1
        assert d["roles"][0]["id"] == "custom"

    def test_06_overwrite_rbac(self, client: TestClient) -> None:
        resp = client.put(
            f"{PREFIX}/1/rbac",
            json={
                "roles": [
                    {"id": "superadmin", "name": "Super Admin", "permissions": ["*"]}
                ],
                "navPermissions": {"superadmin": ["*"]},
                "apiPermissions": {"superadmin": ["*"]},
            },
        )
        assert resp.status_code == 200
        assert len(resp.json()["roles"]) == 1
        assert resp.json()["roles"][0]["id"] == "superadmin"

    def test_07_verify_overwrite(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/1/rbac")
        assert len(resp.json()["roles"]) == 1
        assert resp.json()["roles"][0]["id"] == "superadmin"


class TestTeamRBACRoles:
    def test_08_get_roles(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/1/rbac/roles")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_09_save_roles(self, client: TestClient) -> None:
        new_roles = [
            {"id": "role-a", "name": "Role A", "permissions": ["read"]},
            {"id": "role-b", "name": "Role B", "permissions": ["write"]},
        ]
        resp = client.put(f"{PREFIX}/1/rbac/roles", json=new_roles)
        assert resp.status_code == 200

    def test_10_verify_saved_roles(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/1/rbac/roles")
        roles = resp.json()
        role_ids = [r["id"] for r in roles]
        assert "role-a" in role_ids
        assert "role-b" in role_ids


class TestTeamRBACNav:
    def test_11_get_nav_permissions(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/1/rbac/nav")
        assert resp.status_code == 200
        assert isinstance(resp.json(), dict)

    def test_12_save_nav_permissions(self, client: TestClient) -> None:
        nav = {"admin": ["dashboard", "settings"], "viewer": ["dashboard"]}
        resp = client.put(f"{PREFIX}/1/rbac/nav", json=nav)
        assert resp.status_code == 200
        assert resp.json()["navPermissions"]["admin"] == ["dashboard", "settings"]

    def test_13_verify_saved_nav(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/1/rbac/nav")
        assert resp.json()["admin"] == ["dashboard", "settings"]


class TestTeamRBACAPI:
    def test_14_get_api_permissions(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/1/rbac/api")
        assert resp.status_code == 200
        assert isinstance(resp.json(), dict)

    def test_15_save_api_permissions(self, client: TestClient) -> None:
        api = {"admin": ["GET", "POST", "PUT", "DELETE"], "viewer": ["GET"]}
        resp = client.put(f"{PREFIX}/1/rbac/api", json=api)
        assert resp.status_code == 200
        assert resp.json()["apiPermissions"]["admin"] == [
            "GET",
            "POST",
            "PUT",
            "DELETE",
        ]

    def test_16_verify_saved_api(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/1/rbac/api")
        assert resp.json()["viewer"] == ["GET"]

    def test_17_verify_full_config_preserves_all_keys(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/1/rbac")
        d = resp.json()
        assert "roles" in d
        assert "navPermissions" in d
        assert "apiPermissions" in d
        assert len(d["roles"]) >= 2
