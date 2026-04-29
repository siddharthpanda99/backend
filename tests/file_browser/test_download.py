"""Tests for file download functionality."""

import requests
import pytest


def test_download_file(api_base, temp_file):
    """Verify file download endpoint returns the file."""
    file_id = temp_file

    # Download the file
    resp = requests.get(f"{api_base}/files/{file_id}/download")
    assert resp.status_code == 200
    assert "text/plain" in resp.headers["content-type"]
    assert b"test file for modular testing" in resp.content


def test_download_nonexistent_file(api_base):
    """Verify download returns 404 for non-existent files."""
    resp = requests.get(f"{api_base}/files/nonexistent-id/download")
    assert resp.status_code == 404
