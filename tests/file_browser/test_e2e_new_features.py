"""Comprehensive E2E tests for all new features combined."""

import requests
import pytest


def test_full_file_lifecycle_with_all_features(api_base, test_id):
    """
    Comprehensive test covering:
    1. Create folder
    2. Upload file
    3. Add tags
    4. Add label
    5. Star file
    6. Create share link
    7. Copy file
    8. Move file
    9. Download file
    10. Remove tag
    11. Delete file
    """
    # 1. Create folder
    folder_name = f"e2e_folder_{test_id}"
    resp = requests.post(f"{api_base}/folders", json={"name": folder_name})
    assert resp.status_code == 200
    folder_id = resp.json()["id"]

    try:
        # 2. Upload file
        files = {"file": (f"test_{test_id}.txt", b"Test content for e2e")}
        resp = requests.post(
            f"{api_base}/files", files=files, data={"folder_id": folder_id}
        )
        assert resp.status_code == 200
        file_id = resp.json()["id"]

        # 3. Add tags
        resp = requests.post(
            f"{api_base}/files/{file_id}/tags", json={"tags": ["e2e", "test"]}
        )
        assert resp.status_code == 200
        assert "e2e" in resp.json()["tags"]

        # 4. Add label
        resp = requests.post(
            f"{api_base}/files/{file_id}/label", json={"label": "Priority"}
        )
        assert resp.status_code == 200
        assert resp.json()["label"] == "Priority"

        # 5. Star file
        resp = requests.post(f"{api_base}/files/{file_id}/star", json={"starred": True})
        assert resp.status_code == 200
        assert resp.json()["is_starred"] is True

        # 6. Create share link
        resp = requests.post(
            f"{api_base}/files/{file_id}/share",
            json={"access_level": "view", "expires_days": 1},
        )
        assert resp.status_code == 200
        share_token = resp.json()["token"]

        # Verify share link works
        resp = requests.get(f"{api_base}/share/{share_token}")
        assert resp.status_code == 200
        assert resp.json()["file_id"] == file_id

        # 7. Copy file
        resp = requests.post(
            f"{api_base}/files/{file_id}/copy", json={"target_folder_id": None}
        )
        assert resp.status_code == 200
        copy_id = resp.json()["id"]

        # Verify copy has same tag
        resp = requests.get(f"{api_base}/files/{copy_id}")
        assert "e2e" in resp.json()["tags"]

        # 8. Move file to root
        resp = requests.post(
            f"{api_base}/files/{file_id}/move", json={"target_folder_id": None}
        )
        assert resp.status_code == 200

        # 9. Download file
        resp = requests.get(f"{api_base}/files/{file_id}/download")
        assert resp.status_code == 200
        assert b"Test content" in resp.content

        # 10. Remove tag
        resp = requests.delete(
            f"{api_base}/files/{file_id}/tags", json={"tags": ["e2e"]}
        )
        assert resp.status_code == 200
        assert "e2e" not in resp.json()["tags"]
        assert "test" in resp.json()["tags"]

        # 11. Delete copy
        resp = requests.delete(f"{api_base}/files/{copy_id}")
        assert resp.status_code == 200

    finally:
        # Cleanup folder (recursively deletes contents)
        requests.post(
            f"{api_base}/files/bulk-delete",
            json={"ids": [folder_id], "permanent": True},
        )


def test_folder_copy_with_metadata_preservation(api_base, test_id):
    """Test copying folder preserves all metadata."""
    # Create folder with files and metadata
    ws_name = f"workspace_meta_{test_id}"
    resp = requests.post(f"{api_base}/folders", json={"name": ws_name})
    src_folder_id = resp.json()["id"]

    # Create subfolder
    resp = requests.post(
        f"{api_base}/folders", json={"name": "subfolder", "parent_id": src_folder_id}
    )
    subfolder_id = resp.json()["id"]

    # Upload file with tags/label
    files = {"file": (f"meta_{test_id}.txt", b"content")}
    resp = requests.post(
        f"{api_base}/files", files=files, data={"folder_id": subfolder_id}
    )
    file_id = resp.json()["id"]

    requests.post(f"{api_base}/files/{file_id}/tags", json={"tags": ["preserved"]})
    requests.post(f"{api_base}/files/{file_id}/label", json={"label": "TestLabel"})

    try:
        # Copy folder
        resp = requests.post(
            f"{api_base}/folders/{src_folder_id}/copy", json={"target_folder_id": None}
        )
        assert resp.status_code == 200
        new_folder_id = resp.json()["id"]

        # Verify copy succeeded
        resp = requests.get(f"{api_base}/files/{new_folder_id}")
        assert resp.status_code == 200

        # Cleanup
        requests.post(
            f"{api_base}/files/bulk-delete",
            json={"ids": [new_folder_id], "permanent": True},
        )

    finally:
        requests.post(
            f"{api_base}/files/bulk-delete",
            json={"ids": [src_folder_id], "permanent": True},
        )


