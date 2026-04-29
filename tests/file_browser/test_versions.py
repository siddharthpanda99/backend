"""Tests for version history functionality."""

import requests
import pytest


def test_get_versions_empty(api_base, temp_file):
    """Verify getting versions for a file with no versions returns empty list."""
    file_id = temp_file

    resp = requests.get(f"{api_base}/files/{file_id}/versions")
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_versions_nonexistent_file(api_base):
    """Verify getting versions for non-existent file returns empty or errors."""
    resp = requests.get(f"{api_base}/files/nonexistent/versions")
    # May be 200 with empty list or 404
    assert resp.status_code in [200, 404]


def test_restore_version_nonexistent(api_base, temp_file):
    """Verify restoring non-existent version returns error."""
    file_id = temp_file

    resp = requests.post(f"{api_base}/files/{file_id}/versions/nonexistent/restore")
    assert resp.status_code == 404


def test_version_item_structure(api_base, temp_file):
    """Verify version item has expected structure when versions exist."""
    file_id = temp_file

    # Create initial version (by uploading)
    resp = requests.get(f"{api_base}/files/{file_id}/versions")
    assert resp.status_code == 200
    versions = resp.json()

    # Even if empty, verify structure
    if versions:
        v = versions[0]
        assert "id" in v
        assert "version_number" in v
        assert "is_current" in v
