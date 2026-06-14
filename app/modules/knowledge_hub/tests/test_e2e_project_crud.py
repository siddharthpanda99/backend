"""
E2E tests for the full Knowledge Project CRUD lifecycle.

Tests create, read, update, delete, duplicate, members, and activity
logging for knowledge projects.

Usage:
    cd "Backend Monorepo/Backend"
    uv run python -m pytest app/modules/knowledge_hub/tests/test_e2e_project_crud.py -v
"""

from __future__ import annotations

from typing import Optional

import pytest
from fastapi.testclient import TestClient

PREFIX = "/api/v1/knowledge-hub"

# Module-level storage for auto-generated IDs across test classes
_E2E_AUTO_ID: Optional[str] = None
_E2E_DUP_IDS: list[str] = []


# ═══════════════════════════════════════════════════════════════════
# Phase 1: Project CRUD
# ═══════════════════════════════════════════════════════════════════


class TestProjectCreate:
    """Project creation tests."""

    def test_01_create_minimal_project(self, client: TestClient) -> None:
        """Create a project with only required fields."""
        resp = client.post(
            f"{PREFIX}/projects",
            json={"id": "e2e-crud-minimal", "name": "Minimal Project"},
        )
        assert resp.status_code == 201
        d = resp.json()["data"]
        assert d["id"] == "e2e-crud-minimal"
        assert d["name"] == "Minimal Project"
        assert d["status"] == "draft"
        assert d["description"] is None
        assert d["packet_ids"] == []
        assert d["tags"] == []
        assert d["attached_agent_id"] is None
        assert d["verified_at"] is None
        assert "created_at" in d
        assert "updated_at" in d

    def test_02_create_full_project(self, client: TestClient) -> None:
        """Create a project with all fields."""
        resp = client.post(
            f"{PREFIX}/projects",
            json={
                "id": "e2e-crud-full",
                "name": "Full Project",
                "description": "A project with every field populated",
                "packet_ids": ["pkt-academic-001", "pkt-news-001"],
                "tags": ["e2e-test", "crud", "full"],
            },
        )
        assert resp.status_code == 201
        d = resp.json()["data"]
        assert d["id"] == "e2e-crud-full"
        assert d["name"] == "Full Project"
        assert d["description"] == "A project with every field populated"
        assert len(d["packet_ids"]) == 2
        assert "pkt-academic-001" in d["packet_ids"]
        assert "pkt-news-001" in d["packet_ids"]
        assert d["tags"] == ["e2e-test", "crud", "full"]

    def test_03_create_without_id(self, client: TestClient) -> None:
        """Create a project without specifying an ID (auto-generated)."""
        global _E2E_AUTO_ID
        resp = client.post(
            f"{PREFIX}/projects",
            json={
                "name": "Auto-ID Project",
                "description": "ID will be auto-generated",
                "tags": ["auto-id"],
            },
        )
        assert resp.status_code == 201
        d = resp.json()["data"]
        assert d["id"] is not None
        assert d["name"] == "Auto-ID Project"
        _E2E_AUTO_ID = d["id"]

    def test_04_get_created_project(self, client: TestClient) -> None:
        """GET returns the full project record."""
        resp = client.get(f"{PREFIX}/projects/e2e-crud-full")
        assert resp.status_code == 200
        d = resp.json()["data"]
        assert d["name"] == "Full Project"
        assert d["status"] == "draft"
        assert d["description"] == "A project with every field populated"
        assert len(d["packet_ids"]) == 2
        assert "data_object_schema" in d
        assert "methods" in d["data_object_schema"]


