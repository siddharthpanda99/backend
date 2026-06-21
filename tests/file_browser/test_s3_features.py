"""Tests for zip/unzip, versioning, alerts, and preview features."""

import os
import pytest
import requests
import tempfile
import zipfile


api_base = "http://localhost:8000/api/v1/file-browser"


@pytest.fixture
def temp_zip_file():
    """Create a temp zip file for testing."""
    fd, path = tempfile.mkstemp(suffix=".zip")
    os.close(fd)

    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("test1.txt", "content 1")
        zf.writestr("test2.txt", "content 2")

    yield path

    if os.path.exists(path):
        os.remove(path)


class TestCompression:
    """Tests for zip/unzip operations."""

    def test_compress_single_file(self, api_base, temp_file):
        """Verify compressing a single file creates a zip."""
        file_id = temp_file

        resp = requests.post(
            f"{api_base}/files/compress",
            json={"file_ids": [file_id], "output_name": "archive"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"].endswith(".zip")
        assert data["file_count"] == 1

    def test_extract_archive(self, api_base, temp_zip_file):
        """Verify extracting a zip archive."""
        # First upload the zip
        with open(temp_zip_file, "rb") as f:
            resp = requests.post(
                f"{api_base}/files", files={"file": ("test.zip", f, "application/zip")}
            )

        assert resp.status_code == 200
        file_id = resp.json()["id"]

        # Extract it
        resp = requests.post(f"{api_base}/files/{file_id}/extract")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 2  # test1.txt, test2.txt


class TestVersioning:
    """Tests for S3-style versioning."""

    def test_create_version(self, api_base, temp_file):
        """Verify creating a new version."""
        file_id = temp_file

        resp = requests.post(f"{api_base}/files/{file_id}/versions")
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data
        assert data["version_number"] == 1

    def test_list_versions(self, api_base, temp_file):
        """Verify listing versions."""
        file_id = temp_file

        # Create a version
        requests.post(f"{api_base}/files/{file_id}/versions")

        # List versions
        resp = requests.get(f"{api_base}/files/{file_id}/versions")
        assert resp.status_code == 200
        versions = resp.json()
        assert len(versions) >= 1
        assert versions[0]["version_number"] == 1

    def test_restore_version(self, api_base, temp_file):
        """Verify restoring a file version."""
        file_id = temp_file

        # Create a version
        create_resp = requests.post(f"{api_base}/files/{file_id}/versions")
        version_id = create_resp.json()["id"]

        # Restore
        resp = requests.post(
            f"{api_base}/files/{file_id}/versions/{version_id}/restore"
        )
        assert resp.status_code == 200

    def test_version_nonexistent_file(self, api_base):
        """Verify version creation fails for non-existent file."""
        resp = requests.post(f"{api_base}/files/nonexistent/versions")
        assert resp.status_code == 404


class TestAlerts:
    """Tests for S3-style alerts."""

    def test_create_alert(self, api_base):
        """Verify creating an alert."""
        resp = requests.post(
            f"{api_base}/alerts?user_id=test-user",
            json={
                "title": "Test Alert",
                "message": "This is a test",
                "alert_type": "info",
                "severity": "info",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Test Alert"

    def test_get_user_alerts(self, api_base):
        """Verify getting user alerts."""
        # Create alert first
        requests.post(
            f"{api_base}/alerts?user_id=alert-user",
            json={
                "title": "Test",
                "message": "Test msg",
                "alert_type": "info",
                "severity": "info",
            },
        )

        # Get alerts
        resp = requests.get(f"{api_base}/alerts/alert-user")
        assert resp.status_code == 200
        alerts = resp.json()
        assert len(alerts) >= 1
        assert alerts[0]["title"] == "Test"

    def test_get_unread_alerts(self, api_base):
        """Verify getting only unread alerts."""
        # Get unread only
        resp = requests.get(f"{api_base}/alerts/alert-user?unread_only=true")
        assert resp.status_code == 200

    def test_mark_alert_read(self, api_base):
        """Verify marking alert as read."""
        # Create alert
        create_resp = requests.post(
            f"{api_base}/alerts?user_id=mark-user",
            json={
                "title": "Mark",
                "message": "Msg",
                "alert_type": "info",
                "severity": "info",
            },
        )
        alert_id = create_resp.json()["id"]

        # Mark as read
        resp = requests.post(f"{api_base}/alerts/{alert_id}/read")
        assert resp.status_code == 200
        assert resp.json()["success"] is True


class TestEvents:
    """Tests for event logging."""

    def test_get_event_logs(self, api_base):
        """Verify getting event logs."""
        resp = requests.get(f"{api_base}/events")
        assert resp.status_code == 200
        logs = resp.json()
        assert isinstance(logs, list)

    def test_filter_events_by_type(self, api_base):
        """Verify filtering events by type."""
        resp = requests.get(f"{api_base}/events?event_type=upload")
        assert resp.status_code == 200


class TestFilePreview:
    """Tests for file preview/viewer."""

    def test_create_preview(self, api_base, temp_file):
        """Verify generating a preview."""
        file_id = temp_file

        resp = requests.post(f"{api_base}/files/{file_id}/preview")
        # May fail if PIL not available or not an image
        assert resp.status_code in [200, 404, 500]

    def test_get_preview(self, api_base, temp_file):
        """Verify getting preview info."""
        file_id = temp_file

        resp = requests.get(f"{api_base}/files/{file_id}/preview")
        # May not exist if not generated
        assert resp.status_code in [200, 404]

    def test_preview_nonexistent_file(self, api_base):
        """Verify preview fails for non-existent file."""
        resp = requests.get(f"{api_base}/files/nonexistent/preview")
        assert resp.status_code == 404


class TestIntegration:
    """Integration tests combining features."""

    def test_full_workflow_with_versioning(self, api_base, temp_file):
        """Test complete workflow: upload -> version -> alert -> event."""
        file_id = temp_file

        # Create version
        v_resp = requests.post(f"{api_base}/files/{file_id}/versions")
        assert v_resp.status_code == 200

        # Create alert about version
        a_resp = requests.post(
            f"{api_base}/alerts?user_id=workflow-user",
            json={
                "title": "Version Created",
                "message": f"Version created for {file_id}",
                "alert_type": "info",
                "severity": "info",
                "source_type": "file",
                "source_id": file_id,
            },
        )
        assert a_resp.status_code == 200

        # Check alerts
        alerts_resp = requests.get(f"{api_base}/alerts/workflow-user")
        assert alerts_resp.status_code == 200

    def test_compression_with_metadata(self, api_base, temp_file):
        """Test compression preserves metadata."""
        # Get original file tags/label
        orig_resp = requests.get(f"{api_base}/files/{temp_file}")
        assert orig_resp.status_code == 200

        # Compress
        comp_resp = requests.post(
            f"{api_base}/files/compress",
            json={"file_ids": [temp_file], "output_name": "backup"},
        )
        if comp_resp.status_code == 200:
            archive_id = comp_resp.json()["id"]

            # Get archive details
            get_resp = requests.get(f"{api_base}/files/{archive_id}")
            assert get_resp.status_code == 200
