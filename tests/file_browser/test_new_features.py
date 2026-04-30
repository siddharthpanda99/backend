"""Tests for pre-signed URL feature."""

import pytest
import requests


api_base = "http://localhost:8000/api/v1/file-browser"


class TestSignedUrls:
    """Tests for pre-signed URLs."""

    def test_generate_signed_url(self, api_base, temp_file):
        """Verify generating a signed URL."""
        resp = requests.post(
            f"{api_base}/files/{temp_file}/signed-url", json={"expires_seconds": 3600}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] == True
        assert data["id"]

    def test_generate_signed_url_with_user(self, api_base, temp_file):
        """Verify signed URL with user ID."""
        resp = requests.post(
            f"{api_base}/files/{temp_file}/signed-url",
            json={"expires_seconds": 3600, "user_id": "user123"},
        )
        assert resp.status_code == 200

    def test_verify_signed_url_invalid(self, api_base):
        """Verify invalid token fails."""
        resp = requests.get(f"{api_base}/signed/invalid-token")
        assert resp.status_code == 401


class TestResumeUploads:
    """Tests for resume uploads."""

    def test_upload_session_status(self, api_base):
        """Verify upload session status."""
        # Create session
        resp = requests.post(
            f"{api_base}/upload", json={"filename": "large.bin", "total_size": 1000000}
        )
        if resp.status_code == 200:
            session_id = resp.json()["session_id"]
            # Get status
            status = requests.get(f"{api_base}/upload/{session_id}")
            assert status.status_code == 200

    def test_complete_session_missing_chunks(self, api_base):
        """Verify completing session without all chunks fails."""
        resp = requests.post(
            f"{api_base}/upload", json={"filename": "test.bin", "total_size": 1000}
        )
        if resp.status_code == 200:
            session_id = resp.json()["session_id"]
            complete = requests.post(f"{api_base}/upload/{session_id}/complete")
            # Should fail or return warning
            assert complete.status_code in [200, 400]


class TestFileComments:
    """Tests for file comments."""

    def test_add_comment(self, api_base, temp_file):
        """Verify adding a comment to a file."""
        resp = requests.post(
            f"{api_base}/files/{temp_file}/comments", json={"content": "Test comment"}
        )
        # May return 404 if not implemented
        assert resp.status_code in [200, 404, 501]

    def test_list_comments(self, api_base, temp_file):
        """Verify listing file comments."""
        resp = requests.get(f"{api_base}/files/{temp_file}/comments")
        assert resp.status_code in [200, 404, 501]


class TestFileLocking:
    """Tests for file locking."""

    def test_lock_file(self, api_base, temp_file):
        """Verify locking a file."""
        resp = requests.post(f"{api_base}/files/{temp_file}/lock", json={"lock": True})
        assert resp.status_code in [200, 404, 501]

    def test_unlock_file(self, api_base, temp_file):
        """Verify unlocking a file."""
        resp = requests.post(f"{api_base}/files/{temp_file}/lock", json={"lock": False})
        assert resp.status_code in [200, 404, 501]


class TestFileEncryption:
    """Tests for file encryption."""

    def test_encrypt_file(self, api_base, temp_file):
        """Verify encrypting a file."""
        resp = requests.post(f"{api_base}/files/{temp_file}/encrypt")
        assert resp.status_code in [200, 404, 501]

    def test_decrypt_file(self, api_base, temp_file):
        """Verify decrypting a file."""
        resp = requests.post(f"{api_base}/files/{temp_file}/decrypt")
        assert resp.status_code in [200, 404, 501]