class TestProjectRead:
    """Project read and list tests."""

    def test_05_get_project_not_found(self, client: TestClient) -> None:
        """GET a non-existent project returns 404."""
        resp = client.get(f"{PREFIX}/projects/nonexistent-project-id")
        assert resp.status_code == 404

    def test_06_list_projects(self, client: TestClient) -> None:
        """List returns all projects including seed data."""
        resp = client.get(f"{PREFIX}/projects")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["total"] >= 1
        names = [p["name"] for p in body["data"]]
        assert "AI Impact Research" in names
        assert "Minimal Project" in names
        assert "Full Project" in names

    def test_07_list_projects_filter_by_status(self, client: TestClient) -> None:
        """List projects filtered by status."""
        resp = client.get(f"{PREFIX}/projects?status=draft")
        assert resp.status_code == 200
        assert all(p["status"] == "draft" for p in resp.json()["data"])


class TestProjectUpdate:
    """Project update tests."""

    def test_08_update_project_name(self, client: TestClient) -> None:
        """Update only the name."""
        resp = client.put(
            f"{PREFIX}/projects/e2e-crud-minimal",
            json={"name": "Updated Minimal Project"},
        )
        assert resp.status_code == 200
        d = resp.json()["data"]
        assert d["name"] == "Updated Minimal Project"
        assert d["status"] == "draft"  # unchanged

    def test_09_update_project_all_fields(self, client: TestClient) -> None:
        """Update all mutable fields."""
        resp = client.put(
            f"{PREFIX}/projects/e2e-crud-minimal",
            json={
                "name": "Fully Updated Project",
                "description": "Updated description",
                "packet_ids": ["pkt-academic-001"],
                "tags": ["updated", "e2e-test"],
            },
        )
        assert resp.status_code == 200
        d = resp.json()["data"]
        assert d["name"] == "Fully Updated Project"
        assert d["description"] == "Updated description"
        assert d["packet_ids"] == ["pkt-academic-001"]
        assert d["tags"] == ["updated", "e2e-test"]

    def test_10_update_non_existent_project(self, client: TestClient) -> None:
        """Updating a non-existent project returns 404."""
        resp = client.put(
            f"{PREFIX}/projects/nonexistent-update",
            json={"name": "Should Not Exist"},
        )
        assert resp.status_code == 404

    def test_11_update_preserves_timestamps(self, client: TestClient) -> None:
        """Update refreshes updated_at but preserves created_at."""
        resp = client.get(f"{PREFIX}/projects/e2e-crud-full")
        d = resp.json()["data"]
        created = d["created_at"]

        resp = client.put(
            f"{PREFIX}/projects/e2e-crud-full",
            json={"name": "Still Full Project"},
        )
        updated_d = resp.json()["data"]
        assert updated_d["created_at"] == created
        # updated_at should differ from created_at after update
        assert updated_d["updated_at"] != created


# ═══════════════════════════════════════════════════════════════════
# Phase 2: Project Duplicate
# ═══════════════════════════════════════════════════════════════════


