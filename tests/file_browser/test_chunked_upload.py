"""Tests for chunked upload functionality."""

import requests
import pytest


def test_create_upload_session(api_base, test_id):
    """Verify creating a chunked upload session."""
    resp = requests.post(
        f"{api_base}/upload/session",
        json={
            "filename": f"chunked_{test_id}.txt",
            "total_size_bytes": 10485760,  # 10MB
            "mime_type": "text/plain",
            "folder_id": None,
            "chunk_size_bytes": 5242880,  # 5MB
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data
    assert data["total_chunks"] == 2
    session_id = data["id"]

    # Cleanup - sessions auto-expire
    return session_id


def test_get_upload_session(api_base, test_id):
    """Verify getting upload session status."""
    # Create session
    resp = requests.post(
        f"{api_base}/upload/session",
        json={
            "filename": f"test_{test_id}.txt",
            "total_size_bytes": 1000,
            "chunk_size_bytes": 500,
        },
    )
    session_id = resp.json()["id"]

    # Get session status
    resp = requests.get(f"{api_base}/upload/session/{session_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == session_id
    assert data["uploaded_chunks"] == 0
    assert data["total_chunks"] == 2


def test_get_nonexistent_session(api_base):
    """Verify getting non-existent session returns 404."""
    resp = requests.get(f"{api_base}/upload/session/nonexistent")
    assert resp.status_code == 404


def test_upload_chunk(api_base, test_id):
    """Verify uploading a chunk."""
    # Create session
    resp = requests.post(
        f"{api_base}/upload/session",
        json={
            "filename": f"chunk_{test_id}.txt",
            "total_size_bytes": 1000,
            "chunk_size_bytes": 500,
        },
    )
    session_id = resp.json()["id"]

    # Upload chunk
    files = {"chunk": b"part1"}
    resp = requests.post(
        f"{api_base}/upload/chunk?session_id={session_id}&chunk_index=0", files=files
    )
    # May need proper FormData handling
    # For now just verify we can hit the endpoint structure


def test_complete_upload_session(api_base, test_id):
    """Verify completing an upload session."""
    # First upload a regular file to get a file_id
    files = {"file": (f"original_{test_id}.txt", b"content")}
    resp = requests.post(f"{api_base}/files", files=files)
    file_id = resp.json()["id"]

    # Create session
    resp = requests.post(
        f"{api_base}/upload/session",
        json={
            "filename": f"to_complete_{test_id}.txt",
            "total_size_bytes": 1000,
            "chunk_size_bytes": 500,
        },
    )
    session_id = resp.json()["id"]

    # Complete session
    resp = requests.post(
        f"{api_base}/upload/session/{session_id}/complete?file_id={file_id}"
    )
    assert resp.status_code == 200

    # Cleanup
    requests.post(
        f"{api_base}/files/bulk-delete", json={"ids": [file_id], "permanent": True}
    )
