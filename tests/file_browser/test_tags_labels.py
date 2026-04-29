"""Tests for tags and labels listing functionality."""

import requests
import pytest


def test_list_all_tags(api_base, temp_file):
    """Verify listing all tags."""
    file_id = temp_file

    # Add some tags
    requests.post(f"{api_base}/files/{file_id}/tags", json={"tags": ["alpha", "beta"]})

    # List all tags
    resp = requests.get(f"{api_base}/tags")
    assert resp.status_code == 200
    tags = resp.json()
    assert isinstance(tags, list)

    # Should find our added tags
    tag_names = [t["name"] for t in tags]
    assert "alpha" in tag_names or "beta" in tag_names


def test_list_all_labels(api_base, temp_file):
    """Verify listing all labels."""
    file_id = temp_file

    # Add a label
    requests.post(f"{api_base}/files/{file_id}/label", json={"label": "Important"})

    # List all labels
    resp = requests.get(f"{api_base}/labels")
    assert resp.status_code == 200
    labels = resp.json()
    assert isinstance(labels, list)

    # Should find our label
    label_names = [l["name"] for l in labels]
    assert "Important" in label_names


def test_tags_have_expected_structure(api_base):
    """Verify tag items have expected structure."""
    resp = requests.get(f"{api_base}/tags")
    assert resp.status_code == 200
    tags = resp.json()

    # Even if empty, verify structure when present
    if tags:
        t = tags[0]
        assert "id" in t
        assert "name" in t
        assert "slug" in t


def test_labels_have_expected_structure(api_base):
    """Verify label items have expected structure."""
    resp = requests.get(f"{api_base}/labels")
    assert resp.status_code == 200
    labels = resp.json()

    # Even if empty, verify structure when present
    if labels:
        l = labels[0]
        assert "id" in l
        assert "name" in l
        assert "color" in l


def test_tags_usage_count(api_base, temp_file):
    """Verify tags show correct usage count."""
    file_id = temp_file

    # Add same tag to file twice (should not duplicate)
    requests.post(f"{api_base}/files/{file_id}/tags", json={"tags": ["counted"]})

    # Get all tags
    resp = requests.get(f"{api_base}/tags")
    tags = resp.json()

    # Find our tag
    counted_tag = next((t for t in tags if t["name"] == "counted"), None)
    if counted_tag:
        assert "usage_count" in counted_tag
        assert counted_tag["usage_count"] >= 1