class TestProjectDuplicate:
    """Project duplication tests."""

    def test_12_duplicate_project(self, client: TestClient) -> None:
        """Duplicate a project including its documents."""
        global _E2E_DUP_IDS
        # Fetch current name first (may have been updated by TestProjectUpdate)
        current = client.get(f"{PREFIX}/projects/e2e-crud-full").json()["data"]
        expected_copy_name = f"{current['name']} (Copy)"

        resp = client.post(
            f"{PREFIX}/projects/e2e-crud-full/duplicate",
            json={"include_docs": True},
        )
        assert resp.status_code == 201
        d = resp.json()["data"]
        assert d["name"] == expected_copy_name
        assert d["status"] == "draft"
        assert d["packet_ids"] == ["pkt-academic-001", "pkt-news-001"]
        assert d["tags"] == ["e2e-test", "crud", "full"]
        assert "Copy" in d["name"]
        assert resp.json()["documents_copied"] >= 0
        _E2E_DUP_IDS.append(d["id"])

    def test_13_duplicate_project_without_docs(self, client: TestClient) -> None:
        """Duplicate a project without documents."""
        global _E2E_DUP_IDS
        current = client.get(f"{PREFIX}/projects/e2e-crud-minimal").json()["data"]
        expected_copy_name = f"{current['name']} (Copy)"

        resp = client.post(
            f"{PREFIX}/projects/e2e-crud-minimal/duplicate",
            json={"include_docs": False},
        )
        assert resp.status_code == 201
        d = resp.json()["data"]
        assert d["name"] == expected_copy_name
        assert d["status"] == "draft"
        _E2E_DUP_IDS.append(d["id"])

    def test_14_duplicate_non_existent(self, client: TestClient) -> None:
        """Duplicating a non-existent project returns 404."""
        resp = client.post(
            f"{PREFIX}/projects/nonexistent-dup/duplicate",
            json={"include_docs": True},
        )
        assert resp.status_code == 404

    def test_15_verify_duplicate_independence(self, client: TestClient) -> None:
        """Original and duplicate are independent records."""
        global _E2E_DUP_IDS
        if not _E2E_DUP_IDS:
            pytest.skip("No duplicates created yet")

        orig = client.get(f"{PREFIX}/projects/e2e-crud-full").json()["data"]
        dup = client.get(f"{PREFIX}/projects/{_E2E_DUP_IDS[0]}").json()["data"]
        assert orig["id"] != dup["id"]
        assert orig["name"] != dup["name"]  # Copy has "(Copy)" suffix
        # Update original should not affect duplicate
        client.put(f"{PREFIX}/projects/e2e-crud-full", json={"name": "OG Project"})
        dup_check = client.get(f"{PREFIX}/projects/{_E2E_DUP_IDS[0]}").json()["data"]
        assert dup_check["name"] != "OG Project"
        assert "Copy" in dup_check["name"]


# ═══════════════════════════════════════════════════════════════════
# Phase 3: Project Members
# ═══════════════════════════════════════════════════════════════════