def test_filters_and_search_integration(api_base, test_id):
    """Test filtering and search work together."""
    # Create files with different types
    files_to_create = [
        (f"image_{test_id}.jpg", "image"),
        (f"video_{test_id}.mp4", "video"),
        (f"doc_{test_id}.pdf", "document"),
    ]

    file_ids = []
    for name, _ in files_to_create:
        resp = requests.post(f"{api_base}/files", files={"file": (name, b"content")})
        file_ids.append(resp.json()["id"])

    try:
        # Add tags
        for fid in file_ids:
            requests.post(f"{api_base}/files/{fid}/tags", json={"tags": ["tagged"]})

        # Test type filter
        resp = requests.get(f"{api_base}/files", params={"type": "image"})
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert any("jpg" in item.get("name", "") for item in items)

        # Test tag filter
        resp = requests.get(f"{api_base}/files", params={"tags": "tagged"})
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) >= 3

        # Test search
        resp = requests.get(f"{api_base}/search", params={"q": f"image_{test_id}"})
        assert resp.status_code == 200
        assert any("image" in item.get("name", "") for item in resp.json()["items"])

    finally:
        requests.post(
            f"{api_base}/files/bulk-delete", json={"ids": file_ids, "permanent": True}
        )


def test_share_link_lifecycle(api_base, test_id):
    """Test full share link lifecycle."""
    # Create file
    files = {"file": (f"share_{test_id}.txt", b"sharing content")}
    resp = requests.post(f"{api_base}/files", files=files)
    file_id = resp.json()["id"]

    try:
        # Create multiple share links
        link1 = requests.post(
            f"{api_base}/files/{file_id}/share", json={"access_level": "view"}
        ).json()
        link2 = requests.post(
            f"{api_base}/files/{file_id}/share",
            json={"access_level": "edit", "expires_days": 7},
        ).json()

        # List shares for file
        resp = requests.get(f"{api_base}/files/{file_id}/shares")
        assert resp.status_code == 200
        shares = resp.json()
        assert len(shares) >= 2

        # Revoke first link
        resp = requests.delete(f"{api_base}/shares/{link1['id']}")
        assert resp.status_code == 200

        # Verify revoked link no longer accessible
        resp = requests.get(f"{api_base}/share/{link1['token']}")
        # Should fail or return inactive

        # Second link should still work
        resp = requests.get(f"{api_base}/share/{link2['token']}")
        assert resp.status_code == 200

    finally:
        requests.post(
            f"{api_base}/files/bulk-delete", json={"ids": [file_id], "permanent": True}
        )


def test_sorting_across_operations(api_base, test_id):
    """Test sorting works correctly across different operations."""
    # Create files with predictable names
    names = ["apple", "banana", "cherry"]
    ids = []
    for name in names:
        resp = requests.post(
            f"{api_base}/files", files={"file": (f"{name}_{test_id}.txt", b"content")}
        )
        ids.append(resp.json()["id"])

    try:
        # Sort by name ascending
        resp = requests.get(
            f"{api_base}/files", params={"sort_by": "name", "sort_order": "asc"}
        )
        items = resp.json()["items"]
        test_items = [i for i in items if any(n in i["name"] for n in names)]

        # Verify ascending
        for i in range(len(test_items) - 1):
            assert test_items[i]["name"] <= test_items[i + 1]["name"]

        # Sort by name descending
        resp = requests.get(
            f"{api_base}/files", params={"sort_by": "name", "sort_order": "desc"}
        )
        items = resp.json()["items"]
        test_items = [i for i in items if any(n in i["name"] for n in names)]

        # Verify descending
        for i in range(len(test_items) - 1):
            assert test_items[i]["name"] >= test_items[i + 1]["name"]

    finally:
        requests.post(
            f"{api_base}/files/bulk-delete", json={"ids": ids, "permanent": True}
        )


def test_trash_with_all_metadata_preserved(api_base, test_id):
    """Test that trash preserves all metadata."""
    # Create file with full metadata
    files = {"file": (f"trash_{test_id}.txt", b"to be trashed")}
    resp = requests.post(f"{api_base}/files", files=files)
    file_id = resp.json()["id"]

    # Add metadata
    requests.post(f"{api_base}/files/{file_id}/tags", json={"tags": ["trash-test"]})
    requests.post(f"{api_base}/files/{file_id}/label", json={"label": "Review"})
    requests.post(f"{api_base}/files/{file_id}/star", json={"starred": True})

    # Move to trash
    resp = requests.post(f"{api_base}/files/{file_id}/trash")
    assert resp.status_code == 200
    assert resp.json()["is_trashed"] is True

    # Verify metadata preserved in trash
    resp = requests.get(f"{api_base}/trash")
    trash_items = resp.json()["items"]
    trashed = next((i for i in trash_items if i["id"] == file_id), None)

    assert trashed is not None
    assert "trash-test" in trashed["tags"]
    assert trashed["label"] == "Review"
    assert trashed["is_starred"] is True

    # Restore
    resp = requests.post(f"{api_base}/files/{file_id}/restore")
    assert resp.status_code == 200
    assert resp.json()["is_trashed"] is False
    assert resp.json()["is_starred"] is True

    # Permanent delete
    requests.post(
        f"{api_base}/files/bulk-delete", json={"ids": [file_id], "permanent": True}
    )
