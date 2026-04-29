"""Tests for filtering and search functionality."""

import requests
import pytest


def test_filter_by_type_image(api_base, test_id):
    """Verify filtering files by image type."""
    # Upload an image-like file (with image extension)
    files = {"file": (f"photo_{test_id}.jpg", b"fake image data")}
    resp = requests.post(f"{api_base}/files", files=files)
    image_id = resp.json()["id"]

    try:
        # Upload non-image
        files = {"file": (f"doc_{test_id}.txt", b"text")}
        requests.post(f"{api_base}/files", files=files)

        # Filter by image
        resp = requests.get(f"{api_base}/files", params={"type": "image"})
        assert resp.status_code == 200
        items = resp.json()["items"]

        # Should have at least our image file
        assert any(item["id"] == image_id for item in items)

    finally:
        requests.post(
            f"{api_base}/files/bulk-delete", json={"ids": [image_id], "permanent": True}
        )


def test_filter_by_date_today(api_base, test_id):
    """Verify filtering files by date range (today)."""
    files = {"file": (f"today_{test_id}.txt", b"content")}
    resp = requests.post(f"{api_base}/files", files=files)
    file_id = resp.json()["id"]

    try:
        resp = requests.get(f"{api_base}/files", params={"date_range": "today"})
        assert resp.status_code == 200
        assert isinstance(resp.json()["items"], list)
    finally:
        requests.post(
            f"{api_base}/files/bulk-delete", json={"ids": [file_id], "permanent": True}
        )


def test_filter_by_tags(api_base, test_id):
    """Verify filtering files by tags."""
    file_id = None

    # Upload file
    files = {"file": (f"tagged_{test_id}.txt", b"content")}
    resp = requests.post(f"{api_base}/files", files=files)
    file_id = resp.json()["id"]

    try:
        # Add tag
        requests.post(f"{api_base}/files/{file_id}/tags", json={"tags": ["important"]})

        # Filter by tag - we need to use the tags param
        resp = requests.get(f"{api_base}/files", params={"tags": "important"})
        assert resp.status_code == 200
        items = resp.json()["items"]

        # Should find our tagged file
        assert any(item["id"] == file_id for item in items)

    finally:
        if file_id:
            requests.post(
                f"{api_base}/files/bulk-delete",
                json={"ids": [file_id], "permanent": True},
            )


def test_search_by_name(api_base, test_id):
    """Verify searching files by name."""
    filename = f"unique_searchable_name_{test_id}"
    files = {"file": (filename, b"content")}
    resp = requests.post(f"{api_base}/files", files=files)
    file_id = resp.json()["id"]

    try:
        resp = requests.get(f"{api_base}/search", params={"q": "unique_searchable"})
        assert resp.status_code == 200
        items = resp.json()["items"]

        # Should find the file
        assert any(item["id"] == file_id for item in items)

    finally:
        requests.post(
            f"{api_base}/files/bulk-delete", json={"ids": [file_id], "permanent": True}
        )


def test_combined_filters(api_base, test_id):
    """Verify combining multiple filters."""
    files = {"file": (f"combined_{test_id}.jpg", b"image")}
    resp = requests.post(f"{api_base}/files", files=files)
    file_id = resp.json()["id"]

    try:
        # Add tag
        requests.post(f"{api_base}/files/{file_id}/tags", json={"tags": ["work"]})

        # Search + filter by type
        resp = requests.get(
            f"{api_base}/files",
            params={"search": "combined", "type": "image", "tags": "work"},
        )
        assert resp.status_code == 200

    finally:
        requests.post(
            f"{api_base}/files/bulk-delete", json={"ids": [file_id], "permanent": True}
        )


def test_sort_by_name_ascending(api_base, test_id):
    """Verify sorting files by name ascending."""
    # Upload files with different names
    names = ["zzz_file", "aaa_file", "mmm_file"]
    ids = []

    for name in names:
        files = {"file": (f"{name}_{test_id}.txt", b"content")}
        resp = requests.post(f"{api_base}/files", files=files)
        ids.append(resp.json()["id"])

    try:
        # Sort by name ascending
        resp = requests.get(
            f"{api_base}/files", params={"sort_by": "name", "sort_order": "asc"}
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        names_in_order = [
            item["name"] for item in items if any(n in item["name"] for n in names)
        ]

        # Should be sorted alphabetically
        assert names_in_order == sorted(names_in_order)

    finally:
        requests.post(
            f"{api_base}/files/bulk-delete", json={"ids": ids, "permanent": True}
        )


def test_sort_by_name_descending(api_base, test_id):
    """Verify sorting files by name descending."""
    names = ["aaa_test", "zzz_test", "mmm_test"]
    ids = []

    for name in names:
        files = {"file": (f"{name}_{test_id}.txt", b"content")}
        resp = requests.post(f"{api_base}/files", files=files)
        ids.append(resp.json()["id"])

    try:
        resp = requests.get(
            f"{api_base}/files", params={"sort_by": "name", "sort_order": "desc"}
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        test_items = [item for item in items if any(n in item["name"] for n in names)]

        # Verify descending order
        for i in range(len(test_items) - 1):
            assert test_items[i]["name"] >= test_items[i + 1]["name"]

    finally:
        requests.post(
            f"{api_base}/files/bulk-delete", json={"ids": ids, "permanent": True}
        )