class TestProjectMembers:
    """Project member management tests."""

    def test_16_add_member(self, client: TestClient) -> None:
        """Add a member to the project."""
        resp = client.post(
            f"{PREFIX}/projects/e2e-crud-full/members",
            json={"user_id": "user-alice-001", "role": "editor"},
        )
        assert resp.status_code == 201
        d = resp.json()["data"]
        assert d["user_id"] == "user-alice-001"
        assert d["role"] == "editor"
        assert d["project_id"] == "e2e-crud-full"
        assert "invited_by" in d
        assert "invited_at" in d

    def test_17_add_multiple_members(self, client: TestClient) -> None:
        """Add members with different roles."""
        for user_id, role in [("user-bob-002", "viewer"), ("user-carol-003", "admin")]:
            resp = client.post(
                f"{PREFIX}/projects/e2e-crud-full/members",
                json={"user_id": user_id, "role": role},
            )
            assert resp.status_code == 201
            assert resp.json()["data"]["role"] == role

    def test_18_list_members(self, client: TestClient) -> None:
        """List all members of the project."""
        resp = client.get(f"{PREFIX}/projects/e2e-crud-full/members")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["total"] == 3
        user_ids = {m["user_id"] for m in body["data"]}
        assert "user-alice-001" in user_ids
        assert "user-bob-002" in user_ids
        assert "user-carol-003" in user_ids

    def test_19_change_member_role(self, client: TestClient) -> None:
        """Change a member's role."""
        resp = client.put(
            f"{PREFIX}/projects/e2e-crud-full/members/user-bob-002",
            json={"role": "editor"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["role"] == "editor"

    def test_20_change_member_role_invalid(self, client: TestClient) -> None:
        """Changing role to an invalid value returns 422."""
        resp = client.put(
            f"{PREFIX}/projects/e2e-crud-full/members/user-bob-002",
            json={"role": "superadmin"},
        )
        assert resp.status_code == 422

    def test_21_remove_member(self, client: TestClient) -> None:
        """Remove a member from the project."""
        resp = client.delete(
            f"{PREFIX}/projects/e2e-crud-full/members/user-bob-002"
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        # Verify removal
        list_resp = client.get(f"{PREFIX}/projects/e2e-crud-full/members")
        assert list_resp.json()["total"] == 2

    def test_22_remove_non_existent_member(self, client: TestClient) -> None:
        """Removing a non-existent member returns 404."""
        resp = client.delete(
            f"{PREFIX}/projects/e2e-crud-full/members/user-nonexistent"
        )
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════
# Phase 4: Activity Log & Miscellaneous
# ═══════════════════════════════════════════════════════════════════


class TestProjectActivity:
    """Project activity log tests."""

    def test_23_list_activity(self, client: TestClient) -> None:
        """Activity log is accessible for the project."""
        resp = client.get(f"{PREFIX}/projects/e2e-crud-full/activity")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert isinstance(body["data"], list)

    def test_24_activity_for_non_existent_project(self, client: TestClient) -> None:
        """Activity log for non-existent project returns 404."""
        resp = client.get(f"{PREFIX}/projects/nonexistent/activity")
        assert resp.status_code == 404

    def test_25_list_members_non_existent_project(self, client: TestClient) -> None:
        """List members for non-existent project returns 404."""
        resp = client.get(f"{PREFIX}/projects/nonexistent/members")
        assert resp.status_code == 404

    def test_26_add_member_non_existent_project(self, client: TestClient) -> None:
        """Add member to non-existent project returns 404."""
        resp = client.post(
            f"{PREFIX}/projects/fake-project/members",
            json={"user_id": "test", "role": "viewer"},
        )
        assert resp.status_code == 404

    def test_27_change_role_non_existent_member(self, client: TestClient) -> None:
        """Change role for non-existent member returns 404."""
        resp = client.put(
            f"{PREFIX}/projects/e2e-crud-full/members/user-nonexistent",
            json={"role": "editor"},
        )
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════
# Phase 5: Project Deletion
# ═══════════════════════════════════════════════════════════════════


class TestProjectDelete:
    """Project deletion tests."""

    def test_28_delete_project(self, client: TestClient) -> None:
        """Delete a project."""
        resp = client.delete(f"{PREFIX}/projects/e2e-crud-minimal")
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_29_get_deleted_project(self, client: TestClient) -> None:
        """GET on deleted project returns 404."""
        resp = client.get(f"{PREFIX}/projects/e2e-crud-minimal")
        assert resp.status_code == 404

    def test_30_delete_non_existent_project(self, client: TestClient) -> None:
        """DELETE on non-existent project returns 404."""
        resp = client.delete(f"{PREFIX}/projects/nonexistent-delete")
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════
# Phase 6: Cleanup — Remove all E2E test resources
# ═══════════════════════════════════════════════════════════════════


class TestCleanup:
    """Remove all resources created during E2E CRUD testing."""

    def test_31_cleanup_full_project(self, client: TestClient) -> None:
        """Delete the full test project."""
        client.delete(f"{PREFIX}/projects/e2e-crud-full")
        resp = client.get(f"{PREFIX}/projects/e2e-crud-full")
        assert resp.status_code == 404

    def test_32_cleanup_auto_id_project(self, client: TestClient) -> None:
        """Delete the auto-ID project if it was created."""
        global _E2E_AUTO_ID
        if _E2E_AUTO_ID:
            client.delete(f"{PREFIX}/projects/{_E2E_AUTO_ID}")

    def test_33_cleanup_duplicates(self, client: TestClient) -> None:
        """Delete duplicated projects."""
        global _E2E_DUP_IDS
        for dup_id in _E2E_DUP_IDS:
            client.delete(f"{PREFIX}/projects/{dup_id}")

    def test_34_list_returns_seed_only(self, client: TestClient) -> None:
        """After cleanup, list should only contain seed projects."""
        resp = client.get(f"{PREFIX}/projects")
        assert resp.status_code == 200
        body = resp.json()
        for p in body["data"]:
            assert not p["id"].startswith("e2e-crud-"), f"E2E resource still exists: {p['id']}"
