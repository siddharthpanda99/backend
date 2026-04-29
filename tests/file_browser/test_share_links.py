"""Tests for share links functionality."""

import requests
import pytest


def test_create_share_link(api_base, temp_file):
    """Verify creating a share link for a file."""
    file_id = temp_file

    # Create share link
    resp = requests.post(
        f"{api_base}/files/{file_id}/share",
        json={"access_level": "view", "expires_days": 7},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data
    assert "url" in data
    assert "token" in data
    assert data["access_level"] == "view"
    assert data["expires_days"] == 7


def test_list_share_links(api_base, temp_file):
    """Verify listing share links for a file."""
    file_id = temp_file

    # Create a link first
    requests.post(f"{api_base}/files/{file_id}/share", json={"access_level": "view"})

    # List links
    resp = requests.get(f"{api_base}/files/{file_id}/shares")
    assert resp.status_code == 200
    links = resp.json()
    assert len(links) >= 1
    assert links[0]["resource_id"] == file_id


def test_list_all_share_links(api_base, temp_file):
    """Verify listing all share links."""
    file_id = temp_file
    requests.post(f"{api_base}/files/{file_id}/share", json={"access_level": "view"})

    resp = requests.get(f"{api_base}/shares")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_revoke_share_link(api_base, temp_file):
    """Verify revoking a share link."""
    file_id = temp_file

    # Create link
    resp = requests.post(
        f"{api_base}/files/{file_id}/share", json={"access_level": "view"}
    )
    link_id = resp.json()["id"]

    # Revoke it
    resp = requests.delete(f"{api_base}/shares/{link_id}")
    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_get_share_link_by_token(api_base, temp_file):
    """Verify accessing file via share token."""
    file_id = temp_file

    # Create link
    resp = requests.post(
        f"{api_base}/files/{file_id}/share", json={"access_level": "view"}
    )
    token = resp.json()["token"]

    # Access via token
    resp = requests.get(f"{api_base}/share/{token}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["file_id"] == file_id
    assert "access_level" in data


def test_share_link_file_not_found(api_base):
    """Verify share link creation fails for non-existent file."""
    resp = requests.post(
        f"{api_base}/files/nonexistent/share", json={"access_level": "view"}
    )
    # May return 404 or other error depending on implementation
    assert resp.status_code in [404, 500]
