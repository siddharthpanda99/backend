"""Tests for remove tags functionality."""

import requests
import pytest


def test_add_and_remove_tags(api_base, temp_file):
    """Verify adding and removing tags from a file."""
    file_id = temp_file

    # Add tags
    resp = requests.post(
        f"{api_base}/files/{file_id}/tags", json={"tags": ["important", "work"]}
    )
    assert resp.status_code == 200
    assert "important" in resp.json()["tags"]
    assert "work" in resp.json()["tags"]

    # Remove one tag
    resp = requests.delete(
        f"{api_base}/files/{file_id}/tags", json={"tags": ["important"]}
    )
    assert resp.status_code == 200
    assert "important" not in resp.json()["tags"]
    assert "work" in resp.json()["tags"]


def test_remove_nonexistent_tag(api_base, temp_file):
    """Verify removing a non-existent tag doesn't error."""
    file_id = temp_file

    resp = requests.delete(
        f"{api_base}/files/{file_id}/tags", json={"tags": ["nonexistent"]}
    )
    assert resp.status_code == 200


def test_remove_all_tags(api_base, temp_file):
    """Verify removing all tags leaves empty list."""
    file_id = temp_file

    # Add tags
    requests.post(f"{api_base}/files/{file_id}/tags", json={"tags": ["tag1", "tag2"]})

    # Remove all
    resp = requests.delete(
        f"{api_base}/files/{file_id}/tags", json={"tags": ["tag1", "tag2"]}
    )
    assert resp.status_code == 200
    assert resp.json()["tags"] == []
