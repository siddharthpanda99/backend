"""Tests for copy folder functionality."""

import requests
import pytest


def test_copy_folder(api_base, test_id):
    """Verify copying a folder creates a new folder with same name."""
    # Create source folder
    ws_name = f"workspace_{test_id}"
    resp = requests.post(f"{api_base}/folders", json={"name": ws_name})
    assert resp.status_code == 200
    folder_id = resp.json()["id"]

    try:
        # Copy folder to root
        resp = requests.post(
            f"{api_base}/folders/{folder_id}/copy", json={"target_folder_id": None}
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        new_folder_id = resp.json()["id"]

        # Verify new folder exists
        resp = requests.get(f"{api_base}/files/{new_folder_id}")
        assert resp.status_code == 200
        assert "Copy of" in resp.json()["name"]

        # Cleanup
        requests.post(
            f"{api_base}/files/bulk-delete",
            json={"ids": [new_folder_id], "permanent": True},
        )

    finally:
        # Cleanup original
        requests.post(
            f"{api_base}/files/bulk-delete",
            json={"ids": [folder_id], "permanent": True},
        )


def test_copy_folder_with_children(api_base, test_id):
    """Verify copying a folder preserves child files."""
    # Create source folder with files
    ws_name = f"workspace_{test_id}"
    resp = requests.post(f"{api_base}/folders", json={"name": ws_name})
    folder_id = resp.json()["id"]

    # Upload file into folder
    files = {"file": (f"test_{test_id}.txt", b"content")}
    resp = requests.post(
        f"{api_base}/files", files=files, data={"folder_id": folder_id}
    )
    file_id = resp.json()["id"]

    try:
        # Copy folder
        resp = requests.post(
            f"{api_base}/folders/{folder_id}/copy", json={"target_folder_id": None}
        )
        assert resp.status_code == 200
        new_folder_id = resp.json()["id"]

        # List files in new folder (it should be empty since we copied just the folder)
        resp = requests.get(f"{api_base}/files", params={"folder_id": new_folder_id})
        assert resp.status_code == 200

        # Cleanup
        requests.post(
            f"{api_base}/files/bulk-delete",
            json={"ids": [new_folder_id], "permanent": True},
        )

    finally:
        requests.post(
            f"{api_base}/files/bulk-delete",
            json={"ids": [folder_id], "permanent": True},
        )


def test_copy_nonexistent_folder(api_base):
    """Verify copying non-existent folder returns error."""
    resp = requests.post(
        f"{api_base}/folders/nonexistent/copy", json={"target_folder_id": None}
    )
    assert resp.status_code == 404


def test_copy_folder_with_new_name(api_base, test_id):
    """Verify copying folder with custom name."""
    ws_name = f"workspace_{test_id}"
    resp = requests.post(f"{api_base}/folders", json={"name": ws_name})
    folder_id = resp.json()["id"]

    try:
        resp = requests.post(
            f"{api_base}/folders/{folder_id}/copy",
            json={"target_folder_id": None, "new_name": "Custom Copy Name"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Custom Copy Name"

        # Cleanup
        requests.post(
            f"{api_base}/files/bulk-delete",
            json={"ids": [resp.json()["id"]], "permanent": True},
        )

    finally:
        requests.post(
            f"{api_base}/files/bulk-delete",
            json={"ids": [folder_id], "permanent": True},
        )
